from datetime import date

from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel

from app.db import get_db
from app.auth_core import require_admin_or_manager, require_admin_manager_or_driver_self

router = APIRouter()


class Incident(BaseModel):
    incident_id: int
    driver_id: str
    vehicle_id: str
    timestamp: date
    type: str
    fine_amount: float
    description: str
    status: str


class IncidentCreate(BaseModel):
    driver_id: str
    vehicle_id: str
    timestamp: date
    type: str
    fine_amount: float
    description: str
    status: str


class IncidentUpdate(BaseModel):
    driver_id: int | None = None
    vehicle_id: str | None = None
    timestamp: date | None = None
    type: str | None = None
    fine_amount: float | None = None
    description: str | None = None
    status: str | None = None


class IncidentSelect(BaseModel):
    data: list[Incident]
    total: int


@router.post("/api/incidents", status_code=status.HTTP_201_CREATED)
def insert_incident(
    incident: IncidentCreate,
    auth_info=Depends(require_admin_or_manager),
    conn=Depends(get_db),
):
    try:
        if auth_info.get("role") == "manager":
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM Vehicles WHERE vehicle_id = %s AND fleet_id = %s AND is_deleted = 0",
                (incident.vehicle_id, auth_info.get("fleet_id")),
            )
            if cursor.fetchone() is None:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该车辆不属于你管理的车队")

            cursor.execute(
                "SELECT 1 FROM Drivers WHERE person_id = %s AND fleet_id = %s AND is_deleted = 0",
                (incident.driver_id.lstrip("D").lstrip("d"), auth_info.get("fleet_id")),
            )
            if cursor.fetchone() is None:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该司机不属于你管理的车队")

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Incidents (vehicle_id, driver_id, incident_type, fine_amount, handle_status, occurrence_time) VALUES (%s, %s, %s, %s, %s, %s);",
            (incident.vehicle_id, incident.driver_id.lstrip("D").lstrip("d"), incident.type, incident.fine_amount, incident.status, incident.timestamp),
        )
        cursor.execute("SELECT SCOPE_IDENTITY() AS incident_id;")
        incident_id = int(cursor.fetchone()["incident_id"])
        conn.commit()
        return {"detail": "异常记录创建成功", "incident_id": incident_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="创建异常记录失败") from e


