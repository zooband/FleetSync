from datetime import date

from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel

from app.auth_core import require_admin, require_admin_or_fleet_manager, require_admin_or_vehicle_fleet_manager
from app.db import get_db

router = APIRouter()


class Vehicle(BaseModel):
    vehicle_id: str
    vehicle_load_capacity: float
    vehicle_volume_capacity: float
    vehicle_status: str
    fleet_id: int | None = None
    driver_id: str | None = None


class VehiclesSelect(BaseModel):
    data: list[Vehicle]
    total: int


class VehicleUpdate(Vehicle):
    driver_name: str | None = None
    fleet_name: str | None = None
    remaining_load_capacity: float | None = None
    remaining_volume_capacity: float | None = None
    active_order_id: int | None = None
    active_order_status: str | None = None


class VehicleCreate(BaseModel):
    vehicle_id: str
    vehicle_load_capacity: float
    vehicle_volume_capacity: float
    fleet_id: int | None = None


@router.post("/api/fleets/{fleet_id}/vehicles", status_code=status.HTTP_201_CREATED)
def insert_vehicle(fleet_id: int, vehicle: VehicleCreate, auth_info=Depends(require_admin), conn=Depends(get_db)):
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Vehicles (vehicle_id, max_weight, max_volume, vehicle_status, fleet_id) VALUES (%s, %s, %s, %s, %s);",
            (vehicle.vehicle_id, vehicle.vehicle_load_capacity, vehicle.vehicle_volume_capacity, "空闲", fleet_id),
        )
        conn.commit()
        return {"detail": "车辆创建成功", "vehicle_id": vehicle.vehicle_id}
    except Exception as e:
        conn.rollback()
        if hasattr(e, 'args') and len(e.args) > 0 and "2627" in str(e.args[0]):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"车辆 ID '{vehicle.vehicle_id}' 已存在"
            )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"创建车辆失败: {e}") from e


@router.patch("/api/vehicles/{vehicle_id}", status_code=status.HTTP_201_CREATED)
def update_vehicle(vehicle_id: str, updates: VehicleUpdate, auth_info=Depends(require_admin), conn=Depends(get_db)):
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        return {"message": "没有提供更新内容"}
    
    try:
        cursor = conn.cursor()
        set_clause = ", ".join(f"{k} = %s" for k in update_data)
        update_values = list(update_data.values())
        cursor.execute(
            f"UPDATE Vehicles SET {set_clause} WHERE vehicle_id = %s AND is_deleted = 0",
            update_values + [vehicle_id],
        )
        conn.commit()
        return {"message": "车辆信息更新成功"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/api/vehicles/{vehicle_id}/info", response_model=Vehicle)
def get_vehicle(
    vehicle_id: str,
    auth_info=Depends(require_admin_or_vehicle_fleet_manager),
    conn=Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute("SELECT vehicle_id, max_weight AS vehicle_load_capacity, max_volume AS vehicle_volume_capacity, vehicle_status, fleet_id, driver_id FROM Vehicles WHERE vehicle_id = %s AND is_deleted = 0", (vehicle_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到车辆记录")
    return Vehicle(**row)


@router.post("/api/vehicles/{vehicle_id}/depart")
def depart_vehicle(vehicle_id: str):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="此接口尚未实现")


@router.post("/api/vehicles/{vehicle_id}/deliver")
def deliver_vehicle(vehicle_id: str):  # 分配订单给车辆
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="此接口尚未实现")
    # TODO: 实现此接口


@router.delete("/api/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(vehicle_id: str):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="此接口尚未实现")
    # TODO: 实现此接口


@router.get("/api/distribution-centers/{center_id}/vehicle-resources", response_model=Vehicle)
def get_vehicles_of_center(center_id: int, auth_info=Depends(require_admin), conn=Depends(get_db)):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="此接口尚未实现")
    # TODO: 实现此接口


@router.get("/api/fleets/{fleet_id}/vehicles")
def get_vehicles_of_fleet(
    fleet_id: int,
    q: str | None = Query(""), 
    limit: int = Query(10, ge=1), 
    offset: int = Query(0, ge=0), 
    auth_info=Depends(require_admin_or_fleet_manager), 
    conn=Depends(get_db)
):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM Vehicles WHERE fleet_id = %s AND is_deleted = 0 AND (vehicle_id LIKE %s)", (fleet_id, f"%{q}%"))
    total = cursor.fetchone()["total"]

    cursor.execute("SELECT v.vehicle_id, max_weight AS vehicle_load_capacity, max_volume AS vehicle_volume_capacity, vehicle_status, fleet_id, person_id AS driver_id FROM Vehicles v LEFT JOIN Assignments a ON v.vehicle_id = a.vehicle_id WHERE fleet_id = %s AND is_deleted = 0 AND (v.vehicle_id LIKE %s) ORDER BY v.vehicle_id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY", (fleet_id, f"%{q}%", offset, limit))
    rows = cursor.fetchall()
    data = [Vehicle(**r) for r in rows]

    return VehiclesSelect(data=data, total=total)
