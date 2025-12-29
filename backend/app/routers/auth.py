from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import auth_core, store

router = APIRouter()


class LoginRequest(BaseModel):
    username: str


class LoginResponse(BaseModel):
    token: str
    role: str  # 'admin' | 'manager' | 'staff'
    personnel_id: int | None = None
    fleet_id: int | None = None
    display_name: str | None = None


@router.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    u = payload.username.strip()
    if not u:
        raise HTTPException(status_code=400, detail="username 不能为空")

    if u.lower() == "admin":
        token = auth_core.token_store.issue({"role": "admin"})
        return LoginResponse(token=token, role="admin", personnel_id=None, fleet_id=None, display_name="admin")

    if not u.isdigit():
        raise HTTPException(status_code=400, detail="用户名只能是 admin 或 数字工号")
    pid = int(u)

    for m in store.managers_db:
        if getattr(m, "person_id", None) == pid:
            token = auth_core.token_store.issue({"role": "manager", "personnel_id": pid, "fleet_id": getattr(m, "fleet_id", None)})
            return LoginResponse(token=token, role="manager", personnel_id=pid, fleet_id=getattr(m, "fleet_id", None), display_name=getattr(m, "person_name", None))

    for d in store.drivers_db:
        if getattr(d, "person_id", None) == pid:
            token = auth_core.token_store.issue({"role": "staff", "personnel_id": pid})
            return LoginResponse(token=token, role="staff", personnel_id=pid, fleet_id=getattr(d, "fleet_id", None), display_name=getattr(d, "person_name", None))

    for p in store.personnel_db:
        if getattr(p, "person_id", None) == pid:
            token = auth_core.token_store.issue({"role": "staff", "personnel_id": pid})
            return LoginResponse(token=token, role="staff", personnel_id=pid, fleet_id=None, display_name=getattr(p, "person_name", None))

    raise HTTPException(status_code=404, detail="工号不存在，请先用 admin 创建人员")
