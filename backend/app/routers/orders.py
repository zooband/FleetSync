from datetime import date
from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel
from app.db import get_db
from app.auth_core import require_admin_manager_or_driver_self

router = APIRouter()

# --- 数据模型定义 ---

class Order(BaseModel):
    order_id: int
    origin: str
    destination: str
    weight: float
    volume: float
    status: str
    vehicle_id: str | None = None
    completed_at: date | None = None  # 从 CompletedOrder 表关联获取

class OrderSelect(BaseModel):
    data: list[Order]
    total: int

class OrderCreate(BaseModel):
    origin: str
    destination: str
    weight: float
    volume: float
    status: str = "待处理"
    vehicle_id: str | None = None

class OrderUpdate(BaseModel):
    vehicle_id: str | None = None

# --- 内部工具函数 ---

def select_orders_by_status(status_value: str, limit: int, offset: int, conn) -> OrderSelect:
    """通用状态查询函数"""
    cursor = conn.cursor()
    
    # 1. 统计总数
    cursor.execute("SELECT COUNT(*) AS total FROM Orders WHERE order_status = %s AND is_deleted = 0", (status_value,))
    total = cursor.fetchone()["total"]

    # 2. 分页查询数据 (如果是已完成状态，需要关联 CompletedOrder)
    

    query = """
        SELECT order_id, origin, destination, weight, volume, 
                order_status AS status, vehicle_id, NULL AS completed_at
        FROM Orders
        WHERE order_status = %s
        ORDER BY order_id
        OFFSET %s ROWS FETCH NEXT %s ROWS ONLY
    """
    
    cursor.execute(query, (status_value, offset, limit))
    rows = cursor.fetchall()
    data = [Order(**r) for r in rows]
    return OrderSelect(data=data, total=total)

# --- 路由接口实现 ---

@router.get("/api/orders/pending", response_model=OrderSelect)
def get_orders_pending(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0), conn=Depends(get_db)):
    return select_orders_by_status("待处理", limit, offset, conn)
# loading
@router.get("/api/orders/loading", response_model=OrderSelect)
def get_orders_loading(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0), conn=Depends(get_db)):
    return select_orders_by_status("装货中", limit, offset, conn)
# 运输中
@router.get("/api/orders/transit", response_model=OrderSelect)
def get_orders_in_transit(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0), conn=Depends(get_db)):
    return select_orders_by_status("运输中", limit, offset, conn)
@router.get("/api/orders/done", response_model=OrderSelect)
def get_orders_done(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0), conn=Depends(get_db)):
    return select_orders_by_status("已完成", limit, offset, conn)

@router.get("/api/orders/cancelled", response_model=OrderSelect)
def get_orders_cancelled(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0), conn=Depends(get_db)):
    return select_orders_by_status("已取消", limit, offset, conn)

@router.post("/api/orders", status_code=status.HTTP_201_CREATED)
def insert_order(order: OrderCreate, conn=Depends(get_db)):
    """创建新订单"""
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO Orders (weight, volume, origin, destination, order_status, vehicle_id) 
               VALUES (%s, %s, %s, %s, %s, %s);""",
            (order.weight, order.volume, order.origin, order.destination, order.status, order.vehicle_id)
        )
        # 获取 SQL Server 自动生成的 ID
        cursor.execute("SELECT SCOPE_IDENTITY() AS order_id;")
        order_id = int(cursor.fetchone()["order_id"])
        conn.commit()
        return {"detail": "订单创建成功", "order_id": order_id}
    except Exception as e:
        conn.rollback()
        # 捕获触发器抛出的 RAISERROR (如超载)
        if "超出最大载重" in str(e):
             raise HTTPException(status_code=400, detail="分配失败：车辆剩余载重不足")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")

@router.delete("/api/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_order(order_id: int, conn=Depends(get_db)):
    """逻辑删除或取消订单"""
    cursor = conn.cursor()
    cursor.execute("UPDATE Orders SET order_status = '已取消', is_deleted = 1 WHERE order_id = %s", (order_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="未找到该订单")
    conn.commit()
    return {"detail": "订单已取消"}

@router.get("/api/drivers/{person_id}/orders", response_model=OrderSelect)
def get_driver_finished_orders(
    person_id: int,
    start: str | None = Query(None),
    end: str | None = Query(None),
    limit: int = Query(10, ge=1),
    offset: int = Query(0, ge=0),
    auth_info=Depends(require_admin_manager_or_driver_self),
    conn=Depends(get_db)
):
    """查询特定司机的历史完成订单"""
    cursor = conn.cursor()
    
    # 构造动态 SQL 过滤时间
    base_query = """
        FROM Orders o
        INNER JOIN CompletedOrder c ON o.order_id = c.order_id
        WHERE c.person_id = %s AND o.is_deleted = 0
    """
    params = [person_id]
    if start:
        base_query += " AND c.completed_at >= %s"
        params.append(start)
    if end:
        base_query += " AND c.completed_at <= %s"
        params.append(end)

    # 1. 统计总数
    cursor.execute(f"SELECT COUNT(*) AS total {base_query}", tuple(params))
    total = cursor.fetchone()["total"]

    # 2. 查询明细
    query = f"""
        SELECT o.order_id, o.origin, o.destination, o.weight, o.volume, 
               o.order_status AS status, o.vehicle_id, c.completed_at
        {base_query}
        ORDER BY c.completed_at DESC
        OFFSET %s ROWS FETCH NEXT %s ROWS ONLY
    """
    params.extend([offset, limit])
    cursor.execute(query, tuple(params))
    
    rows = cursor.fetchall()
    return OrderSelect(data=[Order(**r) for r in rows], total=total)


@router.patch("/api/orders/{order_id}")
def assign_order(order_id: int, order: OrderUpdate, conn=Depends(get_db)):
    """将订单分配给车辆"""
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Orders SET vehicle_id = %s, order_status = %s WHERE order_id = %s and order_status = '待处理'",
            (order.vehicle_id, "装货中", order_id)
        )
        # 
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="未找到该订单或订单已被删除")
        # 更改汽车的状态为“装货中”
        conn.commit()
        return {"detail": "订单分配成功"}
    except Exception as e:
        conn.rollback()
        # 捕获触发器抛出的 RAISERROR (如超载)
        if "超出最大载重" in str(e):
             raise HTTPException(status_code=400, detail="分配失败：车辆剩余载重不足")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
