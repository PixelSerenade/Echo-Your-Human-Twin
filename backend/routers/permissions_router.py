from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict
import datetime

from backend.database import get_db
from backend.models import Permission, User, ConsentEntry
from backend.schemas import PermissionsResponse, PermissionUpdateRequest
from backend.services.data_access import ALL_SOURCES
from backend.memory_registry import CATEGORIES, LEGACY_TO_CATEGORY, defaults_for, PERSONAS, PERMISSION_WORDING_VERSION

router = APIRouter(tags=["Permissions & Privacy Control"])

@router.get("/permissions", response_model=PermissionsResponse)
@router.get("/api/permissions", response_model=PermissionsResponse)
async def get_permissions(
    user_id: str = Query("demo-alex-rivers", description="User ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get privacy permission toggles. Mood and tone inference is opt-in;
    legacy personal data sources default to enabled.
    """
    res = await db.execute(
        select(Permission).where(Permission.user_id == user_id)
    )
    records = {p.source: p.enabled for p in res.scalars().all()}

    user = await db.get(User, user_id)
    defaults = defaults_for(getattr(user, "persona", "student"))
    output = {src: records.get(src, records.get(CATEGORIES[src]["legacy"], defaults[src]) if CATEGORIES[src]["legacy"] else defaults[src]) for src in ALL_SOURCES}
    output.update({legacy: output[category] for legacy, category in LEGACY_TO_CATEGORY.items()})

    return PermissionsResponse(
        user_id=user_id,
        permissions=output
    )

@router.put("/permissions", response_model=PermissionsResponse)
@router.put("/api/permissions", response_model=PermissionsResponse)
async def update_permissions(
    req: PermissionUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Update permission toggles for data sources.
    Enforces real-time access revocation across all twin capabilities.
    """
    user_id = req.user_id or "demo-alex-rivers"

    # Ensure user exists
    user = await db.get(User, user_id)
    if not user:
        user = User(id=user_id, name="Alex Rivers", email=f"{user_id}@humantwin.ai")
        db.add(user)
        await db.flush()

    # Upsert each permission
    for source, enabled in req.permissions.items():
        source = LEGACY_TO_CATEGORY.get(source, source)
        if source not in ALL_SOURCES:
            continue
        res = await db.execute(
            select(Permission).where(
                Permission.user_id == user_id,
                Permission.source == source
            )
        )
        perm = res.scalar_one_or_none()
        if perm:
            perm.enabled = enabled
            perm.updated_at = datetime.datetime.utcnow()
        else:
            perm = Permission(
                user_id=user_id,
                source=source,
                enabled=enabled,
                updated_at=datetime.datetime.utcnow()
            )
            db.add(perm)
        db.add(ConsentEntry(user_id=user_id, category=source, value=bool(enabled), wording_version=PERMISSION_WORDING_VERSION, timestamp=datetime.datetime.utcnow()))

    await db.commit()

    # Re-read and return current state
    res = await db.execute(
        select(Permission).where(Permission.user_id == user_id)
    )
    records = {p.source: p.enabled for p in res.scalars().all()}
    user = await db.get(User, user_id)
    defaults = defaults_for(getattr(user, "persona", "student"))
    output = {src: records.get(src, defaults[src]) for src in ALL_SOURCES}
    output.update({legacy: output[category] for legacy, category in LEGACY_TO_CATEGORY.items()})

    return PermissionsResponse(
        user_id=user_id,
        permissions=output
    )
