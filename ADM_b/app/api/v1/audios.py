import json
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db import get_db
from app.models import (
    Audio,
    CreatorPayout,
    CreatorProfile,
    CreatorRankPrice,
    DownloadKind,
    DownloadLog,
    PayoutStatus,
    TokenConsumption,
)
from app.models.audio import Tag, AudioTag
from app.models.base import new_uuid
from app.models.user import User
from app.schemas.audio import (
    AudioDetail,
    AudioListItem,
    AudioListResponse,
    AudioUpdateRequest,
    CreatorBrief,
    DownloadResponse,
)
from app.security.deps import get_current_user, get_optional_user, require_role
from app.security.signed_url import (
    SignedURLError,
    issue_download,
    issue_stream,
    verify_download,
    verify_stream,
)
from app.services import audio_file, tokens as tokens_service

settings = get_settings()

router = APIRouter(prefix="/audios", tags=["audios"])

_MIN_PER_PAGE = 5
_MAX_PER_PAGE = 200

_FILENAME_SAFE_RE = re.compile(r"[^\w\s\-.぀-ゟ゠-ヿ一-鿿]")


def _build_url(path: str, params: dict) -> str:
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{path}?{qs}"


def _safe_filename(title: str) -> str:
    s = _FILENAME_SAFE_RE.sub("", title).strip().replace(" ", "_")
    return s[:80] or "audio"


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _to_list_item(audio: Audio) -> AudioListItem:
    return AudioListItem(
        id=str(audio.id),
        title=audio.title,
        creator=CreatorBrief(
            id=str(audio.creator.user_id),
            display_name=audio.creator.display_name,
        ),
        duration_sec=audio.duration_sec,
        token_cost=audio.duration_sec,
        peaks=audio.peaks,
        youtube_safe=audio.youtube_safe,
        published_at=audio.published_at,
        tags=[t.name for t in audio.tags],
    )


@router.get("", response_model=AudioListResponse)
def list_audios(
    sort: Literal["recommended", "newest"] = Query("recommended"),
    page: int = Query(1, ge=1),
    per_page: int = Query(10),
    mine: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
) -> AudioListResponse:
    if per_page < _MIN_PER_PAGE or per_page > _MAX_PER_PAGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_PER_PAGE",
                "message": f"per_page must be between {_MIN_PER_PAGE} and {_MAX_PER_PAGE}",
            },
        )

    if mine:
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "NOT_AUTHENTICATED", "message": "JWT required for mine=true"},
            )
        base = (
            select(Audio)
            .options(joinedload(Audio.creator))
            .where(Audio.creator_id == current_user.id)
        )
        order = Audio.created_at.desc()
    else:
        base = (
            select(Audio)
            .options(joinedload(Audio.creator))
            .where(Audio.is_public.is_(True), Audio.downloaded_by_user_id.is_(None))
        )
        order = Audio.recommend_score.desc() if sort == "recommended" else Audio.published_at.desc()

    total: int = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()

    rows = db.execute(
        base.order_by(order).offset((page - 1) * per_page).limit(per_page)
    ).scalars().all()

    return AudioListResponse(
        total=total,
        page=page,
        per_page=per_page,
        items=[_to_list_item(a) for a in rows],
    )


@router.post("", response_model=AudioDetail, status_code=status.HTTP_201_CREATED)
def upload_audio(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str | None = Form(None),
    youtube_safe: bool = Form(True),
    is_public: bool = Form(False),
    tags_json: str = Form("[]"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("creator", "admin")),
) -> AudioDetail:
    profile = db.execute(
        select(CreatorProfile).where(CreatorProfile.user_id == current_user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "NO_CREATOR_PROFILE", "message": "creator profile not found"},
        )

    suffix = Path(file.filename or "upload.wav").suffix or ".wav"
    tmp_path: Path | None = None
    audio_id = new_uuid()
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)
            shutil.copyfileobj(file.file, tmp)

        try:
            meta = audio_file.probe(tmp_path)
        except audio_file.AudioFileError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": exc.code, "message": exc.message},
            )

        peaks = audio_file.compute_peaks(tmp_path)
        dest = audio_file.save_original(tmp_path, audio_id)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()

    try:
        tag_names: list[str] = json.loads(tags_json)
        if not isinstance(tag_names, list):
            tag_names = []
    except (json.JSONDecodeError, ValueError):
        tag_names = []

    audio = Audio(
        id=audio_id,
        creator_id=current_user.id,
        title=title,
        description=description,
        file_path=str(dest),
        duration_sec=meta.duration_sec,
        sample_rate=meta.sample_rate,
        bit_depth=meta.bit_depth,
        channels=meta.channels,
        peaks=peaks,
        youtube_safe=youtube_safe,
        is_public=is_public,
    )
    db.add(audio)
    db.flush()
    _sync_tags(db, audio, tag_names)
    db.commit()

    audio = db.execute(
        select(Audio).options(joinedload(Audio.creator)).where(Audio.id == audio_id)
    ).scalar_one()

    return _to_detail(audio)


