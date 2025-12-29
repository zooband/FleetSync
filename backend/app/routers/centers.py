from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from app import schemas, store
from app.routers.fleets import CreateFleet, _cascade_delete_fleet

router = APIRouter()


class PaginatedResponse(BaseModel):
    data: list[schemas.DistributionCenter]
    total: int


class DistributionCenterCreate(BaseModel):
    center_name: str


class DistributionCenterUpdate(BaseModel):
    center_name: str | None = None


@router.post("/api/distribution-centers", response_model=schemas.DistributionCenter, status_code=status.HTTP_201_CREATED)
def insert_distribution_center(center: DistributionCenterCreate):
    new_id = store.get_next_distributioncenter_id()
    new_center = schemas.DistributionCenter(center_id=new_id, center_name=center.center_name)
    store.distributioncenters_db.append(new_center)
    return new_center


@router.get("/api/distribution-centers", response_model=PaginatedResponse)
def get_distribution_centers(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    filtered = store.distributioncenters_db
    total = len(filtered)
    paginated_data = filtered[offset : offset + limit]
    return PaginatedResponse(data=paginated_data, total=total)


@router.get("/api/distribution-centers/{center_id}", response_model=schemas.DistributionCenter)
def get_distribution_center(center_id: int):
    for c in store.distributioncenters_db:
        if c.center_id == center_id:
            return c
    raise HTTPException(status_code=404, detail="Distribution Center not found")


@router.patch("/api/distribution-centers/{center_id}", response_model=schemas.DistributionCenter)
def update_distribution_center(center_id: int, updates: DistributionCenterUpdate, request: Request):
    # 按需求：只有 admin 可以编辑配送中心信息
    if getattr(getattr(request, "state", None), "auth", {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    for i, center in enumerate(store.distributioncenters_db):
        if center.center_id == center_id:
            update_data = updates.model_dump(exclude_unset=True)
            updated_center = center.model_copy(update=update_data)
            store.distributioncenters_db[i] = updated_center
            return updated_center
    raise HTTPException(status_code=404, detail="Distribution Center not found")


@router.delete("/api/distribution-centers/{center_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_distribution_center(center_id: int, request: Request):
    # 高权限：仅 admin（middleware 已限制，但这里保持显式）
    if getattr(getattr(request, "state", None), "auth", {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    # 级联删除：配送中心 -> 车队 -> 车辆/订单/异常/人员
    fleet_ids = [f.fleet_id for f in store.fleets_db if f.center_id == center_id]
    for fid in fleet_ids:
        _cascade_delete_fleet(fid)

    for i, center in enumerate(store.distributioncenters_db):
        if center.center_id == center_id:
            store.distributioncenters_db.pop(i)
            return
    raise HTTPException(status_code=404, detail="Distribution Center not found")


class FleetSelectResponse(BaseModel):
    data: list[schemas.Fleet]
    total: int


@router.get("/api/distribution-centers/{center_id}/fleets")
def get_center_fleets(center_id: int, limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    filtered = [f for f in store.fleets_db if f.center_id == center_id]
    total = len(filtered)
    paginated_data = filtered[offset : offset + limit]
    return FleetSelectResponse(data=paginated_data, total=total)


class CenterAvailableVehicle(BaseModel):
    vehicle_id: str
    remaining_load_capacity: float
    remaining_volumn_capacity: float


class CenterUnavailableVehicle(BaseModel):
    vehicle_id: str
    status: str


class CenterVehicleResources(BaseModel):
    available: list[CenterAvailableVehicle]
    unavailable: list[CenterUnavailableVehicle]


@router.get("/api/distribution-centers/{center_id}/vehicle-resources", response_model=CenterVehicleResources)
def get_center_vehicle_resources(center_id: int):
    fleet_ids = {f.fleet_id for f in store.fleets_db if f.center_id == center_id}
    center_vehicles = [v for v in store.vehicles_db if v.fleet_id is not None and v.fleet_id in fleet_ids]

    used_weight: dict[str, float] = {}
    used_volume: dict[str, float] = {}
    active_status: dict[str, str] = {}
    for o in store.orders_db:
        if not o.vehicle_id:
            continue
        if o.status not in ("装货中", "运输中"):
            continue
        used_weight[o.vehicle_id] = used_weight.get(o.vehicle_id, 0.0) + float(o.weight)
        used_volume[o.vehicle_id] = used_volume.get(o.vehicle_id, 0.0) + float(o.volume)
        active_status[o.vehicle_id] = o.status

    has_open_incident: set[str] = set()
    for inc in store.incidents_db:
        if getattr(inc, "status", None) == "未处理":
            has_open_incident.add(inc.vehicle_id)

    available: list[CenterAvailableVehicle] = []
    unavailable: list[CenterUnavailableVehicle] = []

    for v in center_vehicles:
        used_w = used_weight.get(v.vehicle_id, 0.0)
        used_v = used_volume.get(v.vehicle_id, 0.0)
        remaining_w = max(float(v.vehicle_load_capacity) - used_w, 0.0)
        remaining_vol = max(float(v.vehicle_volumn_capacity) - used_v, 0.0)

        has_active_order = v.vehicle_id in active_status
        is_full = remaining_w <= 0.0 or remaining_vol <= 0.0
        is_abnormal = v.vehicle_id in has_open_incident

        if v.vehicle_status == "空闲" and (not has_active_order) and (not is_full) and (not is_abnormal):
            available.append(
                CenterAvailableVehicle(
                    vehicle_id=v.vehicle_id,
                    remaining_load_capacity=remaining_w,
                    remaining_volumn_capacity=remaining_vol,
                )
            )
        else:
            if is_abnormal:
                status_text = "异常"
            elif is_full:
                status_text = "满载"
            elif has_active_order:
                status_text = active_status.get(v.vehicle_id) or v.vehicle_status
            else:
                status_text = v.vehicle_status
            unavailable.append(CenterUnavailableVehicle(vehicle_id=v.vehicle_id, status=status_text))

    available.sort(key=lambda x: x.vehicle_id)
    unavailable.sort(key=lambda x: x.vehicle_id)

    return CenterVehicleResources(available=available, unavailable=unavailable)


@router.post("/api/distribution-centers/{center_id}/fleets", status_code=status.HTTP_201_CREATED)
def add_center_fleet(center_id: int, fleet: CreateFleet, request: Request):
    # 仅 admin 可创建车队
    if getattr(getattr(request, "state", None), "auth", {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    new_id = store.get_next_fleet_id()

    # 创建调度主管（不再依赖“普通员工 -> 指派/升级”）
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
        center_id=center_id,
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


@router.delete("/api/distribution-centers/{center_id}/fleets/{fleet_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_center_fleet(center_id: int, fleet_id: int):
    # 级联删除整个车队
    target = next((f for f in store.fleets_db if f.fleet_id == fleet_id and f.center_id == center_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Fleet not found")
    _cascade_delete_fleet(fleet_id)
    return


class FleetUpdate(BaseModel):
    fleet_name: str | None = None


@router.patch("/api/distribution-centers/{center_id}/fleets/{fleet_id}", status_code=status.HTTP_200_OK)
def update_center_fleet(center_id: int, fleet_id: int, updates: FleetUpdate):
    for i, fleet in enumerate(store.fleets_db):
        if fleet.fleet_id == fleet_id and fleet.center_id == center_id:
            updated_fleet = fleet.model_copy(update=updates.model_dump(exclude_unset=True))
            store.fleets_db[i] = updated_fleet
            return updated_fleet
    raise HTTPException(status_code=404, detail="Fleet not found")
