from datetime import date

from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel

from app.db import get_db
from app.auth_core import require_admin_manager_or_driver_self

router = APIRouter()

class Order(BaseModel):
    order_id: int
    origin: str
    destination: str
    weight: float
    volume: float
    status: str  # ['待处理', '装货中', '运输中', '已完成', '已取消']
    vehicle_id: str | None = None
    completed_at: date | None = None


class OrderSelect(BaseModel):
    data: list[Order]
    total: int

class OrderCreate(BaseModel):
    origin: str
    destination: str
    weight: float
    volume: float
    status: str
    vehicle_id: str | None

class OrderUpdate(BaseModel):
    status: str | None = None
    vehicle_id: str | None = None


def select_orders_by_status(status_value: str, limit: int, offset: int) -> OrderSelect:
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM Orders WHERE status = %s", (status_value,))
    total = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT order_id, origin, destination, weight, volume, status, vehicle_id, completed_at "
        "FROM Orders WHERE status = %s ORDER BY order_id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
        (status_value, offset, limit),
    )
    rows = cursor.fetchall()
    data = [Order(**r) for r in rows]
    return OrderSelect(data=data, total=total)


@router.get("/api/orders/pending", response_model=OrderSelect)
def get_orders_pending(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    return select_orders_by_status("待处理", limit, offset)


@router.get("/api/orders/loading", response_model=OrderSelect)
def get_orders_loading(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    return select_orders_by_status("装货中", limit, offset)


@router.get("/api/orders/transit", response_model=OrderSelect)
def get_orders_transit(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    return select_orders_by_status("运输中", limit, offset)


@router.get("/api/orders/done", response_model=OrderSelect)
def get_orders_done(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    return select_orders_by_status("已完成", limit, offset)


@router.get("/api/orders/cancelled", response_model=OrderSelect)
def get_orders_cancelled(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    return select_orders_by_status("已取消", limit, offset)


@router.post("/api/orders", response_model=Order, status_code=status.HTTP_201_CREATED)
def insert_order(order: OrderCreate, conn=Depends(get_db)):
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Orders (weight, volume, origin, destination, order_status, vehicle_id) VALUES (%s, %s, %s, %s, %s, %s);", (order.weight, order.volume, order.origin, order.destination, order.status, order.vehicle_id))
        cursor.execute("SELECT SCOPE_IDENTITY() AS order_id;")
        order_id = int(cursor.fetchone()["order_id"])
        conn.commit()
        return {"detail": "订单创建成功", "order_id": order_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="订单创建失败") from e


@router.delete("/api/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_order(order_id: int):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT vehicle_id FROM Orders WHERE order_id = %s AND order_status != '已取消'", (order_id,))
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到订单记录")

        cursor.execute("UPDATE Orders SET order_status = '已取消' WHERE order_id = %s AND order_status != '已取消'", (order_id,))
        conn.commit()
        return {"detail": "订单取消成功"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="取消订单失败") from e
    

@router.get("/api/drivers/{person_id}/orders", response_model=OrderSelect)
def get_driver_finished_orders(
    person_id: int,
    start: str | None = Query(None),
    end: str | None = Query(None),
    limit: int = Query(10, ge=1),
    offset: int = Query(0, ge=0),
    auth_info=Depends(require_admin_manager_or_driver_self),
):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) AS total FROM Orders o JOIN CompletedTaskLogs c ON o.order_id = c.order_id WHERE driver_id = %s"
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
        "SELECT order_id, origin, destination, weight, volume, order_status AS status, vehicle_id, completed_at FROM Orders o JOIN CompletedTaskLogs c ON o.order_id = c.order_id WHERE driver_id = %s"
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
    data = [Order(**r) for r in rows]
    return OrderSelect(data=data, total=total)