import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional
from fastapi import Request, HTTPException, status, Depends
from ..config import Settings


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_decode(data: str) -> bytes:
    padding = "=" * (4 - (len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_admin_token(username: str, secret_key: str, expires_in_seconds: int = 86400 * 14, claims: Optional[dict] = None) -> str:
    """Creates a cryptographically signed HMAC-SHA256 bearer token with expiration."""
    payload = {
        "sub": username,
        "exp": int(time.time()) + expires_in_seconds,
        "iat": int(time.time()),
        "nonce": secrets.token_hex(8),
    }
    if claims:
        payload.update({key: value for key, value in claims.items() if key not in ("sub", "exp", "iat", "nonce")})
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = _b64_encode(payload_bytes)

    sig = hmac.new(secret_key.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = _b64_encode(sig)

    return f"{payload_b64}.{sig_b64}"


def verify_admin_token(token: str, secret_key: str) -> Optional[dict]:
    """Verifies HMAC-SHA256 signature and validates expiration."""
    if not token or "." not in token:
        return None

    try:
        payload_b64, sig_b64 = token.split(".", 1)
        expected_sig = hmac.new(secret_key.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
        actual_sig = _b64_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload_bytes = _b64_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        if payload.get("exp", 0) < time.time():
            return None

        return payload
    except Exception:
        return None
def hash_password(password: str, iterations: int = 600000) -> str:
    """Hashes a password using PBKDF2-HMAC-SHA256 with a 16-byte random salt (OWASP standard)."""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    # Uses ':' delimiter so the string has zero '$' characters and is 100% safe in .env files & shell scripts
    return f"pbkdf2:sha256:{iterations}:{salt.hex()}:{dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verifies a raw password against an OWASP PBKDF2-HMAC-SHA256 hash.
    Supports both shell-safe ':' delimiter and standard '$' delimiter.
    Falls back gracefully to constant-time comparison if a raw password was passed in env.
    """
    if not password or not stored_hash:
        return False

    if stored_hash.startswith("pbkdf2:sha256:"):
        try:
            if "$" in stored_hash:
                parts = stored_hash.split("$")
                algo_iter = parts[0].split(":")
                iterations = int(algo_iter[2])
                salt = bytes.fromhex(parts[1])
                expected_dk = bytes.fromhex(parts[2])
            else:
                parts = stored_hash.split(":")
                iterations = int(parts[2])
                salt = bytes.fromhex(parts[3])
                expected_dk = bytes.fromhex(parts[4])

            actual_dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
            return secrets.compare_digest(actual_dk, expected_dk)
        except Exception:
            return False

    # Fallback for plain string if raw password was provided via environment variable
    return secrets.compare_digest(password.encode("utf-8"), stored_hash.encode("utf-8"))

def verify_credentials(username: str, password: str, settings: Settings) -> bool:
    """Verifies username and checks password against salted PBKDF2 hash."""
    if not secrets.compare_digest(username.strip().encode("utf-8"), settings.admin_username.encode("utf-8")):
        return False
    return verify_password(password.strip(), settings.admin_password_hash)


def extract_token(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if authorization:
        return authorization[7:].strip() if authorization.startswith("Bearer ") else ""
    return request.cookies.get("admin_token", "").strip()


def get_users_directory(request: Request):
    from .users_auth import UsersDirectory
    directory = getattr(request.app.state, "users_directory", None)
    if directory is None:
        directory = UsersDirectory(Settings.load())
        request.app.state.users_directory = directory
    return directory


def require_admin(request: Request) -> dict:
    """Authenticate dashboard readers; Users permissions are loaded server-side on every session check."""
    from .users_auth import UsersUnavailable
    settings = Settings.load()
    payload = verify_admin_token(extract_token(request), settings.auth_secret_key)
    if not payload:
        raise HTTPException(status_code=401, detail="Sign in to view this data.", headers={"WWW-Authenticate": "Bearer"})
    if settings.auth_source == "users":
        if payload.get("auth_source") != "users":
            raise HTTPException(status_code=401, detail="Please sign in with your Users-sheet account.")
        try:
            user = get_users_directory(request).validate(payload)
        except UsersUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error))
        if not user:
            raise HTTPException(status_code=401, detail="Your account or access changed. Please sign in again.")
        principal = user.principal()
    elif settings.auth_source == "env":
        principal = {"sub": payload["sub"], "username": payload["sub"], "role": "admin", "allowed_sources": None, "all_sources": True, "branch": "", "tele_id": "", "auth_source": "env"}
    else:
        raise HTTPException(status_code=503, detail="Login is not configured.")
    request.state.principal = principal
    return principal


def require_all_sources(principal: dict = Depends(require_admin)) -> dict:
    if not principal.get("all_sources"):
        raise HTTPException(status_code=403, detail="This operation requires access to all sources.")
    return principal


def require_operations_admin(principal: dict = Depends(require_all_sources)) -> dict:
    if principal.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only an administrator can change platform data.")
    return principal
