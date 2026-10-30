import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status
from auth import hash_password, require_role
from database import get_db
from models import AssignWorker, IssueList, IssuePublic, WorkerCreate, UserPublic

router = APIRouter(prefix='/api/admin', tags=['Admin'])

@router.get('/issues', response_model=IssueList)
def admin_issues(limit: int = 100, offset: int = 0, admin=Depends(require_role('admin'))):
    if limit < 1 or limit > 500 or offset < 0:
        raise HTTPException(status_code=422, detail='limit must be 1–500 and offset must be non-negative')
    with get_db() as conn:
        total = conn.execute('SELECT COUNT(*) FROM issues').fetchone()[0]
        rows = conn.execute('SELECT * FROM issues ORDER BY risk_percentage DESC, created_at ASC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return {'items': [dict(row) for row in rows], 'total': total, 'limit': limit, 'offset': offset}

@router.get('/workers', response_model=list[UserPublic])
def workers(admin=Depends(require_role('admin'))):
    with get_db() as conn:
        rows = conn.execute("SELECT id,name,email,role,created_at FROM users WHERE role='worker' ORDER BY name").fetchall()
    return [dict(row) for row in rows]

@router.post('/workers', response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_worker(payload: WorkerCreate, admin=Depends(require_role('admin'))):
    try:
        with get_db() as conn:
            cursor = conn.execute("INSERT INTO users(name,email,password_hash,role,email_verified) VALUES(?,?,?,'worker',1)", (payload.name.strip(), payload.email.lower(), hash_password(payload.password)))
            row = conn.execute('SELECT id,name,email,role,created_at FROM users WHERE id=?', (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail='An account with this email already exists')
    return dict(row)

@router.post('/issues/{issue_id}/assign', response_model=IssuePublic)
def assign_worker(issue_id: int, payload: AssignWorker, admin=Depends(require_role('admin'))):
    with get_db() as conn:
        issue = conn.execute('SELECT * FROM issues WHERE id=?', (issue_id,)).fetchone()
        worker = conn.execute("SELECT id FROM users WHERE id=? AND role='worker'", (payload.worker_id,)).fetchone()
        if issue is None:
            raise HTTPException(status_code=404, detail='Issue not found')
        if worker is None:
            raise HTTPException(status_code=404, detail='Worker not found')
        conn.execute("UPDATE issues SET assigned_worker_id=?, status='assigned', updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?", (payload.worker_id, issue_id))
        conn.execute('INSERT INTO issue_updates(issue_id,actor_id,status,note) VALUES(?,?,?,?)', (issue_id, admin['id'], 'assigned', f"Assigned to worker {payload.worker_id}"))
        result = conn.execute('SELECT * FROM issues WHERE id=?', (issue_id,)).fetchone()
    return dict(result)

@router.get('/stats')
def stats(admin=Depends(require_role('admin'))):
    with get_db() as conn:
        totals = {row['status']: row['count'] for row in conn.execute('SELECT status,COUNT(*) AS count FROM issues GROUP BY status')}
        total = conn.execute('SELECT COUNT(*) FROM issues').fetchone()[0]
        workers_count = conn.execute("SELECT COUNT(*) FROM users WHERE role='worker'").fetchone()[0]
        average_risk = conn.execute('SELECT COALESCE(ROUND(AVG(risk_percentage),1),0) FROM issues').fetchone()[0]
    return {'total_issues': total, 'issues_by_status': totals, 'workers': workers_count, 'average_risk_percentage': average_risk}