@router.get("/stream")
def stream_audio(
    audio_id: str = Query(...),
    start: int = Query(0, ge=0),
    exp: int = Query(...),
    sig: str = Query(...),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    try:
        verify_stream(audio_id, start, exp, sig)
    except SignedURLError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": exc.code, "message": exc.message},
        )

    try:
        parsed_id = uuid.UUID(audio_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    audio = db.execute(
        select(Audio).where(Audio.id == parsed_id, Audio.is_public.is_(True))
    ).scalar_one_or_none()
    if audio is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    file_path = Path(audio.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "audio file missing"})

    proc = subprocess.Popen(
        [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-t", str(settings.PREVIEW_DURATION_SEC),
            "-i", str(file_path),
            "-c:a", "copy",
            "-f", "wav",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    def _iter_chunks():
        try:
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            proc.stdout.close()
            proc.wait()

    return StreamingResponse(_iter_chunks(), media_type="audio/wav")


@router.get("/download-file")
def download_file(
    audio_id: str = Query(...),
    exp: int = Query(...),
    sig: str = Query(...),
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        verify_download(audio_id, exp, sig)
    except SignedURLError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": exc.code, "message": exc.message},
        )

    try:
        parsed_id = uuid.UUID(audio_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    audio = db.execute(select(Audio).where(Audio.id == parsed_id)).scalar_one_or_none()
    if audio is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    file_path = Path(audio.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "FILE_NOT_FOUND", "message": "audio file missing"},
        )

    return FileResponse(
        path=str(file_path),
        media_type="audio/wav",
        filename=f"{_safe_filename(audio.title)}.wav",
    )


@router.post("/{audio_id}/download", response_model=DownloadResponse)
def download_audio(
    audio_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DownloadResponse:
    try:
        parsed_id = uuid.UUID(audio_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    audio = db.execute(
        select(Audio).where(Audio.id == parsed_id).with_for_update()
    ).scalar_one_or_none()
    if audio is None or not audio.is_public:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    ip = _client_ip(request)
    ua = request.headers.get("user-agent")
    role = current_user.role.value

    # ── creator: 自分の音源のみ DL可。token不要、sold にしない ────────────────
    if role == "creator":
        if audio.creator_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "CREATOR_CANNOT_DOWNLOAD", "message": "creators can only download their own audio"},
            )
        db.add(DownloadLog(
            user_id=current_user.id, audio_id=parsed_id,
            kind=DownloadKind.admin_preview, ip=ip, user_agent=ua,
        ))
        db.commit()
        params = issue_download(str(parsed_id))
        return DownloadResponse(
            download_url=_build_url("/api/v1/audios/download-file", params),
            is_redownload=False,
        )

    # ── admin: 全音源 DL可。token不要、sold にしない ──────────────────────────
    if role == "admin":
        db.add(DownloadLog(
            user_id=current_user.id, audio_id=parsed_id,
            kind=DownloadKind.admin_preview, ip=ip, user_agent=ua,
        ))
        db.commit()
        params = issue_download(str(parsed_id))
        return DownloadResponse(
            download_url=_build_url("/api/v1/audios/download-file", params),
            is_redownload=False,
        )

    # ── user: 以下は通常の購入フロー ──────────────────────────────────────────

    # Re-download by the original buyer: no token consumption, no payout.
    if audio.downloaded_by_user_id == current_user.id:
        db.add(DownloadLog(
            user_id=current_user.id, audio_id=parsed_id,
            kind=DownloadKind.redownload, ip=ip, user_agent=ua,
        ))
        db.commit()
        params = issue_download(str(parsed_id))
        return DownloadResponse(
            download_url=_build_url("/api/v1/audios/download-file", params),
            is_redownload=True,
        )

    # Already sold to someone else.
    if audio.downloaded_by_user_id is not None:
        db.add(DownloadLog(
            user_id=current_user.id, audio_id=parsed_id,
            kind=DownloadKind.denied_sold, ip=ip, user_agent=ua,
        ))
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ALREADY_SOLD", "message": "this audio has already been purchased by another user"},
        )

    # Initial purchase: token check, mark sold, create payout.
    license_obj = current_user.license
    if license_obj is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NO_LICENSE", "message": "no active license"},
        )

    cost = audio.duration_sec
    available = tokens_service.available_tokens(db, current_user.id, license_obj)
    if available < cost:
        db.add(DownloadLog(
            user_id=current_user.id, audio_id=parsed_id,
            kind=DownloadKind.denied_no_token, ip=ip, user_agent=ua,
        ))
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "INSUFFICIENT_TOKENS",
                "message": f"need {cost} tokens but only {available} available",
                "required": cost,
                "available": available,
            },
        )

    creator_profile = db.execute(
        select(CreatorProfile).where(CreatorProfile.user_id == audio.creator_id)
    ).scalar_one()
    rank_price = db.execute(
        select(CreatorRankPrice).where(CreatorRankPrice.rank == creator_profile.rank)
    ).scalar_one()

    audio.downloaded_by_user_id = current_user.id
    audio.downloaded_at = func.now()

    period = tokens_service.current_period_jst()
    db.add(TokenConsumption(
        user_id=current_user.id,
        audio_id=parsed_id,
        license_id=license_obj.id,
        tokens=cost,
        period_yyyymm=period,
    ))
    db.add(CreatorPayout(
        audio_id=parsed_id,
        creator_id=audio.creator_id,
        rank_at_payout=creator_profile.rank,
        unit_price_yen=rank_price.unit_price_yen,
        amount_yen=rank_price.unit_price_yen,
        status=PayoutStatus.pending,
    ))
    db.add(DownloadLog(
        user_id=current_user.id, audio_id=parsed_id,
        kind=DownloadKind.initial, ip=ip, user_agent=ua,
    ))
    db.commit()

    params = issue_download(str(parsed_id))
    return DownloadResponse(
        download_url=_build_url("/api/v1/audios/download-file", params),
        is_redownload=False,
        token_cost=cost,
        remaining_tokens=available - cost,
    )


