from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import auth_core
from app.db import connect_db

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

    prefix = u[0].upper()
    raw_id = u[1:]
    if not raw_id.isdigit():
        raise HTTPException(status_code=400, detail="工号格式错误，应为 M<数字> 或 D<数字> 或 admin")

    person_id = int(raw_id)

    if prefix not in {"M", "D"}:
        raise HTTPException(status_code=404, detail="工号不存在，请先用 admin 创建人员")

    conn = connect_db()
    try:
        cursor = conn.cursor()
        if prefix == "M":
            # 调度主管
            cursor.execute(
                "SELECT fleet_id, person_name AS display_name FROM Managers WHERE is_deleted = 0 AND person_id = %s",
                (person_id,),
            )
            cursor_row = cursor.fetchone()
            if cursor_row:
                token = auth_core.token_store.issue(
                    {"role": "manager", "personnel_id": person_id, "fleet_id": cursor_row["fleet_id"]}
                )
                return LoginResponse(
                    token=token,
                    role="manager",
                    personnel_id=person_id,
                    fleet_id=cursor_row["fleet_id"],
                    display_name=cursor_row["display_name"],
                )

        if prefix == "D":
            # 司机
            cursor.execute(
                "SELECT fleet_id, person_name AS display_name FROM Drivers WHERE is_deleted = 0 AND person_id = %s",
                (person_id,),
            )
            cursor_row = cursor.fetchone()
            if cursor_row:
                token = auth_core.token_store.issue(
                    {"role": "staff", "personnel_id": person_id, "fleet_id": cursor_row["fleet_id"]}
                )
                return LoginResponse(
                    token=token,
                    role="staff",
                    personnel_id=person_id,
                    fleet_id=cursor_row["fleet_id"],
                    display_name=cursor_row["display_name"],
                )

        raise HTTPException(status_code=404, detail="工号不存在或已被删除")
    finally:
        conn.close()
