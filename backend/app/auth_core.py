import uuid
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import HTTPException

from app.db import get_db
from fastapi import Depends


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
        # 司机仅允许查询自己的绩效与个人相关信息
        if path.startswith("/api/personnels/"):
            pid = _extract_int_segment(path, 3)
            return pid is not None and pid == session.get("personnel_id")

        if path.startswith("/api/drivers/"):
            # /api/drivers/{person_id}/orders 或 /api/drivers/{person_id}/incidents
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

        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "Not authenticated"})

    session = token_store.get(token)
    if not session:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "Invalid token"})

    if not is_allowed(path, session):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": "Forbidden"})

    request.state.auth = session
    return await call_next(request)


def require_admin(request: Request):
    auth_info = getattr(request.state, "auth", None)
    if auth_info is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="身份验证失败，请提供有效的凭据")
    if auth_info.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足，需要管理员权限")
    return auth_info


def require_authenticated(request: Request) -> dict[str, Any]:
    auth_info = getattr(request.state, "auth", None)
    if auth_info is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="身份验证失败，请提供有效的凭据")
    return auth_info


def require_admin_or_manager(auth_info: dict[str, Any] = Depends(require_authenticated)) -> dict[str, Any]:
    if auth_info.get("role") in {"admin", "manager"}:
        return auth_info
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足，需要管理员或调度主管权限")


def require_admin_or_fleet_manager(
    fleet_id: int,
    auth_info: dict[str, Any] = Depends(require_authenticated),
) -> dict[str, Any]:
    if auth_info.get("role") == "admin":
        return auth_info
    if auth_info.get("role") == "manager" and auth_info.get("fleet_id") == fleet_id:
        return auth_info
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足，仅允许管理员或该车队调度主管访问")


def require_admin_or_manager_self(
    person_id: str,
    auth_info: dict[str, Any] = Depends(require_authenticated),
) -> dict[str, Any]:
    if auth_info.get("role") == "admin":
        return auth_info

    raw = person_id.lstrip("M").lstrip("m")
    if raw.isdigit() and auth_info.get("role") == "manager" and auth_info.get("personnel_id") == int(raw):
        return auth_info
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足，仅允许管理员或本人访问")


def _parse_prefixed_person_id(value: str, prefix: str) -> int | None:
    v = value.strip()
    if not v:
        return None
    if v[0].upper() != prefix.upper():
        return None
    rest = v[1:]
    if not rest.isdigit():
        return None
    return int(rest)


def require_admin_manager_or_driver_self(
    person_id: str,
    auth_info: dict[str, Any] = Depends(require_authenticated),
    conn=Depends(get_db),
) -> dict[str, Any]:
    role = auth_info.get("role")
    if role == "admin":
        return auth_info

    if role == "staff" and auth_info.get("personnel_id") == person_id:
        return auth_info

    if role == "manager":
        cursor = conn.cursor()
        cursor.execute(
            "SELECT fleet_id FROM Drivers WHERE is_deleted = 0 AND person_id = %s",
            (person_id,),
        )
        row = cursor.fetchone()
        if row and row.get("fleet_id") == auth_info.get("fleet_id"):
            return auth_info

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="权限不足，仅允许管理员、该车队调度主管或司机本人访问",
    )


def require_admin_or_vehicle_fleet_manager(
    vehicle_id: str,
    auth_info: dict[str, Any] = Depends(require_authenticated),
    conn=Depends(get_db),
) -> dict[str, Any]:
    if auth_info.get("role") == "admin":
        return auth_info

    if auth_info.get("role") != "manager":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足，仅允许管理员或调度主管访问")

    cursor = conn.cursor()
    cursor.execute(
        "SELECT fleet_id FROM Vehicles WHERE vehicle_id = %s AND is_deleted = 0",
        (vehicle_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到车辆记录")
    if row.get("fleet_id") != auth_info.get("fleet_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足，仅允许该车辆所属车队调度主管访问")
    return auth_info