@router.get("/{audio_id}/download-url", response_model=DownloadResponse)
def get_download_url(
    audio_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DownloadResponse:
    try:
        parsed_id = uuid.UUID(audio_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    audio = db.execute(select(Audio).where(Audio.id == parsed_id)).scalar_one_or_none()
    if audio is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    role = current_user.role.value
    ip = _client_ip(request)
    ua = request.headers.get("user-agent")

    # admin: 全音源を何度でも再DL可
    if role == "admin":
        db.add(DownloadLog(user_id=current_user.id, audio_id=parsed_id,
                           kind=DownloadKind.admin_preview, ip=ip, user_agent=ua))
        db.commit()
        params = issue_download(str(parsed_id))
        return DownloadResponse(download_url=_build_url("/api/v1/audios/download-file", params), is_redownload=True)

    # creator: 自分の音源のみ再DL可
    if role == "creator":
        if audio.creator_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail={"code": "CREATOR_CANNOT_DOWNLOAD", "message": "creators can only download their own audio"})
        db.add(DownloadLog(user_id=current_user.id, audio_id=parsed_id,
                           kind=DownloadKind.admin_preview, ip=ip, user_agent=ua))
        db.commit()
        params = issue_download(str(parsed_id))
        return DownloadResponse(download_url=_build_url("/api/v1/audios/download-file", params), is_redownload=True)

    # user: 購入済みチェック
    if audio.downloaded_by_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "NOT_PURCHASED", "message": "audio has not been purchased"},
        )
    if audio.downloaded_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NOT_OWNER", "message": "you do not own this audio"},
        )

    db.add(DownloadLog(user_id=current_user.id, audio_id=parsed_id,
                       kind=DownloadKind.redownload, ip=ip, user_agent=ua))
    db.commit()

    params = issue_download(str(parsed_id))
    return DownloadResponse(
        download_url=_build_url("/api/v1/audios/download-file", params),
        is_redownload=True,
    )


