from typing import List, Optional
from fastapi import APIRouter, HTTPException, Response, Request, Depends
from pydantic import BaseModel, Field
from ..config import Settings
from ..core.auth import (
    verify_credentials, create_admin_token, verify_admin_token, require_admin,
    get_users_directory, extract_token,
)
from ..core.users_auth import UsersUnavailable

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    # Used only by explicit legacy env authentication; Users login needs password alone.
    username: str = Field(default="", max_length=200)
    password: str = Field(min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    token: str
    username: str
    expires_in: int
    role: str
    allowed_sources: Optional[List[str]] = None
    all_sources: bool
    branch: str = ""
    tele_id: str = ""


@router.post("/login", response_model=LoginResponse)
def login_admin(creds: LoginRequest, response: Response, request: Request):
    settings = Settings.load()
    if settings.auth_source == "users":
        try:
            directory = get_users_directory(request)
            user, throttled = directory.authenticate(creds.password, request.client.host if request.client else "unknown")
        except UsersUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error))
        if throttled:
            raise HTTPException(status_code=429, detail="Too many sign-in attempts. Please wait a few minutes.", headers={"Retry-After": "300"})
        if not user:
            raise HTTPException(status_code=401, detail="Password not accepted. Use a unique password from an active Users account.")
        principal = user.principal()
        subject = user.key
        claims = {"auth_source": "users", "users_version": user.version}
    elif settings.auth_source == "env" and verify_credentials(creds.username, creds.password, settings):
        principal = {"username": settings.admin_username, "role": "admin", "allowed_sources": None, "all_sources": True, "branch": "", "tele_id": ""}
        subject, claims = settings.admin_username, {"auth_source": "env"}
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    expires_in = settings.session_seconds
    token = create_admin_token(subject, settings.auth_secret_key, expires_in, claims)
    response.set_cookie(key="admin_token", value=token, max_age=expires_in,
                        httponly=True, samesite="lax", secure=request.url.scheme == "https")
    return LoginResponse(token=token, expires_in=expires_in, **{key: principal[key] for key in ("username", "role", "allowed_sources", "all_sources", "branch", "tele_id")})


@router.get("/me")
def get_current_admin_info(principal: dict = Depends(require_admin)):
    return {"authenticated": True, **{key: principal.get(key) for key in ("username", "role", "allowed_sources", "all_sources", "branch", "tele_id")}}


@router.post("/logout")
def logout_admin(response: Response, request: Request):
    settings = Settings.load()
    payload = verify_admin_token(extract_token(request), settings.auth_secret_key)
    if payload and payload.get("auth_source") == "users":
        get_users_directory(request).revoke(payload)
    response.delete_cookie(key="admin_token")
    return {"message": "Logged out successfully."}
