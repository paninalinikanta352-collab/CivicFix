import json
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from ai_detector import analyze_photo
from ai_service import calculate_risk_percentage
from ai_categorizer import detect_category
from auth import current_user, require_role
from database import get_db
from models import IssueCreate, IssueList, IssuePatch, IssuePublic, IssueStatus, IssueUpdatePublic, StatusUpdate

router = APIRouter(prefix='/api/issues', tags=['Issues'])
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / 'uploads'
MAX_PHOTO_BYTES = 8 * 1024 * 1024
IMAGE_SIGNATURES = {
    'image/jpeg': (b'\xff\xd8\xff', '.jpg'),
    'image/png': (b'\x89PNG\r\n\x1a\n', '.png'),
    'image/webp': (b'RIFF', '.webp'),
}

@router.get('', response_model=IssueList)
def list_issues(category: str | None = None, issue_status: str | None = Query(default=None, alias='status'), limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    clauses, values = [], []
    if category:
        clauses.append('category=?'); values.append(category)
    if issue_status:
        if issue_status not in {'reported','assigned','in_progress','resolved','rejected'}:
            raise HTTPException(status_code=422, detail='Invalid status filter')
        clauses.append('status=?'); values.append(issue_status)
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    with get_db() as conn:
        total = conn.execute('SELECT COUNT(*) FROM issues' + where, values).fetchone()[0]
        rows = conn.execute('SELECT * FROM issues' + where + ' ORDER BY created_at DESC LIMIT ? OFFSET ?', [*values, limit, offset]).fetchall()
    return {'items': [dict(row) for row in rows], 'total': total, 'limit': limit, 'offset': offset}

@router.post('', response_model=IssuePublic, status_code=status.HTTP_201_CREATED)
async def create_issue(
    title: str = Form(min_length=4, max_length=160),
    description: str = Form(min_length=8, max_length=5000),
    category: str = Form(default='other', pattern='^(roads|water|electricity|cleanliness|other)$'),
    latitude: float | None = Form(default=None, ge=-90, le=90, alias='lat'),
    longitude: float | None = Form(default=None, ge=-180, le=180, alias='lng'),
    address: str | None = Form(default=None, max_length=500),
    photo: UploadFile = File(..., alias='image'),
    user=Depends(current_user),
):
    """Create an issue with a required JPEG, PNG, or WebP photo (maximum 8 MB)."""
    title, description = title.strip(), description.strip()
    if len(title) < 4 or len(description) < 8:
        raise HTTPException(status_code=422, detail='Title must be at least 4 characters and description at least 8')
    if not title or not description:
        raise HTTPException(status_code=422, detail='Title and description are required')

    mime_type = photo.content_type or ''
    signature_info = IMAGE_SIGNATURES.get(mime_type)
    if signature_info is None:
        raise HTTPException(status_code=415, detail='Photo must be JPEG, PNG, or WebP')

    contents = await photo.read(MAX_PHOTO_BYTES + 1)
    await photo.close()
    if len(contents) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail='Photo must be 8 MB or smaller')
    signature, extension = signature_info
    valid_signature = contents.startswith(signature)
    if mime_type == 'image/webp':
        valid_signature = valid_signature and len(contents) >= 12 and contents[8:12] == b'WEBP'
    if not valid_signature:
        raise HTTPException(status_code=415, detail='Photo contents do not match the declared image type')

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f'{uuid4().hex}{extension}'
    image_path = UPLOAD_DIR / filename
    image_path.write_bytes(contents)

    # Optional AI category detection: when the citizen left the category as
    # 'other', ask the configured LLM to classify from title + description.
    # Never blocks reporting - detect_category returns None on any failure.
    category_source = 'user'
    if category == 'other':
        detected = await run_in_threadpool(detect_category, title, description)
        if detected:
            category = detected['category']
            category_source = 'ai'
        else:
            category_source = 'default'

    risk = calculate_risk_percentage(category, description, address or "")
    # Optional AI enhancement: inspect the photo and cross-check the title.
    # Every failure inside analyze_photo returns None, so reporting still works
    # even without the model files installed. Risk score is never touched.
    ai_result = await run_in_threadpool(analyze_photo, contents, title)
    ai_json = json.dumps(ai_result) if ai_result else None
    try:
        with get_db() as conn:
            cursor = conn.execute('''INSERT INTO issues(title,description,category,latitude,longitude,address,photo_url,risk_percentage,ai_analysis,category_source,reporter_id)
              VALUES(?,?,?,?,?,?,?,?,?,?,?)''', (title, description, category, latitude, longitude, address, f'/uploads/{filename}', risk, ai_json, category_source, user['id']))
            issue = conn.execute('SELECT * FROM issues WHERE id=?', (cursor.lastrowid,)).fetchone()
            conn.execute('INSERT INTO issue_updates(issue_id,actor_id,status,note) VALUES(?,?,?,?)', (issue['id'], user['id'], 'reported', 'Issue submitted'))
    except Exception:
        image_path.unlink(missing_ok=True)
        raise
    return dict(issue)

