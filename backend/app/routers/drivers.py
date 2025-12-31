from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from fastapi import Depends
from app.db import get_db
from app.auth_core import require_admin, require_admin_or_fleet_manager

router = APIRouter()


class Driver(BaseModel):
    person_id: str
    person_name: str
    person_contact: str | None = None
    driver_license: str
    driver_status: str
    fleet_id: int


class DriverUpdate(BaseModel):
    driver_name: str | None = None
    driver_contact: str | None = None
    driver_license: str | None = None
    driver_status: str | None = None


class DriverCreate(BaseModel):
    person_name: str
    person_contact: str | None = None
    driver_license: str


class DriversSelect(BaseModel):
    data: list[Driver]
    total: int


@router.post("/api/fleets/{fleet_id}/drivers", status_code=status.HTTP_201_CREATED)
def insert_driver(fleet_id: int, payload: DriverCreate, auth_info=Depends(require_admin), conn=Depends(get_db)):
    cursor = conn.cursor(as_dict=False)
    cursor.execute("SELECT 1 FROM Fleets WHERE fleet_id = %s AND is_deleted = 0", (fleet_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"找不到ID为{fleet_id}的车队")

    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Drivers (person_name, person_contact, driver_license, fleet_id) VALUES (%s, %s, %s, %s);", (payload.person_name, payload.person_contact, payload.driver_license, fleet_id)
        )
        cursor.execute("SELECT SCOPE_IDENTITY() AS driver_id;")
        driver_id = int(cursor.fetchone()["driver_id"])
        conn.commit()
        return {"detail": "司机创建成功", "fleet_id": fleet_id, "driver_id": f"D{driver_id}"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="创建司机失败") from e


@router.patch("/api/drivers/{driver_id}", response_model=Driver)
def update_driver(driver_id: str, updates: DriverUpdate, auth_info=Depends(require_admin), conn=Depends(get_db)):
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        return {"detail": "没有提供更新内容"}

    try:
        cursor = conn.cursor()

        set_clause = ", ".join(f"{k} = %s" for k in update_data)
        values = list(update_data.values()) + [driver_id[1:]]
        cursor.execute(
            f"UPDATE Drivers SET {set_clause} WHERE driver_id = %s AND is_deleted = 0",
            values,
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到司机记录")
        conn.commit()
        return {"detail": "司机信息更新成功"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="更新司机失败") from e


@router.delete("/api/drivers/{driver_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_driver(driver_id: str, auth_info=Depends(require_admin), conn=Depends(get_db)):
    cursor = conn.cursor(as_dict=False)
    cursor.execute("SELECT 1 FROM Drivers WHERE driver_id = %s AND is_deleted = 0", (driver_id,))
    if cursor.fetchone() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"找不到ID为 {driver_id} 的司机")
    try:
        cursor.execute("SELECT 1 FROM Assignments a JOIN Orders o ON a.vehicle_id = o.vehicle_id WHERE a.person_id = %s AND o.order_status = '运输中'", (driver_id[1:],))
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该司机有活跃运单，无法删除")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Assignments WHERE driver_id = %s", (driver_id[1:],))
        cursor.execute("UPDATE Drivers SET is_deleted = 1 WHERE driver_id = %s AND is_deleted = 0", (driver_id[1:],))
        conn.commit()
        return {"detail": "司机删除成功"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="删除司机时发生错误") from e


@router.get("/api/fleets/{fleet_id}/drivers", response_model=DriversSelect)
def list_fleet_drivers(
    fleet_id: int,
    q: str | None = Query(""),
    limit: int = Query(10, ge=1),
    offset: int = Query(0, ge=0),
    auth_info=Depends(require_admin_or_fleet_manager),
    conn=Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM Drivers WHERE fleet_id = %s AND is_deleted = 0 AND (person_name LIKE %s OR person_contact LIKE %s)", (fleet_id, f"%{q}%", f"%{q}%"))
    total = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT 'D' + CAST(person_id AS NVARCHAR) AS person_id, person_name, driver_license, driver_status, person_contact, fleet_id FROM Drivers WHERE fleet_id = %s AND is_deleted = 0 AND (person_name LIKE %s OR person_contact LIKE %s) ORDER BY person_id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
        (fleet_id, f"%{q}%", f"%{q}%", offset, limit),
    )
    rows = cursor.fetchall()
    data = [Driver(**r) for r in rows]
    return DriversSelect(data=data, total=total)
