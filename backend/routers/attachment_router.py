import io
import os
import shutil
import time
import uuid
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from backend.config import settings
from backend.database import get_db
from backend.llm.gemini_client import gemini_client
from backend.models import Attachment, User, Timetable, Permission
from backend.memory_registry import defaults_for
from backend.routers.auth_router import get_current_user_id

router = APIRouter(prefix="/api", tags=["attachments"])

MAX_BYTES = settings.MAX_UPLOAD_BYTES
UNSUPPORTED = (
    "That file type isn't supported. Try a PDF, DOCX, TXT, image (PNG, JPG, WEBP) "
    "or video (MP4, WEBM)."
)
RATE_WINDOW_SECONDS = 60.0
RATE_MAX = 20
_requests: Dict[str, List[float]] = defaultdict(list)


def _require_user(request: Request) -> str:
    user_id = get_current_user_id(request) or request.query_params.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Please sign in before adding a file.")
    return user_id


def _rate_limit(user_id: str, action: str) -> None:
    key = f"{user_id}:{action}"
    now = time.monotonic()
    _requests[key] = [stamp for stamp in _requests[key] if now - stamp < RATE_WINDOW_SECONDS]
    if len(_requests[key]) >= RATE_MAX:
        raise HTTPException(status_code=429, detail="That's a lot at once. Give it a moment, then try again.")
    _requests[key].append(now)


async def _read_limited(request: Request) -> bytes:
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_BYTES:
            raise HTTPException(status_code=413, detail="Only files up to 5 MB are allowed.")
    if not data:
        raise HTTPException(status_code=400, detail="That file looks empty. Try choosing it again.")
    return bytes(data)


def _is_text(data: bytes) -> bool:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if "\x00" in text:
        return False
    sample = text[:4096]
    return not sample or sum(ord(char) < 32 and char not in "\n\r\t" for char in sample) / len(sample) < 0.02


def sniff_type(filename: str, data: bytes) -> Tuple[str, str]:
    extension = Path(filename).suffix.lower()
    if extension == ".pdf" and data.startswith(b"%PDF-"):
        return "application/pdf", "document"
    if extension == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "image"
    if extension in {".jpg", ".jpeg"} and data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "image"
    if extension == ".webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "image"
    if extension == ".mp4" and len(data) >= 12 and data[4:8] == b"ftyp":
        return "video/mp4", "video"
    if extension == ".webm" and data.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm", "video"
    if extension == ".txt" and _is_text(data):
        return "text/plain", "document"
    if extension == ".docx" and data.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
                if "[Content_Types].xml" in names and any(name.startswith("word/") for name in names):
                    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "document"
        except zipfile.BadZipFile:
            pass
    raise HTTPException(status_code=415, detail=UNSUPPORTED)


def _attachment_path(item: Attachment) -> Path:
    return Path(settings.UPLOAD_DIR) / item.user_id / item.stored_name


