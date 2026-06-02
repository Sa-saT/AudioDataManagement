from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import License, User
from app.security.jwt import TokenError, decode_token

bearer = HTTPBearer(auto_error=False)


def _validate_session(db: Session, payload: dict) -> None:
    """B案: JWT.sid と licenses.current_session_id を照合。
    別端末で /activate されると DB 側の sid が更新されるため、旧トークンは無効化される。
    """
    jwt_sid = payload.get("sid")
    license_id = payload.get("license_id")
    if jwt_sid is None or license_id is None:
        # 旧トークン (B案以前) は強制的に再アクティベートさせる
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "SESSION_INVALIDATED", "message": "session not bound; re-activate"},
        )
    license_row = db.execute(
        select(License).where(License.id == license_id)
    ).scalar_one_or_none()
    if license_row is None or license_row.current_session_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "SESSION_INVALIDATED", "message": "session not found; re-activate"},
        )
    if str(license_row.current_session_id) != str(jwt_sid):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "SESSION_INVALIDATED", "message": "another device activated this license"},
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "NOT_AUTHENTICATED", "message": "JWT required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        )
    _validate_session(db, payload)
    user = db.execute(select(User).where(User.id == payload["sub"])).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "USER_NOT_FOUND", "message": "user not found"},
        )
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
    except TokenError:
        return None
    # B案: optional でもセッション無効ならログイン無扱い (黙って guest)
    jwt_sid = payload.get("sid")
    license_id = payload.get("license_id")
    if jwt_sid is None or license_id is None:
        return None
    license_row = db.execute(select(License).where(License.id == license_id)).scalar_one_or_none()
    if license_row is None or str(license_row.current_session_id) != str(jwt_sid):
        return None
    return db.execute(select(User).where(User.id == payload["sub"])).scalar_one_or_none()


def require_role(*roles: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role.value not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": f"requires role: {list(roles)}"},
            )
        return user
    return _dep
