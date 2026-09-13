import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import AdminUser, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)

ALGO = "HS256"


def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return pwd_context.verify(raw, hashed)


def create_token(subject: str, kind: str, extra: dict | None = None) -> str:
    payload = {
        "sub": subject,
        "kind": kind,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGO)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGO])
    except JWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已失效") from e


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract(creds: HTTPAuthorizationCredentials | None) -> str | None:
    return creds.credentials if creds else None


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    token = _extract(creds)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录")
    payload = decode_token(token)
    if payload.get("kind") != "user":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录类型错误")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    return user


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User | None:
    token = _extract(creds)
    if not token:
        return None
    try:
        payload = decode_token(token)
    except HTTPException:
        return None
    if payload.get("kind") != "user":
        return None
    return db.get(User, int(payload["sub"]))


def get_current_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> AdminUser:
    token = _extract(creds)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录后台")
    payload = decode_token(token)
    if payload.get("kind") != "admin":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录类型错误")
    admin = db.get(AdminUser, int(payload["sub"]))
    if not admin or not admin.enabled:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号不可用")
    return admin


def client_ip_hash(request: Request) -> str:
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "0.0.0.0")
    return sha256(ip.split(",")[0].strip())