@router.patch("/api/incidents/{incident_id}")
def update_incident(
    incident_id: int,
    updates: IncidentUpdate,
    auth_info=Depends(require_admin_or_manager),
    conn=Depends(get_db),
):
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        return {"detail": "没有提供更新内容"}

    try:
        cursor = conn.cursor()

        if auth_info.get("role") == "manager":
            cursor.execute(
                "SELECT 1 FROM Incidents i JOIN Vehicles v ON i.vehicle_id = v.vehicle_id "
                "WHERE i.incident_id = %s AND i.is_deleted = 0 AND v.is_deleted = 0 AND v.fleet_id = %s",
                (incident_id, auth_info.get("fleet_id")),
            )
            if cursor.fetchone() is None:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该异常记录")

        if "driver_id" in update_data and update_data["driver_id"] is not None:
            # 允许传 D<数字> 或纯数字
            raw = str(update_data["driver_id"]).lstrip("D").lstrip("d")
            update_data["driver_id"] = int(raw) if raw.isdigit() else update_data["driver_id"]

        set_clause = ", ".join(f"{k} = %s" for k in update_data)
        values = list(update_data.values()) + [incident_id]
        cursor.execute(
            f"UPDATE Incidents SET {set_clause} WHERE incident_id = %s AND is_deleted = 0",
            values,
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到异常记录")
        conn.commit()
        return {"detail": "异常记录更新成功"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="更新异常记录失败") from e


@router.get("/api/incidents", response_model=IncidentSelect)
def list_incidents(
    limit: int = Query(10, ge=1),
    offset: int = Query(0, ge=0),
    auth_info=Depends(require_admin_or_manager),
    conn=Depends(get_db),
):
    cursor = conn.cursor()

    if auth_info.get("role") == "manager":
        cursor.execute(
            "SELECT COUNT(*) AS total FROM Incidents i JOIN Vehicles v ON i.vehicle_id = v.vehicle_id "
            "WHERE i.is_deleted = 0 AND v.is_deleted = 0 AND v.fleet_id = %s",
            (auth_info.get("fleet_id"),),
        )
        total = cursor.fetchone()["total"]
        cursor.execute(
            "SELECT i.incident_id, i.driver_id, i.vehicle_id, i.occurrence_time AS timestamp, i.incident_type AS type, "
            "i.fine_amount, i.description, i.handle_status AS status "
            "FROM Incidents i JOIN Vehicles v ON i.vehicle_id = v.vehicle_id "
            "WHERE i.is_deleted = 0 AND v.is_deleted = 0 AND v.fleet_id = %s "
            "ORDER BY i.incident_id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            (auth_info.get("fleet_id"), offset, limit),
        )
    else:
        cursor.execute("SELECT COUNT(*) AS total FROM Incidents WHERE is_deleted = 0")
        total = cursor.fetchone()["total"]
        cursor.execute(
            "SELECT incident_id, driver_id, vehicle_id, occurrence_time AS timestamp, incident_type AS type, fine_amount, description, handle_status AS status "
            "FROM Incidents WHERE is_deleted = 0 ORDER BY incident_id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            (offset, limit),
        )

    rows = cursor.fetchall()
    data = [Incident(**r) for r in rows]
    return IncidentSelect(data=data, total=total)


@router.delete("/api/incidents/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_incident(
    incident_id: int,
    auth_info=Depends(require_admin_or_manager),
    conn=Depends(get_db),
):
    try:
        cursor = conn.cursor()

        if auth_info.get("role") == "manager":
            cursor.execute(
                "SELECT 1 FROM Incidents i JOIN Vehicles v ON i.vehicle_id = v.vehicle_id "
                "WHERE i.incident_id = %s AND i.is_deleted = 0 AND v.is_deleted = 0 AND v.fleet_id = %s",
                (incident_id, auth_info.get("fleet_id")),
            )
            if cursor.fetchone() is None:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除该异常记录")

        cursor.execute("UPDATE Incidents SET is_deleted = 1 WHERE incident_id = %s AND is_deleted = 0", (incident_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到异常记录")
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="删除异常记录失败") from e


@router.get("/api/drivers/{person_id}/incidents", response_model=IncidentSelect)
def get_driver_incidents(
    person_id: int,
    start: str | None = Query(None), # 起始日期YYYY-MM-DD
    end: str | None = Query(None), # 结束日期YYYY-MM-DD
    limit: int = Query(10, ge=1),
    offset: int = Query(0, ge=0),
    auth_info=Depends(require_admin_manager_or_driver_self),
    conn=Depends(get_db)
):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) AS total FROM Incidents WHERE driver_id = %s AND is_deleted = 0"
        + (" AND occurrence_time >= %s" if start else "")
        + (" AND occurrence_time <= %s" if end else ""),
        tuple(
            arg
            for arg in [person_id, start, end]
            if arg is not None
        ),
    )
    total = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT incident_id, driver_id, vehicle_id, occurrence_time AS timestamp, incident_type AS type, fine_amount, description, handle_status AS status FROM Incidents WHERE driver_id = %s AND is_deleted = 0"
        + (" AND occurrence_time >= %s" if start else "")
        + (" AND occurrence_time <= %s" if end else "")
        + " ORDER BY incident_id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
        tuple(
            arg
            for arg in [person_id, start, end, offset, limit]
            if arg is not None
        ),
    )
    rows = cursor.fetchall()
    data = [Incident(**r) for r in rows]

    return IncidentSelect(data=data, total=total)