@router.post("/attachments", status_code=201)
async def upload_attachment(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = _require_user(request)
    _rate_limit(user_id, "upload")
    if not await db.get(User, user_id):
        raise HTTPException(status_code=401, detail="Your session has expired. Please sign in again.")
    filename = unquote(request.headers.get("x-file-name", "attachment"))[:255]
    data = await _read_limited(request)
    mime_type, kind = sniff_type(filename, data)
    attachment_id = str(uuid.uuid4())
    stored_name = f"{uuid.uuid4().hex}.bin"
    folder = Path(settings.UPLOAD_DIR) / user_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / stored_name
    try:
        path.write_bytes(data)
        item = Attachment(
            id=attachment_id,
            user_id=user_id,
            original_name=filename,
            stored_name=stored_name,
            mime_type=mime_type,
            kind=kind,
            size_bytes=len(data),
        )
        db.add(item)
        await db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return _serialize(item)


def _serialize(item: Attachment) -> dict:
    return {
        "id": item.id,
        "name": item.original_name,
        "mime_type": item.mime_type,
        "kind": item.kind,
        "size_bytes": item.size_bytes,
        "created_at": item.created_at,
    }


@router.get("/attachments")
async def list_attachments(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = _require_user(request)
    result = await db.execute(
        select(Attachment).where(Attachment.user_id == user_id).order_by(Attachment.created_at.desc())
    )
    return {"attachments": [_serialize(item) for item in result.scalars().all()]}


async def _owned_attachment(attachment_id: str, user_id: str, db: AsyncSession) -> Attachment:
    item = await db.get(Attachment, attachment_id)
    if not item or item.user_id != user_id:
        raise HTTPException(status_code=404, detail="I couldn't find that file.")
    return item


@router.get("/attachments/{attachment_id}")
async def view_attachment(attachment_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    item = await _owned_attachment(attachment_id, _require_user(request), db)
    path = _attachment_path(item)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="I couldn't find that file.")
    return FileResponse(path, media_type=item.mime_type, filename=item.original_name)


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(attachment_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    item = await _owned_attachment(attachment_id, _require_user(request), db)
    _attachment_path(item).unlink(missing_ok=True)
    await db.delete(item)
    await db.commit()
    return {"message": "That file has been deleted."}


@router.post("/transcribe")
async def transcribe(request: Request):
    user_id = _require_user(request)
    _rate_limit(user_id, "transcribe")
    audio = await _read_limited(request)
    mime_type = request.headers.get("content-type", "").split(";", 1)[0]
    if mime_type not in {"audio/webm", "audio/mp4", "audio/ogg", "audio/wav"}:
        raise HTTPException(status_code=415, detail="Hmm, I couldn't catch that. Try again?")
    try:
        transcript = await gemini_client.call_gemini_text(
            "Transcribe this audio faithfully. Return only the spoken words, without timestamps or commentary.",
            system_instruction="You are a precise speech transcription service.",
            temperature=0.1,
            inline_data={"mime_type": mime_type, "data": audio},
        )
    except Exception as exc:
        print(f"Transcription failed: {exc}")
        if settings.DEMO_MODE or not settings.GEMINI_API_KEY:
            return {"transcript": "What should I focus on tonight?"}
        raise HTTPException(status_code=502, detail="Hmm, I couldn't catch that. Try again?") from exc
    return {"transcript": transcript.strip()}


def delete_user_uploads(user_id: str) -> None:
    folder = Path(settings.UPLOAD_DIR) / user_id
    if folder.exists():
        shutil.rmtree(folder)


class ConfirmItem(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    day: str
    start_time: str
    end_time: str


class ConfirmExtractedRequest(BaseModel):
    items: List[ConfirmItem]


@router.post("/attachments/{attachment_id}/confirm-extracted")
async def confirm_extracted_items(
    attachment_id: str,
    payload: ConfirmExtractedRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user_id = _require_user(request)
    await _owned_attachment(attachment_id, user_id, db)
    user = await db.get(User, user_id)
    permission_rows = (await db.execute(select(Permission).where(Permission.user_id == user_id, Permission.source.in_(["schedule_commitments", "timetable"])))).scalars().all()
    permission_map = {row.source: row.enabled for row in permission_rows}
    schedule_enabled = permission_map.get("schedule_commitments", permission_map.get("timetable", defaults_for(getattr(user, "persona", "student"))["schedule_commitments"]))
    if not schedule_enabled:
        raise HTTPException(status_code=403, detail="Turn on Schedule & Commitments in Privacy before saving schedule items.")
    allowed_days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
    saved = []
    for item in payload.items:
        if item.day.lower() not in allowed_days:
            continue
        entry = Timetable(
            user_id=user_id,
            day_of_week=item.day.capitalize(),
            start_time=item.start_time,
            end_time=item.end_time,
            activity_name=item.title,
            location="Imported attachment",
            is_mandatory=True,
        )
        db.add(entry)
        saved.append(item.title)
    await db.commit()
    return {"message": "Those timetable items are saved.", "saved": saved}
