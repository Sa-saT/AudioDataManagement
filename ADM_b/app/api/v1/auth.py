from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import License, User, UserRole
from app.models.creator import CreatorProfile, CreatorRank
from app.schemas.auth import ActivateJsonRequest, ActivateResponse, UserOut
from app.security.jwt import create_access_token
from app.security.license import (
    LicenseError,
    LicensePayload,
    check_validity,
    parse_lic_bytes,
    validate_payload,
    verify_signature,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


async def _read_lic_bytes(request: Request, file: UploadFile | None) -> bytes:
    """ファイルアップロードまたは JSON body {"lic": "..."} から raw bytes を返す。
    Phase C バイナリは file 経由で送る (JSON body は text 専用)。"""
    if file is not None:
        return await file.read()

    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if content_type == "application/json":
        try:
            body = await request.json()
        except ValueError as exc:
            raise _error("MALFORMED_LICENSE", f"invalid json body: {exc}", 400)
        try:
            req = ActivateJsonRequest(**body)
        except Exception as exc:
            raise _error("MALFORMED_LICENSE", str(exc), 400)
        return req.lic.encode("utf-8")

    raise _error(
        "MALFORMED_LICENSE",
        "expected multipart 'file' or JSON body with 'lic'",
        400,
    )


def _upsert_user_and_license(db: Session, payload: LicensePayload) -> tuple[User, License]:
    license_row = db.execute(
        select(License).where(License.license_code == payload.license_code)
    ).scalar_one_or_none()

    if license_row is not None:
        if license_row.revoked_at is not None:
            raise _error("LICENSE_REVOKED", "license has been revoked", 401)
        user = db.get(User, license_row.user_id)
        if user is None:
            raise _error("INTERNAL_ERROR", "license has no user", 500)
        user.username = payload.username
        user.role = UserRole(payload.role)
        license_row.role = UserRole(payload.role)
        license_row.monthly_quota_tokens = payload.monthly_quota_tokens
        license_row.group_name = payload.raw.get("group") or None
        license_row.signature = payload.signature
        license_row.issued_at = payload.issued_at
        license_row.expires_at = payload.expires_at
        return user, license_row

    existing_user = db.execute(
        select(User).where(User.username == payload.username)
    ).scalar_one_or_none()

    if existing_user is None:
        user = User(username=payload.username, role=UserRole(payload.role))
        db.add(user)
        db.flush()
    else:
        if existing_user.license is not None and existing_user.license.license_code != payload.license_code:
            raise _error(
                "USERNAME_TAKEN",
                "username already bound to a different license",
                409,
            )
        existing_user.role = UserRole(payload.role)
        user = existing_user

    license_row = License(
        user_id=user.id,
        license_code=payload.license_code,
        role=UserRole(payload.role),
        monthly_quota_tokens=payload.monthly_quota_tokens,
        group_name=payload.raw.get("group") or None,
        signature=payload.signature,
        issued_at=payload.issued_at,
        expires_at=payload.expires_at,
    )
    db.add(license_row)
    db.flush()

    _ensure_creator_profile(db, user, payload.role)
    return user, license_row


def _ensure_creator_profile(db: Session, user: User, role: str) -> None:
    """role=creator/admin で CreatorProfile が無ければ自動作成 (display_name=username)."""
    if role not in ("creator", "admin"):
        return
    profile = db.execute(
        select(CreatorProfile).where(CreatorProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is not None:
        return
    db.add(CreatorProfile(
        user_id=user.id,
        display_name=user.username,
        rank=CreatorRank.bronze,
    ))
    db.flush()


@router.post(
    "/activate",
    response_model=ActivateResponse,
    status_code=status.HTTP_200_OK,
)
async def activate(
    request: Request,
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> ActivateResponse:
    raw = await _read_lic_bytes(request, file)

    try:
        data = parse_lic_bytes(raw)
        payload = validate_payload(data)
        verify_signature(payload, require=True)
        check_validity(payload)
    except LicenseError as exc:
        status_code = 401 if exc.code in {
            "INVALID_LICENSE_SIGNATURE",
            "LICENSE_EXPIRED",
            "LICENSE_REVOKED",
        } else 400
        raise _error(exc.code, exc.message, status_code)

    user, license_row = _upsert_user_and_license(db, payload)
    # B案: activate 毎に新セッション UUID を発行し DB に保存。
    # 以降のリクエストでは JWT.sid と DB.current_session_id を照合 → 不一致なら旧セッションは無効。
    new_session_id = uuid.uuid4()
    license_row.current_session_id = new_session_id
    db.commit()
    db.refresh(user)
    db.refresh(license_row)

    token, expires = create_access_token(
        user_id=user.id,
        role=user.role.value,
        license_id=license_row.id,
        session_id=new_session_id,
    )

    return ActivateResponse(
        access_token=token,
        expires_at=expires,
        user=UserOut(
            id=str(user.id),
            username=user.username,
            role=user.role.value,
            license_code=license_row.license_code,
            monthly_quota_tokens=license_row.monthly_quota_tokens,
        ),
    )
