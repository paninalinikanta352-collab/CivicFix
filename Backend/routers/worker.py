"""Endpoints for workers: view and progress their assigned issues."""
from fastapi import APIRouter, Depends
from auth import require_role
from database import get_db
from models import IssuePublic

router = APIRouter(prefix='/api/worker', tags=['Worker'])


@router.get('/assignments', response_model=list[IssuePublic])
def my_assignments(worker=Depends(require_role('worker'))):
    """Issues currently assigned to the logged-in worker, riskiest first."""
    with get_db() as conn:
        rows = conn.execute(
            'SELECT * FROM issues WHERE assigned_worker_id=? '
            "ORDER BY risk_percentage DESC, created_at DESC",
            (worker['id'],),
        ).fetchall()
    return [dict(row) for row in rows]
