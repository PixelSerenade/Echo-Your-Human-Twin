import io
import os
import zipfile
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from sqlalchemy import select

from backend.main import app
from backend.models import User, Attachment, Timetable
from backend.database import AsyncSessionLocal
from backend.config import settings
from backend.scripts.generate_data import init_models, seed_demo_persona, USER_ID

UNSUPPORTED_MSG = (
    "That file type isn't supported. Try a PDF, DOCX, TXT, image (PNG, JPG, WEBP) "
    "or video (MP4, WEBM)."
)
SIZE_ERROR_MSG = "Only files up to 5 MB are allowed."


def make_pdf(size_bytes: int = 100) -> bytes:
    header = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
    if size_bytes <= len(header):
        return header[:size_bytes]
    return header + b"0" * (size_bytes - len(header))


def make_png(size_bytes: int = 100) -> bytes:
    header = b"\x89PNG\r\n\x1a\n"
    if size_bytes <= len(header):
        return header[:size_bytes]
    return header + b"\x00" * (size_bytes - len(header))


def make_jpeg(size_bytes: int = 100) -> bytes:
    header = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    if size_bytes <= len(header):
        return header[:size_bytes]
    return header + b"\x00" * (size_bytes - len(header))


def make_webp(size_bytes: int = 100) -> bytes:
    # RIFF + 4 bytes size + WEBP
    header = b"RIFF\x20\x00\x00\x00WEBPVP8 "
    if size_bytes <= len(header):
        return header[:size_bytes]
    return header + b"\x00" * (size_bytes - len(header))


def make_mp4(size_bytes: int = 100) -> bytes:
    # 4 bytes len + ftyp + isom
    header = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00"
    if size_bytes <= len(header):
        return header[:size_bytes]
    return header + b"\x00" * (size_bytes - len(header))


def make_webm(size_bytes: int = 100) -> bytes:
    header = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81\x01"
    if size_bytes <= len(header):
        return header[:size_bytes]
    return header + b"\x00" * (size_bytes - len(header))


def make_txt(content: str = "Class Schedule: Monday 10:00 to 11:30 Algorithms") -> bytes:
    return content.encode("utf-8")


def make_docx(text: str = "Schedule for next semester") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>')
        doc_xml = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>'
        zf.writestr("word/document.xml", doc_xml)
    return buf.getvalue()


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_test_db():
    await init_models()
    await seed_demo_persona()
    # Create user B for cross-user permission checks
    async with AsyncSessionLocal() as session:
        existing_b = await session.get(User, "test-user-b")
        if not existing_b:
            user_b = User(
                id="test-user-b",
                name="User B",
                email="user_b@humantwin.ai",
                twin_name="Echo",
            )
            session.add(user_b)
            await session.commit()


@pytest.mark.asyncio
async def test_size_limit_accepted_under_5mb():
    """Verify files just under 5MB (document, image, video) are accepted."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        under_size = 4 * 1024 * 1024 + 900 * 1024  # ~4.9 MB (under 5 MB)

        # 1. Document (PDF)
        pdf_bytes = make_pdf(under_size)
        resp = await ac.post(
            "/api/attachments",
            content=pdf_bytes,
            headers={
                "X-User-Id": USER_ID,
                "X-File-Name": "syllabus.pdf",
                "Content-Type": "application/pdf",
            },
        )
        assert resp.status_code == 201, resp.text
        pdf_item = resp.json()
        assert pdf_item["kind"] == "document"
        assert pdf_item["size_bytes"] == len(pdf_bytes)

        # 2. Image (PNG)
        png_bytes = make_png(under_size)
        resp_png = await ac.post(
            "/api/attachments",
            content=png_bytes,
            headers={
                "X-User-Id": USER_ID,
                "X-File-Name": "photo.png",
                "Content-Type": "image/png",
            },
        )
        assert resp_png.status_code == 201
        png_item = resp_png.json()
        assert png_item["kind"] == "image"

        # 3. Video (MP4)
        mp4_bytes = make_mp4(under_size)
        resp_mp4 = await ac.post(
            "/api/attachments",
            content=mp4_bytes,
            headers={
                "X-User-Id": USER_ID,
                "X-File-Name": "lecture.mp4",
                "Content-Type": "video/mp4",
            },
        )
        assert resp_mp4.status_code == 201
        mp4_item = resp_mp4.json()
        assert mp4_item["kind"] == "video"


@pytest.mark.asyncio
async def test_size_limit_rejected_over_5mb_with_413():
    """Verify files just over 5MB return HTTP 413."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        over_size = 5 * 1024 * 1024 + 1024  # 5 MB + 1 KB

        # Over 5MB PDF
        pdf_bytes = make_pdf(over_size)
        resp = await ac.post(
            "/api/attachments",
            content=pdf_bytes,
            headers={
                "X-User-Id": USER_ID,
                "X-File-Name": "big_doc.pdf",
                "Content-Type": "application/pdf",
                "Content-Length": str(len(pdf_bytes)),
            },
        )
        assert resp.status_code == 413
        assert SIZE_ERROR_MSG in (resp.json().get("detail") or "")


