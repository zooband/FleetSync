import uuid
from typing import Any

from fastapi import Request


class TokenStore:
    def __init__(self):
        self._store: dict[str, dict[str, Any]] = {}

    def issue(self, session: dict[str, Any]) -> str:
        token = uuid.uuid4().hex
        self._store[token] = session
        return token

    def get(self, token: str) -> dict[str, Any] | None:
        return self._store.get(token)


token_store = TokenStore()


def parse_bearer_token(auth_header: str | None) -> str | None:
    if not auth_header:
        return None
    parts = auth_header.split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, token = parts[0].strip(), parts[1].strip()
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def _extract_int_segment(path: str, idx: int) -> int | None:
    segs = path.split("/")
    if len(segs) <= idx:
        return None
    raw = segs[idx]
    if not raw.isdigit():
        return None
    return int(raw)


def is_allowed(path: str, session: dict[str, Any]) -> bool:
    role = session.get("role")

    if role == "admin":
        return True

    if role == "staff":
        if path.startswith("/api/personnels/"):
            pid = _extract_int_segment(path, 3)
            return pid is not None and pid == session.get("personnel_id")
        return False

    if role == "manager":
        if path.startswith("/api/fleets/"):
            fid = _extract_int_segment(path, 3)
            return fid is not None and fid == session.get("fleet_id")

        if path.startswith("/api/personnels/drivers") or path.startswith("/api/personnels/managers"):
            return True

        if path.startswith("/api/personnels/"):
            pid = _extract_int_segment(path, 3)
            return pid is not None and pid == session.get("personnel_id")
        if path.startswith("/api/orders"):
            return True
        if path.startswith("/api/incidents"):
            return True
        if path.startswith("/api/vehicles"):
            return True
        return False

    return False


async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/") or request.method == "OPTIONS":
        return await call_next(request)

    if path == "/api/auth/login":
        return await call_next(request)

    token = parse_bearer_token(request.headers.get("Authorization"))
    if not token:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

    session = token_store.get(token)
    if not session:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=401, content={"detail": "Invalid token"})

    if not is_allowed(path, session):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    request.state.auth = session
    return await call_next(request)