@router.get('/{issue_id}', response_model=IssuePublic)
def get_issue(issue_id: int):
    with get_db() as conn:
        issue = conn.execute('SELECT * FROM issues WHERE id=?', (issue_id,)).fetchone()
    if issue is None:
        raise HTTPException(status_code=404, detail='Issue not found')
    return dict(issue)

@router.patch('/{issue_id}', response_model=IssuePublic)
def edit_issue(issue_id: int, payload: IssuePatch, user=Depends(current_user)):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail='No changes supplied')
    with get_db() as conn:
        issue = conn.execute('SELECT * FROM issues WHERE id=?', (issue_id,)).fetchone()
        if issue is None:
            raise HTTPException(status_code=404, detail='Issue not found')
        if issue['reporter_id'] != user['id'] and user['role'] != 'admin':
            raise HTTPException(status_code=403, detail='Only the reporter or an admin can edit issue details')
        merged = dict(issue); merged.update(changes)
        if 'category' in changes or 'description' in changes or 'address' in changes:
            changes['risk_percentage'] = calculate_risk_percentage(
                str(merged['category']),
                str(merged['description']),
                str(merged.get('address') or ''),
            )
        allowed = {'title','description','category','latitude','longitude','address','risk_percentage','category_source'}
        if 'category' in changes:
            changes.setdefault('category_source', 'user')
        fields = {key: value for key, value in changes.items() if key in allowed}
        assignments = [f'{key}=?' for key in fields]
        assignments.append("updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')")
        conn.execute(f"UPDATE issues SET {','.join(assignments)} WHERE id=?", [*fields.values(), issue_id])
        result = conn.execute('SELECT * FROM issues WHERE id=?', (issue_id,)).fetchone()
    return dict(result)

@router.post('/{issue_id}/status', response_model=IssuePublic)
def update_status(issue_id: int, payload: StatusUpdate, user=Depends(require_role('worker','admin'))):
    with get_db() as conn:
        issue = conn.execute('SELECT * FROM issues WHERE id=?', (issue_id,)).fetchone()
        if issue is None:
            raise HTTPException(status_code=404, detail='Issue not found')
        if user['role'] == 'worker' and issue['assigned_worker_id'] != user['id']:
            raise HTTPException(status_code=403, detail='This issue is not assigned to you')
        conn.execute("UPDATE issues SET status=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?", (payload.status, issue_id))
        conn.execute('INSERT INTO issue_updates(issue_id,actor_id,status,note) VALUES(?,?,?,?)', (issue_id, user['id'], payload.status, payload.note))
        result = conn.execute('SELECT * FROM issues WHERE id=?', (issue_id,)).fetchone()
    return dict(result)

@router.get('/{issue_id}/updates', response_model=list[IssueUpdatePublic])
def issue_updates(issue_id: int):
    with get_db() as conn:
        exists = conn.execute('SELECT 1 FROM issues WHERE id=?', (issue_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail='Issue not found')
        rows = conn.execute('SELECT * FROM issue_updates WHERE issue_id=? ORDER BY created_at,id', (issue_id,)).fetchall()
    return [dict(row) for row in rows]
