from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app import schemas, store
from app.routers import vehicles

router = APIRouter()


class SelectOrder(BaseModel):
    data: list[schemas.Order]
    total: int


def select_orders_by_status(status_value: str, limit: int, offset: int) -> SelectOrder:
    filtered = [o for o in store.orders_db if o.status == status_value]
    total = len(filtered)
    paginated = filtered[offset : offset + limit]
    return SelectOrder(data=paginated, total=total)


@router.get("/api/orders/pending", response_model=SelectOrder)
def get_orders_pending(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    return select_orders_by_status("待处理", limit, offset)


@router.get("/api/orders/loading", response_model=SelectOrder)
def get_orders_loading(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    return select_orders_by_status("装货中", limit, offset)


@router.get("/api/orders/transit", response_model=SelectOrder)
def get_orders_transit(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    return select_orders_by_status("运输中", limit, offset)


@router.get("/api/orders/done", response_model=SelectOrder)
def get_orders_done(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    return select_orders_by_status("已完成", limit, offset)


@router.get("/api/orders/cancelled", response_model=SelectOrder)
def get_orders_cancelled(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    return select_orders_by_status("已取消", limit, offset)


class CreateOrder(BaseModel):
    origin: str
    destination: str
    weight: float
    volume: float
    status: str
    vehicle_id: str | None


@router.post("/api/orders", response_model=schemas.Order, status_code=status.HTTP_201_CREATED)
def insert_order(order: CreateOrder):
    new_id = store.get_next_order_id()
    new_order = schemas.Order(
        order_id=new_id,
        origin=order.origin,
        destination=order.destination,
        weight=order.weight,
        volume=order.volume,
        status=order.status,
        vehicle_id=order.vehicle_id,
    )
    store.orders_db.append(new_order)
    return new_order


class UpdateOrder(BaseModel):
    status: str | None = None
    vehicle_id: str | None = None


@router.patch("/api/orders/{order_id}", response_model=schemas.Order)
def update_order(order_id: int, updates: UpdateOrder):
    for i, order in enumerate(store.orders_db):
        if order.order_id == order_id:
            prev_vehicle_id = order.vehicle_id
            update_data = updates.model_dump(exclude_unset=True)

            # 若通过该接口将订单置为“已完成”，同步记录完成日期
            if update_data.get("status") == "已完成":
                update_data.setdefault("completed_at", date.today())

            # 分配/变更车辆：允许同车多单（装货中/运输中合并占用），但必须满足剩余容量。
            if "vehicle_id" in update_data and update_data.get("vehicle_id") is not None:
                new_vehicle_id = str(update_data["vehicle_id"])
                vehicle = next((v for v in store.vehicles_db if v.vehicle_id == new_vehicle_id), None)
                if vehicle is None:
                    raise HTTPException(status_code=404, detail="找不到车辆")
                if vehicle.vehicle_status == "维修中":
                    raise HTTPException(status_code=400, detail="车辆维修中，无法分配")
                if vehicle.vehicle_status == "运输中":
                    raise HTTPException(status_code=400, detail="车辆运输中，无法追加订单")

                used_w = 0.0
                used_v = 0.0
                for o in store.orders_db:
                    if o.order_id == order.order_id:
                        continue
                    if o.vehicle_id != new_vehicle_id:
                        continue
                    if o.status not in ("装货中", "运输中"):
                        continue
                    used_w += float(o.weight)
                    used_v += float(o.volume)

                remaining_w = max(float(vehicle.vehicle_load_capacity) - used_w, 0.0)
                remaining_v = max(float(vehicle.vehicle_volumn_capacity) - used_v, 0.0)

                if float(order.weight) > remaining_w or float(order.volume) > remaining_v:
                    raise HTTPException(status_code=400, detail="车辆剩余容量不足")

            updated_order = order.model_copy(update=update_data)
            store.orders_db[i] = updated_order

            if updated_order.status == "已取消" and prev_vehicle_id:
                vehicles.release_vehicle_if_idle(prev_vehicle_id, updated_order.order_id)

            return updated_order
    raise HTTPException(status_code=404, detail="Order not found")


@router.delete("/api/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_order_compat(order_id: int):
    for order in store.orders_db:
        if order.order_id == order_id:
            prev_vehicle_id = order.vehicle_id
            order.status = "已取消"
            if prev_vehicle_id:
                vehicles.release_vehicle_if_idle(prev_vehicle_id, order.order_id)
            return
    raise HTTPException(status_code=404, detail="Order not found")
