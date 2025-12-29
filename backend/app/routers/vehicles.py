from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app import schemas, store

router = APIRouter()


class SelectVehiclesResponse(BaseModel):
    data: list[schemas.VehicleView]
    total: int


def get_fleet_name(fleet_id: int | None) -> str | None:
    if fleet_id is None:
        return None
    for f in store.fleets_db:
        if f.fleet_id == fleet_id:
            return f.fleet_name
    return None


def get_driver_name(driver_id: int | None) -> str | None:
    if driver_id is None:
        return None
    for p in store.personnel_db:
        if p.person_id == driver_id:
            return p.person_name
    for d in store.drivers_db:
        if d.person_id == driver_id:
            return d.person_name
    return None


def vehicle_remaining(vehicle_id: str, capacity_w: float, capacity_v: float) -> tuple[float, float]:
    used_w = 0.0
    used_v = 0.0
    for o in store.orders_db:
        if o.vehicle_id != vehicle_id:
            continue
        if o.status not in ("装货中", "运输中"):
            continue
        used_w += float(o.weight)
        used_v += float(o.volume)
    return max(float(capacity_w) - used_w, 0.0), max(float(capacity_v) - used_v, 0.0)


def get_active_order_for_vehicle(vehicle_id: str) -> schemas.Order | None:
    candidates = [o for o in store.orders_db if o.vehicle_id == vehicle_id and o.status in ("装货中", "运输中")]
    if not candidates:
        return None
    return max(candidates, key=lambda o: o.order_id)


def has_other_active_orders(vehicle_id: str, exclude_order_id: int) -> bool:
    for o in store.orders_db:
        if o.order_id == exclude_order_id:
            continue
        if o.vehicle_id == vehicle_id and o.status in ("装货中", "运输中"):
            return True
    return False


def set_driver_status(driver_id: int | None, status_value: str) -> None:
    if driver_id is None:
        return
    for i, d in enumerate(store.drivers_db):
        if d.person_id == driver_id:
            store.drivers_db[i] = d.model_copy(update={"driver_status": status_value})
            return


def release_vehicle_if_idle(vehicle_id: str, exclude_order_id: int) -> None:
    if has_other_active_orders(vehicle_id, exclude_order_id):
        return
    for i, v in enumerate(store.vehicles_db):
        if v.vehicle_id == vehicle_id:
            store.vehicles_db[i] = v.model_copy(update={"vehicle_status": "空闲"})
            set_driver_status(v.driver_id, "空闲")
            return


def to_vehicle_view(v: schemas.Vehicle) -> schemas.VehicleView:
    remaining_w, remaining_v = vehicle_remaining(v.vehicle_id, v.vehicle_load_capacity, v.vehicle_volumn_capacity)
    active = get_active_order_for_vehicle(v.vehicle_id)
    return schemas.VehicleView(
        **v.model_dump(),
        driver_name=get_driver_name(v.driver_id),
        fleet_name=get_fleet_name(v.fleet_id),
        remaining_load_capacity=remaining_w,
        remaining_volumn_capacity=remaining_v,
        active_order_id=(active.order_id if active else None),
        active_order_status=(active.status if active else None),
    )


class CreateVehicle(BaseModel):
    vehicle_id: str
    vehicle_load_capacity: float
    vehicle_volumn_capacity: float
    fleet_id: int | None = None


@router.post("/api/vehicles", response_model=schemas.Vehicle, status_code=status.HTTP_201_CREATED)
def insert_vehicle(vehicle: CreateVehicle):
    v = schemas.Vehicle(
        vehicle_id=vehicle.vehicle_id,
        vehicle_load_capacity=vehicle.vehicle_load_capacity,
        vehicle_volumn_capacity=vehicle.vehicle_volumn_capacity,
        vehicle_status="空闲",
        fleet_id=vehicle.fleet_id,
        driver_id=None,
    )
    store.vehicles_db.append(v)
    return v


class PatchVehicle(BaseModel):
    fleet_id: int | None = None
    driver_id: int | None = None
    vehicle_load_capacity: float | None = None
    vehicle_volumn_capacity: float | None = None
    vehicle_status: str | None = None


