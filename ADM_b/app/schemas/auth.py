from datetime import datetime

from pydantic import BaseModel, Field


class ActivateJsonRequest(BaseModel):
    lic: str = Field(..., min_length=1, description="raw lic file content (JSON or KV)")


class UserOut(BaseModel):
    id: str
    username: str
    role: str
    license_code: str
    monthly_quota_tokens: int


class ActivateResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut
