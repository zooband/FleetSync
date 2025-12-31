from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel

from app.auth_core import require_admin, require_admin_or_manager_self
from app.db import get_db

router = APIRouter()


class Manager(BaseModel):
    person_id: str
    person_name: str
    person_contact: str | None = None
    fleet_id: int


class ManagerSelect(BaseModel):
    data: list[Manager]
    total: int


class ManagerUpdate(BaseModel):
    person_name: str | None = None
    person_contact: str | None = None


@router.patch("/api/managers/{person_id}")
def update_manager(person_id: str, updates: ManagerUpdate, auth_info=Depends(require_admin), conn=Depends(get_db)):
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        return {"message": "没有提供更新内容"}
    try:
        cursor = conn.cursor()
        set_clause = ", ".join(f"{k} = %s" for k in update_data)
        update_values = list(update_data.values())
        cursor.execute(
            f"UPDATE Managers SET {set_clause} WHERE person_id = %s AND is_deleted = 0",
            update_values + [person_id.lstrip("M")],
        )
        conn.commit()
        return {"message": "调度主管信息更新成功"}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/managers/{person_id}", response_model=Manager)
def get_manager_info(
    person_id: str,
    auth_info=Depends(require_admin_or_manager_self),
    conn=Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 'M' + CAST(person_id AS NVARCHAR) AS person_id, person_name, person_contact, fleet_id FROM Managers WHERE person_id = %s AND is_deleted = 0",
        (person_id.lstrip("M"),),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到调度主管记录")
    return Manager(**row)
