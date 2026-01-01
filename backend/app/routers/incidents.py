from datetime import date

from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel

from app.db import get_db
from app.auth_core import require_admin_or_manager, require_admin_manager_or_driver_self

router = APIRouter()


class DriverRef(BaseModel):
    person_id: str
    person_name: str


class Incident(BaseModel):
    incident_id: int
    # 兼容两种返回：
    # 1) 旧格式："D5"
    # 2) 新格式：{"person_id": "D5", "person_name": "斯基"}
    driver_id: str | DriverRef
    vehicle_id: str
    occurrence_time: date
    incident_type: str
    fine_amount: float
    incident_description: str
    handle_status: str


class IncidentCreate(BaseModel):
    vehicle_id: str
    # 说明：作业要求由后端自动推导司机/时间/类型/处理状态，因此创建时仅需传 vehicle_id
    incident_description: str | None = None
    fine_amount: float | None = None



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
        role = auth_info.get("role")
        cursor = conn.cursor()

        # 车辆必须存在且非异常状态
        cursor.execute(
            "SELECT vehicle_status, fleet_id FROM Vehicles WHERE vehicle_id = %s AND is_deleted = 0",
            (incident.vehicle_id,),
        )
        v = cursor.fetchone()
        if not v:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到车辆记录")

        vehicle_status = str(v.get("vehicle_status") or "")
        if vehicle_status == "异常":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="车辆处于异常状态，无法新增异常记录")

        # 车辆必须已分配司机（Assignments），且司机未被软删除
        cursor.execute(
            "SELECT a.person_id AS driver_id, d.fleet_id AS driver_fleet_id "
            "FROM Assignments a "
            "JOIN Drivers d ON a.person_id = d.person_id AND d.is_deleted = 0 "
            "WHERE a.vehicle_id = %s",
            (incident.vehicle_id,),
        )
        arow = cursor.fetchone()
        if not arow:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该车辆未分配司机，无法新增异常记录")

        # 调度主管：只能为自己车队内车辆新增异常（车辆和分配司机都必须属于该车队）
        if role == "manager":
            fleet_id = auth_info.get("fleet_id")
            if v.get("fleet_id") != fleet_id or arow.get("driver_fleet_id") != fleet_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该车辆不属于你管理的车队")

        driver_id = int(arow.get("driver_id"))
        incident_type = "运输中异常" if vehicle_status == "运输中" else "空闲时异常"
        occurrence_time = date.today()
        handle_status = "未处理"

        incident_description = (incident.incident_description or "").strip()
        fine_amount = float(incident.fine_amount) if incident.fine_amount is not None else 0.0

        # 由于表结构 incident_description NOT NULL，这里默认空字符串；fine_amount 默认 0
        cursor.execute(
            "INSERT INTO Incidents (vehicle_id, driver_id, incident_type, fine_amount, incident_description, handle_status, occurrence_time) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s);",
            (
                incident.vehicle_id,
                driver_id,
                incident_type,
                fine_amount,
                incident_description,
                handle_status,
                occurrence_time,
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

        # 作业要求：编辑仅允许把处理状态标记为“已处理”
        allowed_keys = {"handle_status"}
        extra = set(update_data.keys()) - allowed_keys
        if extra:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅允许更新异常处理状态")

        next_status = str(update_data.get("handle_status") or "").strip()
        if next_status != "已处理":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="handle_status 仅支持设置为 已处理")

        cursor.execute(
            "UPDATE Incidents SET handle_status = %s WHERE incident_id = %s AND is_deleted = 0",
            ("已处理", incident_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到异常记录")
        conn.commit()
        return {"detail": "异常记录更新成功"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"更新异常记录失败: {e}") from e


class VehicleOption(BaseModel):
    vehicle_id: str


class VehicleOptionSelect(BaseModel):
    data: list[VehicleOption]
    total: int


@router.get("/api/incidents/available-vehicles", response_model=VehicleOptionSelect)
def list_available_vehicles_for_incident(
    q: str | None = Query(""),
    limit: int = Query(10, ge=1),
    offset: int = Query(0, ge=0),
    auth_info=Depends(require_admin_or_manager),
    conn=Depends(get_db),
):
    """用于异常新增的车辆下拉：仅返回“非异常状态 + 已分配司机(Assignments)”的车辆。"""
    cursor = conn.cursor()

    keyword = (q or "").strip()
    like_kw = f"%{keyword}%"
    role = auth_info.get("role")

    if role == "manager":
        fleet_id = auth_info.get("fleet_id")
        cursor.execute(
            "SELECT COUNT(*) AS total "
            "FROM Vehicles v "
            "JOIN Assignments a ON v.vehicle_id = a.vehicle_id "
            "JOIN Drivers d ON a.person_id = d.person_id AND d.is_deleted = 0 "
            "WHERE v.is_deleted = 0 AND v.vehicle_status <> N'异常' "
            "AND v.fleet_id = %s AND d.fleet_id = %s "
            "AND v.vehicle_id LIKE %s",
            (fleet_id, fleet_id, like_kw),
        )
        total = cursor.fetchone()["total"]
        cursor.execute(
            "SELECT v.vehicle_id "
            "FROM Vehicles v "
            "JOIN Assignments a ON v.vehicle_id = a.vehicle_id "
            "JOIN Drivers d ON a.person_id = d.person_id AND d.is_deleted = 0 "
            "WHERE v.is_deleted = 0 AND v.vehicle_status <> N'异常' "
            "AND v.fleet_id = %s AND d.fleet_id = %s "
            "AND v.vehicle_id LIKE %s "
            "ORDER BY v.vehicle_id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            (fleet_id, fleet_id, like_kw, offset, limit),
        )
    else:
        cursor.execute(
            "SELECT COUNT(*) AS total "
            "FROM Vehicles v "
            "JOIN Assignments a ON v.vehicle_id = a.vehicle_id "
            "JOIN Drivers d ON a.person_id = d.person_id AND d.is_deleted = 0 "
            "WHERE v.is_deleted = 0 AND v.vehicle_status <> N'异常' AND v.vehicle_id LIKE %s",
            (like_kw,),
        )
        total = cursor.fetchone()["total"]
        cursor.execute(
            "SELECT v.vehicle_id "
            "FROM Vehicles v "
            "JOIN Assignments a ON v.vehicle_id = a.vehicle_id "
            "JOIN Drivers d ON a.person_id = d.person_id AND d.is_deleted = 0 "
            "WHERE v.is_deleted = 0 AND v.vehicle_status <> N'异常' AND v.vehicle_id LIKE %s "
            "ORDER BY v.vehicle_id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            (like_kw, offset, limit),
        )

    rows = cursor.fetchall()
    data = [VehicleOption(vehicle_id=r.get("vehicle_id")) for r in rows]
    return VehicleOptionSelect(data=data, total=total)


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
            "SELECT i.incident_id, 'D' + CAST(i.driver_id AS NVARCHAR) AS driver_id, d.person_name AS driver_name, "
            "i.vehicle_id, i.occurrence_time, i.incident_type, i.fine_amount, i.incident_description, i.handle_status AS handle_status "
            "FROM Incidents i "
            "JOIN Vehicles v ON i.vehicle_id = v.vehicle_id "
            "LEFT JOIN Drivers d ON i.driver_id = d.person_id AND d.is_deleted = 0 "
            "WHERE i.is_deleted = 0 AND v.is_deleted = 0 AND v.fleet_id = %s "
            "ORDER BY i.incident_id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            (auth_info.get("fleet_id"), offset, limit),
        )
    else:
        cursor.execute("SELECT COUNT(*) AS total FROM Incidents WHERE is_deleted = 0")
        total = cursor.fetchone()["total"]
        cursor.execute(
            "SELECT i.incident_id, 'D' + CAST(i.driver_id AS NVARCHAR) AS driver_id, d.person_name AS driver_name, "
            "i.vehicle_id, i.occurrence_time, i.incident_type, i.fine_amount, i.incident_description, i.handle_status "
            "FROM Incidents i "
            "LEFT JOIN Drivers d ON i.driver_id = d.person_id AND d.is_deleted = 0 "
            "WHERE i.is_deleted = 0 "
            "ORDER BY i.incident_id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            (offset, limit),
        )

    rows = cursor.fetchall()
    data: list[Incident] = []
    for r in rows:
        # r['driver_id'] 形如 'D5'；driver_name 可能为 None（如果司机已软删除）
        driver_id = r.get("driver_id")
        driver_name = r.get("driver_name")
        if isinstance(driver_id, str) and isinstance(driver_name, str) and driver_name.strip():
            r["driver_id"] = {"person_id": driver_id, "person_name": driver_name}
        r.pop("driver_name", None)
        data.append(Incident(**r))
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
    where_clauses = ["i.driver_id = %s", "i.is_deleted = 0"]
    params = [driver_id]

    if start:
        where_clauses.append("i.occurrence_time >= %s")
        params.append(start)
    if end:
        where_clauses.append("i.occurrence_time <= %s")
        params.append(end)

    where_sql = " AND ".join(where_clauses)

    # COUNT 查询
    cursor.execute(f"SELECT COUNT(*) AS total FROM Incidents i WHERE {where_sql}", params)
    total = cursor.fetchone()["total"]

    # 分页查询：注意 offset 和 limit 必须是最后两个参数
    params_with_pagination = params + [offset, limit]
    cursor.execute(
        f"""
        SELECT i.incident_id,
               'D' + CAST(i.driver_id AS NVARCHAR) AS driver_id,
               d.person_name AS driver_name,
               i.vehicle_id,
               i.occurrence_time,
               i.incident_type,
               i.fine_amount,
               i.incident_description,
               i.handle_status
        FROM Incidents i
        LEFT JOIN Drivers d ON i.driver_id = d.person_id AND d.is_deleted = 0
        WHERE {where_sql}
        ORDER BY i.incident_id
        OFFSET %s ROWS FETCH NEXT %s ROWS ONLY
        """,
        params_with_pagination
    )
    rows = cursor.fetchall()
    data: list[Incident] = []
    for r in rows:
        driver_id = r.get("driver_id")
        driver_name = r.get("driver_name")
        if isinstance(driver_id, str) and isinstance(driver_name, str) and driver_name.strip():
            r["driver_id"] = {"person_id": driver_id, "person_name": driver_name}
        r.pop("driver_name", None)
        data.append(Incident(**r))

    return IncidentSelect(data=data, total=total)