@router.patch("/api/vehicles/{vehicle_id}", response_model=schemas.Vehicle, status_code=status.HTTP_201_CREATED)
def update_vehicle(vehicle_id: str, updates: PatchVehicle):
    for i, vehicle in enumerate(store.vehicles_db):
        if vehicle.vehicle_id == vehicle_id:
            update_data = updates.model_dump(exclude_unset=True)

            if "vehicle_status" in update_data:
                target_status = str(update_data.get("vehicle_status"))
                if target_status not in ("空闲", "维修中"):
                    raise HTTPException(status_code=422, detail="vehicle_status 仅支持：空闲 / 维修中")

                # 运输/装货期间不允许切换维修模式
                active = get_active_order_for_vehicle(vehicle.vehicle_id)
                if active is not None and active.status in ("装货中", "运输中"):
                    raise HTTPException(status_code=400, detail="车辆存在进行中的运单，无法切换维修状态")

                # 仅当当前非运输中时允许手动切换；运输中由业务逻辑控制
                if vehicle.vehicle_status == "运输中":
                    raise HTTPException(status_code=400, detail="车辆运输中，无法切换维修状态")

                vehicle = vehicle.model_copy(update={"vehicle_status": target_status})
                update_data.pop("vehicle_status", None)

            if "driver_id" in update_data:
                new_driver_id = update_data.get("driver_id")
                if new_driver_id is not None:
                    driver = next((d for d in store.drivers_db if d.person_id == new_driver_id), None)
                    if driver is None:
                        raise HTTPException(status_code=404, detail="Driver not found")
                    if vehicle.fleet_id is None or getattr(driver, "fleet_id", None) != vehicle.fleet_id:
                        raise HTTPException(status_code=400, detail="司机与车辆不在同一车队")
                    for ov in store.vehicles_db:
                        if ov.vehicle_id != vehicle.vehicle_id and ov.driver_id == new_driver_id:
                            raise HTTPException(status_code=400, detail="该司机已分配到其他车辆")

                vehicle = vehicle.model_copy(update={"driver_id": new_driver_id})
                update_data.pop("driver_id", None)

            updated_vehicle = vehicle.model_copy(update=update_data)
            store.vehicles_db[i] = updated_vehicle
            return updated_vehicle
    raise HTTPException(status_code=404, detail="Vehicle not found")


@router.get("/api/vehicles", response_model=SelectVehiclesResponse)
def get_vehicles(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    filtered = store.vehicles_db
    total = len(filtered)
    paginated = filtered[offset : offset + limit]
    return SelectVehiclesResponse(data=[to_vehicle_view(v) for v in paginated], total=total)


@router.get("/api/vehicles/available", response_model=list[schemas.Vehicle])
def get_available_vehicles():
    return [v for v in store.vehicles_db if v.vehicle_status == "空闲"]


@router.get("/api/vehicles/{vehicle_id}/info", response_model=schemas.VehicleView)
def get_vehicle(vehicle_id: str):
    for v in store.vehicles_db:
        if v.vehicle_id == vehicle_id:
            return to_vehicle_view(v)
    raise HTTPException(status_code=404, detail="Vehicle not found")


@router.post("/api/vehicles/{vehicle_id}/depart", response_model=schemas.Order)
def depart_vehicle(vehicle_id: str):
    vehicle = next((v for v in store.vehicles_db if v.vehicle_id == vehicle_id), None)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # 业务规则：未分配司机不可发车
    if vehicle.driver_id is None:
        raise HTTPException(status_code=400, detail="请先为车辆分配司机")

    # 同一辆车可能承载多单：发车时将该车所有“装货中”订单统一转为“运输中”
    loading_orders = [o for o in store.orders_db if o.vehicle_id == vehicle_id and o.status == "装货中"]
    if not loading_orders:
        raise HTTPException(status_code=400, detail="该车辆当前没有处于装货中的订单")

    for o in loading_orders:
        o.status = "运输中"
    for i, v in enumerate(store.vehicles_db):
        if v.vehicle_id == vehicle_id:
            store.vehicles_db[i] = v.model_copy(update={"vehicle_status": "运输中"})
            break
    set_driver_status(vehicle.driver_id, "运输中")
    # 返回其中一单（兼容前端不依赖 response body 的情况）
    return max(loading_orders, key=lambda x: x.order_id)


@router.post("/api/vehicles/{vehicle_id}/deliver", response_model=schemas.Order)
def deliver_vehicle(vehicle_id: str):
    vehicle = next((v for v in store.vehicles_db if v.vehicle_id == vehicle_id), None)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # 同一辆车可能承载多单：送达时将该车所有“运输中”订单统一转为“已完成”并释放车辆/司机
    transit_orders = [o for o in store.orders_db if o.vehicle_id == vehicle_id and o.status == "运输中"]
    if not transit_orders:
        raise HTTPException(status_code=400, detail="该车辆当前没有运输中的订单")

    today = date.today()
    for o in transit_orders:
        o.status = "已完成"
        # 用于月度“已完成运单”统计
        o.completed_at = today
    for i, v in enumerate(store.vehicles_db):
        if v.vehicle_id == vehicle_id:
            store.vehicles_db[i] = v.model_copy(update={"vehicle_status": "空闲"})
            break
    set_driver_status(vehicle.driver_id, "空闲")
    return max(transit_orders, key=lambda x: x.order_id)


@router.delete("/api/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(vehicle_id: str):
    for i, v in enumerate(store.vehicles_db):
        if v.vehicle_id == vehicle_id:
            store.vehicles_db.pop(i)
            return
    raise HTTPException(status_code=404, detail="Vehicle not found")
