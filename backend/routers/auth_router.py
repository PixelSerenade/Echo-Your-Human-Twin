import hashlib
import secrets
import time
import uuid
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db
from backend.models import User, TwinWeight, Permission
from backend.schemas import SignUpRequest, LoginRequest, UserSessionResponse, TwinWeightsOut
from backend.services.identity import resolve_twin_name
from backend.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

# In-memory rate limiter: { key: [timestamps] }
FAILED_LOGIN_ATTEMPTS: Dict[str, List[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60.0  # seconds
MAX_FAILED_ATTEMPTS = 5

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000).hex()
    return f"{salt}${key}"

def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, key = hashed.split("$")
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000).hex()
        return secrets.compare_digest(key, new_key)
    except Exception:
        return False

def check_rate_limit(key: str):
    now = time.time()
    # Retain only timestamps within the window
    FAILED_LOGIN_ATTEMPTS[key] = [t for t in FAILED_LOGIN_ATTEMPTS[key] if now - t < RATE_LIMIT_WINDOW]
    if len(FAILED_LOGIN_ATTEMPTS[key]) >= MAX_FAILED_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait 60 seconds before trying again."
        )

def record_failed_attempt(key: str):
    FAILED_LOGIN_ATTEMPTS[key].append(time.time())

def clear_failed_attempts(key: str):
    if key in FAILED_LOGIN_ATTEMPTS:
        del FAILED_LOGIN_ATTEMPTS[key]

def get_current_user_id(request: Request) -> Optional[str]:
    # 1. Cookie
    user_id = request.cookies.get("session_user_id")
    if user_id:
        return user_id
    # 2. X-User-Id header
    user_id = request.headers.get("X-User-Id")
    if user_id:
        return user_id
    # 3. Authorization Bearer
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:].strip()
    return None

@router.post("/signup", response_model=UserSessionResponse)
async def signup(req: SignUpRequest, response: Response, db: AsyncSession = Depends(get_db)):
    email_clean = req.email.strip().lower()
    name_clean = req.name.strip()

    # Email format validation
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email_clean):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    # Password complexity check (min 8 chars, at least 1 digit or symbol)
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")
    if not (any(c.isdigit() for c in req.password) or any(not c.isalnum() for c in req.password)):
        raise HTTPException(status_code=400, detail="Password must contain at least one number or symbol.")

    # Check if email is already registered
    res = await db.execute(select(User).where(User.email == email_clean))
    existing = res.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    new_user_id = str(uuid.uuid4())
    pw_hash = hash_password(req.password)

    new_user = User(
        id=new_user_id,
        name=name_clean,
        email=email_clean,
        password_hash=pw_hash,
        twin_name="Echo",
        twin_name_customized=False,
        onboarding_completed=False,
        onboarding_step="persona"
    )
    db.add(new_user)


    # Default initial weights
    default_weights = TwinWeight(
        user_id=new_user_id,
        rational=0.34,
        emotional=0.33,
        ambitious=0.33,
        primary_twin="rational"
    )
    db.add(default_weights)
    await db.commit()
    await db.refresh(new_user)

    # Set httpOnly cookie
    response.set_cookie(
        key="session_user_id",
        value=new_user_id,
        httponly=True,
        samesite="lax",
        path="/"
    )

    return UserSessionResponse(
        user_id=new_user.id,
        name=new_user.name,
        email=new_user.email,
        twin_name=new_user.twin_name,
        twin_name_customized=False,
        onboarding_completed=new_user.onboarding_completed,
        onboarding_step=new_user.onboarding_step,
        persona=new_user.persona or "student",
        primary_twin="rational",
        weights=TwinWeightsOut(
            rational=0.34,
            emotional=0.33,
            ambitious=0.33,
            primary_twin="rational"
        )
    )

@router.post("/login", response_model=UserSessionResponse)
async def login(req: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    email_clean = req.email.strip().lower()
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{email_clean}"

    check_rate_limit(rate_key)

    res = await db.execute(select(User).where(User.email == email_clean))
    user = res.scalar_one_or_none()

    # Check credentials with generic error to prevent user enumeration
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        # Demo account fallback for convenience
        if user and user.id == "demo-alex-rivers" and (req.password == "alex123" or req.password == "demo1234"):
            clear_failed_attempts(rate_key)
        else:
            record_failed_attempt(rate_key)
            raise HTTPException(status_code=401, detail="Invalid email or password.")
    else:
        clear_failed_attempts(rate_key)

    # Set httpOnly cookie
    response.set_cookie(
        key="session_user_id",
        value=user.id,
        httponly=True,
        samesite="lax",
        path="/"
    )

    # Get user weights
    w_res = await db.execute(select(TwinWeight).where(TwinWeight.user_id == user.id))
    weights = w_res.scalar_one_or_none()
    weights_out = None
    primary_twin = "rational"
    if weights:
        primary_twin = weights.primary_twin
        weights_out = TwinWeightsOut(
            rational=weights.rational,
            emotional=weights.emotional,
            ambitious=weights.ambitious,
            primary_twin=weights.primary_twin
        )

    safe_twin_name = resolve_twin_name(user)
    await db.commit()
    return UserSessionResponse(
        user_id=user.id,
        name=user.name,
        email=user.email,
        twin_name=safe_twin_name,
        twin_name_customized=bool(user.twin_name_customized),
        onboarding_completed=bool(user.onboarding_completed),
        onboarding_step=user.onboarding_step or "tags",
        persona=user.persona or "student",
        primary_twin=primary_twin,
        weights=weights_out
    )

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="session_user_id", path="/")
    return {"message": "Logged out successfully"}

@router.get("/me", response_model=UserSessionResponse)
async def get_me(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User session not found.")

    w_res = await db.execute(select(TwinWeight).where(TwinWeight.user_id == user.id))
    weights = w_res.scalar_one_or_none()
    weights_out = None
    primary_twin = "rational"
    if weights:
        primary_twin = weights.primary_twin
        weights_out = TwinWeightsOut(
            rational=weights.rational,
            emotional=weights.emotional,
            ambitious=weights.ambitious,
            primary_twin=weights.primary_twin
        )

    safe_twin_name = resolve_twin_name(user)
    await db.commit()
    return UserSessionResponse(
        user_id=user.id,
        name=user.name,
        email=user.email,
        twin_name=safe_twin_name,
        twin_name_customized=bool(user.twin_name_customized),
        onboarding_completed=bool(user.onboarding_completed),
        onboarding_step=user.onboarding_step or "tags",
        persona=user.persona or "student",
        primary_twin=primary_twin,
        weights=weights_out
    )


@router.delete("/account")
async def delete_account(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found.")
    folder = Path(settings.UPLOAD_DIR) / user_id
    if folder.exists():
        shutil.rmtree(folder)
    await db.delete(user)
    await db.commit()
    response.delete_cookie(key="session_user_id", path="/")
    return {"message": "Your account and uploaded files have been deleted."}
