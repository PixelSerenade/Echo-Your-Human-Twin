from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel
import datetime

from backend.database import get_db
from backend.models import AuditLog
from backend.schemas import AuditLogItem

router = APIRouter(tags=["Audit Log & Transparency"])

class AuditLogResponse(BaseModel):
    user_id: str
    total_entries: int
    entries: List[AuditLogItem]

@router.get("/audit-log", response_model=AuditLogResponse)
@router.get("/api/audit-log", response_model=AuditLogResponse)
async def get_audit_log(
    user_id: str = Query("demo-alex-rivers", description="User ID"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns audit log showing which data sources each answer or operation accessed,
    proving complete transparency and user privacy control.
    """
    res = await db.execute(
        select(AuditLog)
        .where(AuditLog.user_id == user_id)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
    )
    logs = res.scalars().all()

    entries = [
        AuditLogItem(
            id=log.id,
            action=log.action,
            endpoint=log.endpoint,
            sources_accessed=log.sources_accessed if isinstance(log.sources_accessed, list) else [],
            timestamp=log.timestamp
        )
        for log in logs
    ]

    return AuditLogResponse(
        user_id=user_id,
        total_entries=len(entries),
        entries=entries
    )
