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
    occurrence_time: date
    incident_type: str
    fine_amount: float
    incident_description: str
    handle_status: str


class IncidentCreate(BaseModel):
    driver_id: str
    vehicle_id: str
    occurrence_time: date
    incident_type: str
    fine_amount: float
    incident_description: str
    handle_status: str


class IncidentUpdate(BaseModel):
    driver_id: str | None = None
    vehicle_id: str | None = None
    occurrence_time: date | None = None
    incident_type: str | None = None
    fine_amount: float | None = None
    incident_description: str | None = None
    handle_status: str | None = None


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
            cursor = conn.cursor(as_dict=False)
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
            "INSERT INTO Incidents (vehicle_id, driver_id, incident_type, fine_amount, incident_description, handle_status, occurrence_time) VALUES (%s, %s, %s, %s, %s, %s, %s);",
            (
                incident.vehicle_id,
                incident.driver_id.lstrip("D").lstrip("d"),
                incident.incident_type,
                incident.fine_amount,
                incident.incident_description,
                incident.handle_status,
                incident.occurrence_time,
            ),
        )
        cursor.execute("SELECT SCOPE_IDENTITY() AS incident_id;")
        incident_id = int(cursor.fetchone()["incident_id"])
        conn.commit()
        return {"detail": "异常记录创建成功", "incident_id": incident_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"创建异常记录失败: {e}") from e


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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"更新异常记录失败: {e}") from e


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
            "SELECT i.incident_id, 'D' + CAST(i.driver_id AS NVARCHAR) AS driver_id, i.vehicle_id, i.occurrence_time, i.incident_type, "
            "i.fine_amount, i.incident_description, i.handle_status AS handle_status "
            "FROM Incidents i JOIN Vehicles v ON i.vehicle_id = v.vehicle_id "
            "WHERE i.is_deleted = 0 AND v.is_deleted = 0 AND v.fleet_id = %s "
            "ORDER BY i.incident_id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            (auth_info.get("fleet_id"), offset, limit),
        )
    else:
        cursor.execute("SELECT COUNT(*) AS total FROM Incidents WHERE is_deleted = 0")
        total = cursor.fetchone()["total"]
        cursor.execute(
            "SELECT incident_id, 'D' + CAST(driver_id AS NVARCHAR) AS driver_id, vehicle_id, occurrence_time, incident_type, fine_amount, incident_description, handle_status "
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
        cursor = conn.cursor(as_dict=False)

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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"删除异常记录失败: {e}") from e


@router.get("/api/drivers/{person_id}/incidents", response_model=IncidentSelect)
def get_driver_incidents(
    person_id: str,
    start: str | None = Query(None),
    end: str | None = Query(None),
    limit: int = Query(10, ge=1),
    offset: int = Query(0, ge=0),
    auth_info=Depends(require_admin_manager_or_driver_self),
    conn=Depends(get_db)
):
    cursor = conn.cursor(as_dict=True)
    driver_id = person_id.lstrip("D")

    # 构建 WHERE 条件和参数
    where_clauses = ["driver_id = %s", "is_deleted = 0"]
    params = [driver_id]

    if start:
        where_clauses.append("occurrence_time >= %s")
        params.append(start)
    if end:
        where_clauses.append("occurrence_time <= %s")
        params.append(end)

    where_sql = " AND ".join(where_clauses)

    # COUNT 查询
    cursor.execute(f"SELECT COUNT(*) AS total FROM Incidents WHERE {where_sql}", params)
    total = cursor.fetchone()["total"]

    # 分页查询：注意 offset 和 limit 必须是最后两个参数
    params_with_pagination = params + [offset, limit]
    cursor.execute(
        f"""
        SELECT incident_id, 'D' + CAST(driver_id AS NVARCHAR) AS driver_id, vehicle_id, 
               occurrence_time, 
               incident_type, 
               fine_amount, 
               incident_description, 
               handle_status
        FROM Incidents 
        WHERE {where_sql}
        ORDER BY incident_id 
        OFFSET %s ROWS FETCH NEXT %s ROWS ONLY
        """,
        params_with_pagination
    )
    rows = cursor.fetchall()
    data = [Incident(**r) for r in rows]

    return IncidentSelect(data=data, total=total)