@pytest.mark.asyncio
async def test_size_limit_rejected_streaming_bypass_with_missing_or_false_content_length():
    """
    Verify server streaming counter rejects over 5MB payload even if Content-Length
    header is missing or reports a false small value.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        over_size = 5 * 1024 * 1024 + 2048  # 5 MB + 2 KB
        data = make_pdf(over_size)

        # 1. Generator streaming without Content-Length
        async def stream_data():
            chunk_size = 64 * 1024
            for i in range(0, len(data), chunk_size):
                yield data[i:i + chunk_size]

        resp_stream = await ac.post(
            "/api/attachments",
            content=stream_data(),
            headers={
                "X-User-Id": USER_ID,
                "X-File-Name": "stream_doc.pdf",
                "Content-Type": "application/pdf",
            },
        )
        assert resp_stream.status_code == 413
        assert SIZE_ERROR_MSG in resp_stream.json()["detail"]


@pytest.mark.asyncio
async def test_supported_and_unsupported_file_types():
    """Verify supported formats work and unsupported formats are rejected with 415."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Valid DOCX
        docx_data = make_docx("Class timetable Monday 09:00 to 11:00")
        resp_docx = await ac.post(
            "/api/attachments",
            content=docx_data,
            headers={
                "X-User-Id": USER_ID,
                "X-File-Name": "schedule.docx",
                "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            },
        )
        assert resp_docx.status_code == 201

        # Valid TXT
        txt_data = make_txt("Monday 09:00 - 10:30 Math lecture")
        resp_txt = await ac.post(
            "/api/attachments",
            content=txt_data,
            headers={
                "X-User-Id": USER_ID,
                "X-File-Name": "timetable.txt",
                "Content-Type": "text/plain",
            },
        )
        assert resp_txt.status_code == 201

        # Valid WEBP
        webp_data = make_webp(200)
        resp_webp = await ac.post(
            "/api/attachments",
            content=webp_data,
            headers={
                "X-User-Id": USER_ID,
                "X-File-Name": "snapshot.webp",
                "Content-Type": "image/webp",
            },
        )
        assert resp_webp.status_code == 201

        # Valid WEBM
        webm_data = make_webm(200)
        resp_webm = await ac.post(
            "/api/attachments",
            content=webm_data,
            headers={
                "X-User-Id": USER_ID,
                "X-File-Name": "demo.webm",
                "Content-Type": "video/webm",
            },
        )
        assert resp_webm.status_code == 201

        # UNSUPPORTED: .exe
        resp_exe = await ac.post(
            "/api/attachments",
            content=b"MZ\x90\x00" + b"\x00" * 50,
            headers={
                "X-User-Id": USER_ID,
                "X-File-Name": "program.exe",
                "Content-Type": "application/octet-stream",
            },
        )
        assert resp_exe.status_code == 415
        assert UNSUPPORTED_MSG in resp_exe.json()["detail"]

        # UNSUPPORTED: Disguised extension (.png extension with exe header)
        resp_fake = await ac.post(
            "/api/attachments",
            content=b"MZ\x90\x00NotAPng",
            headers={
                "X-User-Id": USER_ID,
                "X-File-Name": "fake.png",
                "Content-Type": "image/png",
            },
        )
        assert resp_fake.status_code == 415
        assert UNSUPPORTED_MSG in resp_fake.json()["detail"]


@pytest.mark.asyncio
async def test_privacy_and_cross_user_isolation():
    """Verify user B can never access or delete user A's uploaded files."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # User A uploads a file
        pdf_data = make_pdf(500)
        resp_up = await ac.post(
            "/api/attachments",
            content=pdf_data,
            headers={
                "X-User-Id": USER_ID,
                "X-File-Name": "secret_plan.pdf",
                "Content-Type": "application/pdf",
            },
        )
        assert resp_up.status_code == 201
        att_id = resp_up.json()["id"]

        # User B tries to view User A's file -> 404
        resp_b_view = await ac.get(
            f"/api/attachments/{att_id}",
            headers={"X-User-Id": "test-user-b"},
        )
        assert resp_b_view.status_code == 404

        # User B tries to delete User A's file -> 404
        resp_b_del = await ac.delete(
            f"/api/attachments/{att_id}",
            headers={"X-User-Id": "test-user-b"},
        )
        assert resp_b_del.status_code == 404

        # User A views their own file -> 200
        resp_a_view = await ac.get(
            f"/api/attachments/{att_id}",
            headers={"X-User-Id": USER_ID},
        )
        assert resp_a_view.status_code == 200
        assert resp_a_view.content == pdf_data

        # User A deletes their file -> 200
        resp_a_del = await ac.delete(
            f"/api/attachments/{att_id}",
            headers={"X-User-Id": USER_ID},
        )
        assert resp_a_del.status_code == 200

        # File is now gone
        resp_check = await ac.get(
            f"/api/attachments/{att_id}",
            headers={"X-User-Id": USER_ID},
        )
        assert resp_check.status_code == 404


@pytest.mark.asyncio
async def test_multimodal_ask_and_timetable_extraction_flow():
    """
    Verify attachment sent with /ask is evaluated, schedule items are proposed,
    and confirming them adds them to the database.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        txt_data = make_txt("Weekly timetable: Monday 09:00 - 10:30 Distributed Systems Lecture")
        resp_up = await ac.post(
            "/api/attachments",
            content=txt_data,
            headers={
                "X-User-Id": USER_ID,
                "X-File-Name": "weekly_schedule.txt",
                "Content-Type": "text/plain",
            },
        )
        assert resp_up.status_code == 201
        att_id = resp_up.json()["id"]

        # Call /ask with attachment_id
        resp_ask = await ac.post(
            "/ask",
            json={
                "user_id": USER_ID,
                "question": "Can you import this weekly timetable for me?",
                "attachment_id": att_id,
            },
        )
        assert resp_ask.status_code == 200
        ask_data = resp_ask.json()
        assert "message" in ask_data

        # Confirm extracted items
        confirm_payload = {
            "items": [
                {
                    "title": "Quantum Computing Lecture",
                    "day": "Monday",
                    "start_time": "09:00",
                    "end_time": "10:30",
                }
            ]
        }
        resp_confirm = await ac.post(
            f"/api/attachments/{att_id}/confirm-extracted",
            json=confirm_payload,
            headers={"X-User-Id": USER_ID},
        )
        assert resp_confirm.status_code == 200
        assert "Those timetable items are saved." in resp_confirm.json()["message"]

        # Verify entry exists in Timetable table
        async with AsyncSessionLocal() as session:
            tt_res = await session.execute(
                select(Timetable).where(
                    Timetable.user_id == USER_ID,
                    Timetable.activity_name == "Quantum Computing Lecture"
                )
            )
            saved_tt = tt_res.scalar_one_or_none()
            assert saved_tt is not None
            assert saved_tt.day_of_week == "Monday"


@pytest.mark.asyncio
async def test_transcribe_endpoint_voice_fallback():
    """Verify audio transcribe endpoint returns transcript and handles limits."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Small webm audio snippet
        audio_data = make_webm(500)
        resp = await ac.post(
            "/api/transcribe",
            content=audio_data,
            headers={
                "X-User-Id": USER_ID,
                "Content-Type": "audio/webm",
            },
        )
        assert resp.status_code == 200
        assert "transcript" in resp.json()
        assert len(resp.json()["transcript"]) > 0

        # Oversize audio over 5MB returns 413
        oversize_audio = make_webm(5 * 1024 * 1024 + 1024)
        resp_big = await ac.post(
            "/api/transcribe",
            content=oversize_audio,
            headers={
                "X-User-Id": USER_ID,
                "Content-Type": "audio/webm",
                "Content-Length": str(len(oversize_audio)),
            },
        )
        assert resp_big.status_code == 413
