from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel

from app.auth_core import require_admin, require_admin_or_fleet_manager
from app.db import get_db

router = APIRouter()

class Fleet(BaseModel):
    fleet_id: int
    fleet_name: str
    manager_id: str
    center_id: int
    manager_name: str
    manager_contact: str | None = None

class FleetCreate(BaseModel):
    fleet_name: str
    manager_name: str
    manager_contact: str | None = None

class FleetSelect(BaseModel):
    data: list[Fleet]
    total: int


class FleetUpdate(BaseModel):
    fleet_name: str | None = None


class FleetMonthlyReport(BaseModel):
    orders: int
    incidents: int
    fines: float


@router.get("/api/distribution-centers/{center_id}/fleets")
def get_center_fleets(center_id: int, limit: int = Query(10, ge=1), offset: int = Query(0, ge=0), auth_info=Depends(require_admin), conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM Fleets WHERE center_id = %s AND is_deleted = 0", (center_id,))
    total = cursor.fetchone()["total"]

    cursor.execute("SELECT f.fleet_id, f.fleet_name, 'M' + CAST(m.person_id AS VARCHAR) AS manager_id, m.person_name AS manager_name, m.person_contact AS manager_contact, f.center_id FROM Fleets f JOIN Managers m ON f.fleet_id = m.fleet_id WHERE f.center_id = %s AND f.is_deleted = 0 ORDER BY fleet_id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY", (center_id, offset, limit))
    rows = cursor.fetchall()
    data = [Fleet(**r) for r in rows]

    return FleetSelect(data=data, total=total)


@router.post("/api/distribution-centers/{center_id}/fleets", status_code=status.HTTP_201_CREATED)
def insert_fleet(center_id: int, fleet: FleetCreate, auth_info=Depends(require_admin), conn=Depends(get_db)):
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Fleets (fleet_name, center_id) VALUES (%s, %s);", (fleet.fleet_name, center_id))
        cursor.execute("SELECT SCOPE_IDENTITY() AS fleet_id;")
        fleet_id = int(cursor.fetchone()["fleet_id"])
        cursor.execute("INSERT INTO Managers (person_name, person_contact, fleet_id) VALUES (%s, %s, %s);", (fleet.manager_name, fleet.manager_contact, fleet_id))
        cursor.execute("SELECT SCOPE_IDENTITY() AS manager_id;")
        manager_id = int(cursor.fetchone()["manager_id"])
        conn.commit()
        return {"detail": "车队和调度主管创建成功", "fleet_id": fleet_id, "manager_id": manager_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="创建车队失败") from e

@router.get("/api/fleets/{fleet_id}", response_model=Fleet)
def get_fleet_detail(
    fleet_id: int,
    auth_info=Depends(require_admin_or_fleet_manager),
    conn=Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute("SELECT f.fleet_id, f.fleet_name, 'M' + CAST(m.person_id AS VARCHAR) AS manager_id, m.person_name AS manager_name, m.person_contact AS manager_contact, f.center_id FROM Fleets f JOIN Managers m ON f.fleet_id = m.fleet_id WHERE f.fleet_id = %s AND f.is_deleted = 0", (fleet_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到车队记录")
    return Fleet(**row)


@router.patch("/api/fleets/{fleet_id}", status_code=status.HTTP_200_OK)
def update_fleet(fleet_id: int, updates: FleetUpdate, auth_info=Depends(require_admin), conn=Depends(get_db)):
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        return {"detail": "没有提供更新内容"}
    
    try:
        cursor = conn.cursor()
        set_clause = ", ".join(f"{k} = %s" for k in update_data)
        values = list(update_data.values()) + [fleet_id]
        cursor.execute(
            f"UPDATE Fleets SET {set_clause} WHERE fleet_id = %s AND is_deleted = 0",
            values,
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到车队记录")
        conn.commit()
        return {"detail": "车队信息更新成功"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="更新车队失败") from e


class FleetManagerUpdate(BaseModel):
    fleet_name: str | None = None
    manager_name: str | None = None
    manager_contact: str | None = None

@router.patch("/api/fleets/{fleet_id}/manager/{manager_id}", status_code=status.HTTP_200_OK)
def update_fleet_manager(fleet_id: int, manager_id: str, updates: FleetManagerUpdate, auth_info=Depends(require_admin), conn=Depends(get_db)):
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        return {"detail": "没有提供更新内容"}
    
    try:
        cursor = conn.cursor()
        if "fleet_name" in update_data:
            cursor.execute(
                "UPDATE Fleets SET fleet_name = %s WHERE fleet_id = %s AND is_deleted = 0",
                (update_data["fleet_name"], fleet_id),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到车队记录")
            del update_data["fleet_name"]
        if update_data:
            update_data_manager = {}
            if "manager_name" in update_data:
                update_data_manager["person_name"] = update_data["manager_name"]
            if "manager_contact" in update_data:
                update_data_manager["person_contact"] = update_data["manager_contact"]
            set_clause = ", ".join(f"{k} = %s" for k in update_data_manager)
            values = list(update_data_manager.values()) + [manager_id[1:]]
            cursor.execute(
                f"UPDATE Managers SET {set_clause} WHERE person_id = %s AND is_deleted = 0",
                values,
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到主管记录")
        conn.commit()
        return {"detail": "车队信息和主管信息更新成功"}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"更新车队信息和主管信息失败: {e}") from e






@router.get("/api/fleets/{fleet_id}/reports/monthly", response_model=FleetMonthlyReport)
def get_fleet_monthly_report(fleet_id: int, month: str | None = Query(None)):
    # TODO: 实现接口
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="该接口尚未实现")
    # m = (month or datetime.now().strftime("%Y-%m")).strip()
    # try:
    #     base = datetime.strptime(m, "%Y-%m")
    # except ValueError:
    #     raise HTTPException(status_code=422, detail="month 格式应为 YYYY-MM")

    # start_d = date(base.year, base.month, 1)
    # end_d = date(base.year + 1, 1, 1) if base.month == 12 else date(base.year, base.month + 1, 1)

    # fleet_vehicle_ids = {v.vehicle_id for v in store.vehicles_db if v.fleet_id == fleet_id}

    # month_orders: list[schemas.Order] = []
    # for o in store.orders_db:
    #     if o.vehicle_id is None or o.vehicle_id not in fleet_vehicle_ids:
    #         continue
    #     if o.status != "已完成":
    #         continue
    #     d = getattr(o, "completed_at", None) or getattr(o, "created_at", None)
    #     if d is None:
    #         continue
    #     if start_d <= d < end_d:
    #         month_orders.append(o)
    # month_incidents = [i for i in store.incidents_db if i.vehicle_id in fleet_vehicle_ids and start_d <= i.timestamp < end_d]
    # fines = sum((i.fine_amount or 0.0) for i in month_incidents)

    # return FleetMonthlyReport(orders=len(month_orders), incidents=len(month_incidents), fines=float(fines))


@router.delete("/api/fleets/{fleet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fleet(fleet_id: int, auth_info=Depends(require_admin), conn=Depends(get_db)):
    cursor = conn.cursor(as_dict=False)
    cursor.execute("SELECT 1 FROM DistributionCenters WHERE fleet_id = %s AND is_deleted = 0", (fleet_id,))
    if cursor.fetchone() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"找不到ID为 {fleet_id} 的车队")
    try:
        cursor.execute("UPDATE Fleets SET is_deleted = 1 WHERE fleet_id = %s AND is_deleted = 0", (fleet_id,))
        cursor.execute("UPDATE v SET v.is_deleted = 1 FROM Vehicles v JOIN Fleets f ON v.fleet_id = f.fleet_id WHERE f.fleet_id = %s AND v.is_deleted = 0", (fleet_id,))
        cursor.execute("UPDATE d SET d.is_deleted = 1 FROM Drivers d JOIN Fleets f ON d.fleet_id = f.fleet_id WHERE f.fleet_id = %s AND d.is_deleted = 0", (fleet_id,))
        cursor.execute("UPDATE m SET m.is_deleted = 1 FROM Managers m JOIN Fleets f ON m.fleet_id = f.fleet_id WHERE f.fleet_id = %s AND m.is_deleted = 0", (fleet_id,))
        conn.commit()
        return {"detail": "车队删除成功"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="删除车队时发生错误") from e