@router.get("/{audio_id}/stream-url")
def get_stream_url(
    audio_id: str,
    start: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    try:
        parsed_id = uuid.UUID(audio_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    audio = db.execute(
        select(Audio.id).where(Audio.id == parsed_id, Audio.is_public.is_(True))
    ).scalar_one_or_none()
    if audio is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    params = issue_stream(str(parsed_id), start)
    return {"url": _build_url("/api/v1/audios/stream", params)}


def _sync_tags(db: Session, audio: Audio, tag_names: list[str]) -> None:
    """Replace audio's tags with the given list, creating Tag rows as needed."""
    tag_names = [n.strip().lower() for n in tag_names if n.strip()]
    existing: dict[str, Tag] = {}
    if tag_names:
        rows = db.execute(select(Tag).where(Tag.name.in_(tag_names))).scalars().all()
        existing = {t.name: t for t in rows}
        for name in tag_names:
            if name not in existing:
                tag = Tag(name=name)
                db.add(tag)
                db.flush()
                existing[name] = tag

    db.execute(
        AudioTag.__table__.delete().where(AudioTag.audio_id == audio.id)
    )
    for name in tag_names:
        db.add(AudioTag(audio_id=audio.id, tag_id=existing[name].id))


@router.put("/{audio_id}", response_model=AudioDetail)
def update_audio(
    audio_id: str,
    body: AudioUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("creator", "admin")),
) -> AudioDetail:
    try:
        parsed_id = uuid.UUID(audio_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    audio = db.execute(
        select(Audio).options(joinedload(Audio.creator)).where(Audio.id == parsed_id)
    ).scalar_one_or_none()
    if audio is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    if current_user.role.value != "admin" and audio.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "not your audio"},
        )

    if body.title is not None:
        audio.title = body.title
    if body.description is not None:
        audio.description = body.description
    if body.youtube_safe is not None:
        audio.youtube_safe = body.youtube_safe
    if body.is_public is not None:
        audio.is_public = body.is_public
    if body.tags is not None:
        _sync_tags(db, audio, body.tags)

    db.commit()
    db.refresh(audio)
    return _to_detail(audio)


@router.delete("/{audio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_audio(
    audio_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("creator", "admin")),
) -> None:
    try:
        parsed_id = uuid.UUID(audio_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    audio = db.execute(
        select(Audio).where(Audio.id == parsed_id)
    ).scalar_one_or_none()
    if audio is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    if current_user.role.value != "admin" and audio.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "not your audio"},
        )

    if audio.downloaded_by_user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "AUDIO_ALREADY_SOLD", "message": "cannot delete a sold audio"},
        )

    file_path = Path(audio.file_path)
    db.delete(audio)
    db.commit()

    if file_path.exists():
        file_path.unlink(missing_ok=True)


def _to_detail(audio: Audio) -> AudioDetail:
    return AudioDetail(
        id=str(audio.id),
        title=audio.title,
        creator=CreatorBrief(
            id=str(audio.creator.user_id),
            display_name=audio.creator.display_name,
        ),
        duration_sec=audio.duration_sec,
        token_cost=audio.duration_sec,
        peaks=audio.peaks,
        youtube_safe=audio.youtube_safe,
        published_at=audio.published_at,
        tags=[t.name for t in audio.tags],
        description=audio.description,
        sample_rate=audio.sample_rate,
        bit_depth=audio.bit_depth,
        channels=audio.channels,
        is_sold=audio.downloaded_by_user_id is not None,
        is_public=audio.is_public,
        downloaded_at=audio.downloaded_at,
        created_at=audio.created_at,
    )


@router.get("/{audio_id}", response_model=AudioDetail)
def get_audio(audio_id: str, db: Session = Depends(get_db)) -> AudioDetail:
    try:
        parsed_id = uuid.UUID(audio_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    audio = db.execute(
        select(Audio)
        .options(joinedload(Audio.creator))
        .where(Audio.id == parsed_id, Audio.is_public.is_(True))
    ).scalar_one_or_none()

    if audio is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    return _to_detail(audio)
