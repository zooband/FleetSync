from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from app import schemas, store
from app.routers import vehicles

router = APIRouter()


def _get_fleet_or_404(fleet_id: int) -> schemas.Fleet:
    for f in store.fleets_db:
        if f.fleet_id == fleet_id:
            return f
    raise HTTPException(status_code=404, detail="Fleet not found")


def _get_personnel_or_404(person_id: int) -> schemas.Personnel:
    for p in store.personnel_db:
        if p.person_id == person_id:
            return p
    raise HTTPException(status_code=404, detail="Personnel not found")


def _get_person_contact(person_id: int) -> str | None:
    for p in store.personnel_db:
        if getattr(p, "person_id", None) == person_id:
            return getattr(p, "person_contact", None)
    for m in store.managers_db:
        if getattr(m, "person_id", None) == person_id:
            return getattr(m, "person_contact", None)
    for d in store.drivers_db:
        if getattr(d, "person_id", None) == person_id:
            return getattr(d, "person_contact", None)
    return None


class CreateFleet(BaseModel):
    fleet_name: str
    manager_name: str
    manager_contact: str | None = None


@router.post("/api/fleets", response_model=schemas.Fleet, status_code=status.HTTP_201_CREATED)
def insert_fleet(fleet: CreateFleet, request: Request):
    # 仅 admin 可创建车队（按需求：创建车队时同步创建调度主管）
    if getattr(getattr(request, "state", None), "auth", {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    new_id = store.get_next_fleet_id()

    manager_pid = store.get_next_person_id()
    manager_person = schemas.Personnel(
        person_id=manager_pid,
        person_name=fleet.manager_name,
        person_contact=fleet.manager_contact,
        person_role="调度主管",
    )
    store.personnel_db.append(manager_person)

    new_fleet = schemas.Fleet(
        fleet_id=new_id,
        fleet_name=fleet.fleet_name,
        manager_id=manager_pid,
        manager_name=fleet.manager_name,
        center_id=0,
    )
    store.fleets_db.append(new_fleet)

    store.managers_db.append(
        schemas.Manager(
            person_id=manager_person.person_id,
            person_name=manager_person.person_name,
            person_role="调度主管",
            person_contact=manager_person.person_contact,
            fleet_id=new_id,
        )
    )

    return new_fleet


def _cascade_delete_fleet(fleet_id: int) -> None:
    # 车辆（以及相关订单/异常）
    vehicle_ids = {v.vehicle_id for v in store.vehicles_db if v.fleet_id == fleet_id}
    if vehicle_ids:
        store.orders_db[:] = [o for o in store.orders_db if o.vehicle_id not in vehicle_ids]
        store.incidents_db[:] = [i for i in store.incidents_db if i.vehicle_id not in vehicle_ids]
        store.vehicles_db[:] = [v for v in store.vehicles_db if v.vehicle_id not in vehicle_ids]

    # 司机（drivers_db + personnel_db）
    driver_ids = {d.person_id for d in store.drivers_db if getattr(d, "fleet_id", None) == fleet_id}
    if driver_ids:
        store.drivers_db[:] = [d for d in store.drivers_db if d.person_id not in driver_ids]
        store.personnel_db[:] = [p for p in store.personnel_db if p.person_id not in driver_ids]

    # 调度主管（managers_db + personnel_db）
    manager_ids = {m.person_id for m in store.managers_db if getattr(m, "fleet_id", None) == fleet_id}
    if manager_ids:
        store.managers_db[:] = [m for m in store.managers_db if m.person_id not in manager_ids]
        store.personnel_db[:] = [p for p in store.personnel_db if p.person_id not in manager_ids]

    # 车队
    store.fleets_db[:] = [f for f in store.fleets_db if f.fleet_id != fleet_id]


class CreateFleetVehicle(BaseModel):
    vehicle_id: str
    vehicle_load_capacity: float
    vehicle_volumn_capacity: float
    vehicle_status: str


class SelectVehicles(BaseModel):
    data: list[schemas.VehicleView]
    total: int


@router.get("/api/fleets/{fleet_id}/vehicles")
def get_vehicles_of_fleet(fleet_id: int, limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    fleet_exists = any(f.fleet_id == fleet_id for f in store.fleets_db)
    if not fleet_exists:
        raise HTTPException(status_code=404, detail="Fleet not found")
    fleet_vehicles = [v for v in store.vehicles_db if v.fleet_id == fleet_id]
    total = len(fleet_vehicles)
    paginated = fleet_vehicles[offset : offset + limit]
    return SelectVehicles(data=[vehicles.to_vehicle_view(v) for v in paginated], total=total)


@router.post("/api/fleets/{fleet_id}/vehicles", status_code=status.HTTP_201_CREATED)
def create_vehicle(fleet_id: int, vehicle: CreateFleetVehicle):
    fleet_exists = any(f.fleet_id == fleet_id for f in store.fleets_db)
    if not fleet_exists:
        raise HTTPException(status_code=404, detail="Fleet not found")
    new_vehicle = schemas.Vehicle(
        vehicle_id=vehicle.vehicle_id,
        vehicle_load_capacity=vehicle.vehicle_load_capacity,
        vehicle_volumn_capacity=vehicle.vehicle_volumn_capacity,
        vehicle_status=vehicle.vehicle_status,
        fleet_id=fleet_id,
    )
    store.vehicles_db.append(new_vehicle)
    return new_vehicle


class SelectPersonnels(BaseModel):
    data: list[schemas.Personnel]
    total: int


@router.get("/api/fleets/{fleet_id}/personnels")
def get_personnels_of_fleet(fleet_id: int, limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    _get_fleet_or_404(fleet_id)

    fleet_personnels: list[schemas.Personnel] = []

    for m in store.managers_db:
        if m.fleet_id == fleet_id:
            for p in store.personnel_db:
                if p.person_id == m.person_id:
                    fleet_personnels.append(p)
                    break
            break

    for d in store.drivers_db:
        if getattr(d, "fleet_id", None) == fleet_id:
            for p in store.personnel_db:
                if p.person_id == d.person_id:
                    fleet_personnels.append(p)
                    break

    uniq: dict[int, schemas.Personnel] = {p.person_id: p for p in fleet_personnels}
    fleet_personnels = list(uniq.values())

    total = len(fleet_personnels)
    filtered = fleet_personnels[offset : offset + limit]
    return SelectPersonnels(data=filtered, total=total)


@router.delete("/api/fleets/{fleet_id}/personnels/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def detach_personnel_from_fleet(fleet_id: int, person_id: int):
    """从车队中移除人员（解绑）。

    当前数据模型中：
    - 调度主管：store.managers_db[fleet_id]
    - 司机：store.drivers_db[fleet_id]

    本接口实现“解绑式删除”：
    - 若 person_id 是该车队调度主管：拒绝
    - 若 person_id 是该车队司机：将其 fleet_id 设为 -1，并解除其在该车队车辆上的 driver_id
    """

    _get_fleet_or_404(fleet_id)
    _get_personnel_or_404(person_id)

    manager = next((m for m in store.managers_db if getattr(m, "fleet_id", None) == fleet_id), None)
    if manager is not None and manager.person_id == person_id:
        raise HTTPException(status_code=400, detail="调度主管不可从车队中删除")

    # 找到该司机记录
    driver_idx = next((i for i, d in enumerate(store.drivers_db) if d.person_id == person_id and getattr(d, "fleet_id", None) == fleet_id), None)
    if driver_idx is None:
        raise HTTPException(status_code=404, detail="Driver not found in fleet")

    # 如果该司机当前承载活跃运单，不允许解绑（避免车辆/运单状态不一致）
    active_vehicle_ids = {v.vehicle_id for v in store.vehicles_db if v.fleet_id == fleet_id and v.driver_id == person_id}
    if active_vehicle_ids:
        for o in store.orders_db:
            if o.vehicle_id in active_vehicle_ids and o.status in ("装货中", "运输中"):
                raise HTTPException(status_code=400, detail="该司机存在进行中的运单，无法解绑")

    # 解绑车辆上的司机
    for i, v in enumerate(store.vehicles_db):
        if v.fleet_id == fleet_id and v.driver_id == person_id:
            store.vehicles_db[i] = v.model_copy(update={"driver_id": None})

    # 解绑司机与车队
    d = store.drivers_db[driver_idx]
    store.drivers_db[driver_idx] = d.model_copy(update={"fleet_id": -1, "driver_status": "空闲"})
    return


class AssignFleetManager(BaseModel):
    person_id: int


class FleetDriverCreate(BaseModel):
    person_name: str
    person_contact: str | None = None
    driver_license: str


class SelectDrivers(BaseModel):
    data: list[schemas.Driver]
    total: int


@router.get("/api/fleets/{fleet_id}/drivers", response_model=SelectDrivers)
def list_fleet_drivers(
    fleet_id: int,
    limit: int = Query(10, ge=1),
    offset: int = Query(0, ge=0),
):
    _get_fleet_or_404(fleet_id)
    rows = [d for d in store.drivers_db if getattr(d, "fleet_id", None) == fleet_id]
    total = len(rows)
    paginated = rows[offset : offset + limit]
    return SelectDrivers(data=paginated, total=total)


@router.post("/api/fleets/{fleet_id}/drivers", response_model=schemas.Driver, status_code=status.HTTP_201_CREATED)
def create_fleet_driver(fleet_id: int, payload: FleetDriverCreate, request: Request):
    # 仅 admin 可创建司机（按需求：车队页创建司机信息）
    if getattr(getattr(request, "state", None), "auth", {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    _get_fleet_or_404(fleet_id)
    pid = store.get_next_person_id()
    p = schemas.Personnel(
        person_id=pid,
        person_name=payload.person_name,
        person_contact=payload.person_contact,
        person_role="司机",
    )
    store.personnel_db.append(p)

    d = schemas.Driver(
        person_id=p.person_id,
        person_name=p.person_name,
        person_role="司机",
        person_contact=p.person_contact,
        driver_license=payload.driver_license,
        driver_status="空闲",
        fleet_id=fleet_id,
    )
    store.drivers_db.append(d)
    return d


class FleetPaginatedResponse(BaseModel):
    data: list[schemas.Fleet]
    total: int


class FleetDetailResponse(BaseModel):
    fleet_id: int
    fleet_name: str
    manager_id: int
    manager_name: str
    manager_contact: str | None = None
    center_id: int


class FleetUpdate(BaseModel):
    fleet_name: str | None = None
    manager_name: str | None = None
    manager_contact: str | None = None


@router.get("/api/fleets")
def list_fleets(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    filtered = store.fleets_db

    total = len(filtered)
    paginated_data = filtered[offset : offset + limit]
    return FleetPaginatedResponse(data=paginated_data, total=total)


@router.get("/api/fleets/{fleet_id}", response_model=FleetDetailResponse)
def get_fleet_detail(fleet_id: int):
    fleet = _get_fleet_or_404(fleet_id)
    return FleetDetailResponse(
        fleet_id=fleet.fleet_id,
        fleet_name=fleet.fleet_name,
        manager_id=fleet.manager_id,
        manager_name=fleet.manager_name,
        manager_contact=_get_person_contact(fleet.manager_id),
        center_id=fleet.center_id,
    )


@router.patch("/api/fleets/{fleet_id}", response_model=FleetDetailResponse)
def update_fleet_detail(fleet_id: int, updates: FleetUpdate, request: Request):
    # 按需求：只有 admin 可以编辑车队信息与调度主管信息
    if getattr(getattr(request, "state", None), "auth", {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    fleet = _get_fleet_or_404(fleet_id)
    update_data = updates.model_dump(exclude_unset=True)

    # 更新 fleets_db
    fleet_patch: dict[str, object] = {}
    if "fleet_name" in update_data:
        fleet_patch["fleet_name"] = update_data["fleet_name"]
    if "manager_name" in update_data:
        fleet_patch["manager_name"] = update_data["manager_name"]

    if fleet_patch:
        for i, f in enumerate(store.fleets_db):
            if f.fleet_id == fleet_id:
                store.fleets_db[i] = f.model_copy(update=fleet_patch)
                fleet = store.fleets_db[i]
                break

    # 同步调度主管（personnel_db + managers_db）
    manager_patch: dict[str, object] = {}
    if "manager_name" in update_data:
        manager_patch["person_name"] = update_data["manager_name"]
    if "manager_contact" in update_data:
        manager_patch["person_contact"] = update_data["manager_contact"]

    if manager_patch:
        # personnel_db
        for i, p in enumerate(store.personnel_db):
            if p.person_id == fleet.manager_id:
                store.personnel_db[i] = p.model_copy(update=manager_patch)
                break
        # managers_db
        for i, m in enumerate(store.managers_db):
            if m.person_id == fleet.manager_id:
                store.managers_db[i] = m.model_copy(update=manager_patch)
                break

    return FleetDetailResponse(
        fleet_id=fleet.fleet_id,
        fleet_name=fleet.fleet_name,
        manager_id=fleet.manager_id,
        manager_name=fleet.manager_name,
        manager_contact=_get_person_contact(fleet.manager_id),
        center_id=fleet.center_id,
    )


@router.get("/api/fleets/{fleet_id}/resources")
def get_fleet_resources(fleet_id: int):
    return {"fleet_id": fleet_id, "vehicles": ["京A12345", "沪B67890"], "drivers": [101, 102], "active_orders": 3}


@router.get("/api/fleets/{fleet_id}/monthly_stat")
def get_fleet_statistics(fleet_id: int, month: date):
    return {"fleet_id": fleet_id, "month": month.isoformat(), "total_orders": 45, "total_distance": 12000, "fuel_cost": 8500.0, "incident_count": 2}


class FleetMonthlyReport(BaseModel):
    orders: int
    incidents: int
    fines: float


@router.get("/api/fleets/{fleet_id}/reports/monthly", response_model=FleetMonthlyReport)
def get_fleet_monthly_report(fleet_id: int, month: str | None = Query(None)):
    m = (month or datetime.now().strftime("%Y-%m")).strip()
    try:
        base = datetime.strptime(m, "%Y-%m")
    except ValueError:
        raise HTTPException(status_code=422, detail="month 格式应为 YYYY-MM")

    start_d = date(base.year, base.month, 1)
    end_d = date(base.year + 1, 1, 1) if base.month == 12 else date(base.year, base.month + 1, 1)

    fleet_vehicle_ids = {v.vehicle_id for v in store.vehicles_db if v.fleet_id == fleet_id}

    month_orders: list[schemas.Order] = []
    for o in store.orders_db:
        if o.vehicle_id is None or o.vehicle_id not in fleet_vehicle_ids:
            continue
        if o.status != "已完成":
            continue
        d = getattr(o, "completed_at", None) or getattr(o, "created_at", None)
        if d is None:
            continue
        if start_d <= d < end_d:
            month_orders.append(o)
    month_incidents = [i for i in store.incidents_db if i.vehicle_id in fleet_vehicle_ids and start_d <= i.timestamp < end_d]
    fines = sum((i.fine_amount or 0.0) for i in month_incidents)

    return FleetMonthlyReport(orders=len(month_orders), incidents=len(month_incidents), fines=float(fines))


@router.delete("/api/fleets/{fleet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fleet(fleet_id: int, request: Request):
    # 删除车队属于高权限操作：仅 admin
    if getattr(getattr(request, "state", None), "auth", {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    _get_fleet_or_404(fleet_id)
    _cascade_delete_fleet(fleet_id)
    return


@router.delete("/api/fleets/{fleet_id}/drivers/{driver_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fleet_driver(fleet_id: int, driver_id: int, request: Request):
    # 仅 admin
    if getattr(getattr(request, "state", None), "auth", {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    _get_fleet_or_404(fleet_id)

    # 找到司机记录（必须属于该车队）
    driver_idx = next(
        (i for i, d in enumerate(store.drivers_db) if d.person_id == driver_id and getattr(d, "fleet_id", None) == fleet_id),
        None,
    )
    if driver_idx is None:
        raise HTTPException(status_code=404, detail="Driver not found in fleet")

    # 如果该司机当前承载活跃运单，不允许删除（避免车辆/运单状态不一致）
    active_vehicle_ids = {v.vehicle_id for v in store.vehicles_db if v.fleet_id == fleet_id and v.driver_id == driver_id}
    if active_vehicle_ids:
        for o in store.orders_db:
            if o.vehicle_id in active_vehicle_ids and o.status in ("装货中", "运输中"):
                raise HTTPException(status_code=400, detail="该司机存在进行中的运单，无法删除")

    # 解绑车辆上的司机
    for i, v in enumerate(store.vehicles_db):
        if v.fleet_id == fleet_id and v.driver_id == driver_id:
            store.vehicles_db[i] = v.model_copy(update={"driver_id": None})

    # 删除司机（drivers_db + personnel_db）
    store.drivers_db.pop(driver_idx)
    store.personnel_db[:] = [p for p in store.personnel_db if p.person_id != driver_id]
    return
