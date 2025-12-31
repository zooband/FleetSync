from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel

from app.auth_core import require_admin, require_admin_or_fleet_manager, require_admin_or_vehicle_fleet_manager
from app.db import get_db

router = APIRouter()


class Vehicle(BaseModel):
    vehicle_id: str
    max_weight: float
    max_volume: float
    remaining_weight: float | None = None
    remaining_volume: float | None = None
    vehicle_status: str
    fleet_id: int | None = None
    driver_name: str | None = None


class VehiclesSelect(BaseModel):
    data: list[Vehicle]
    total: int


class VehicleUpdate(BaseModel):
    vehicle_id: str | None = None
    max_weight: float | None = None
    max_volume: float | None = None


class VehicleCreate(BaseModel):
    vehicle_id: str
    max_weight: float
    max_volume: float
    fleet_id: int | None = None


@router.post("/api/fleets/{fleet_id}/vehicles", status_code=status.HTTP_201_CREATED)
def insert_vehicle(fleet_id: int, vehicle: VehicleCreate, auth_info=Depends(require_admin), conn=Depends(get_db)):
    try:
        cursor = conn.cursor(as_dict=False)

        cursor.execute(
            "SELECT 1 FROM Fleets WHERE fleet_id = %s AND is_deleted = 0",
            (fleet_id,),
        )
        if cursor.fetchone() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"找不到ID为 {fleet_id} 的车队")

        cursor.execute(
            "SELECT 1 FROM Vehicles WHERE vehicle_id = %s AND is_deleted = 0",
            (vehicle.vehicle_id,),
        )
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"车辆ID {vehicle.vehicle_id} 已存在，无法重复创建")

        cursor.execute("""
            MERGE Vehicles AS target
            USING (SELECT %s AS vehicle_id, %s AS max_weight, %s AS max_volume, %s AS vehicle_status, %s AS fleet_id) AS source
            ON target.vehicle_id = source.vehicle_id
            WHEN MATCHED AND target.is_deleted = 1 THEN
                UPDATE SET
                    max_weight = source.max_weight,
                    max_volume = source.max_volume,
                    vehicle_status = source.vehicle_status,
                    fleet_id = source.fleet_id,
                    is_deleted = 0
            WHEN NOT MATCHED THEN
                INSERT (vehicle_id, max_weight, max_volume, vehicle_status, fleet_id, is_deleted)
                VALUES (source.vehicle_id, source.max_weight, source.max_volume, source.vehicle_status, source.fleet_id, 0);
        """, (vehicle.vehicle_id, vehicle.max_weight, vehicle.max_volume, "空闲", fleet_id))
        conn.commit()
        return {"detail": "车辆创建成功", "vehicle_id": vehicle.vehicle_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"创建车辆失败: {e}") from e


@router.patch("/api/vehicles/{vehicle_id}", status_code=status.HTTP_201_CREATED)
def update_vehicle(vehicle_id: str, updates: VehicleUpdate, auth_info=Depends(require_admin), conn=Depends(get_db)):
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        return {"detail": "没有提供更新内容"}
    
    try:
        cursor = conn.cursor()
        set_clause = ", ".join(f"{k} = %s" for k in update_data)
        update_values = list(update_data.values())
        cursor.execute(
            f"UPDATE Vehicles SET {set_clause} WHERE vehicle_id = %s AND is_deleted = 0",
            update_values + [vehicle_id],
        )
        conn.commit()
        return {"detail": "车辆信息更新成功"}
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
    cursor.execute("SELECT vehicle_id, max_weight, max_volume, vehicle_status, fleet_id, driver_id FROM Vehicles WHERE vehicle_id = %s AND is_deleted = 0", (vehicle_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到车辆记录")
    return Vehicle(**row)


@router.post("/api/vehicles/{vehicle_id}/depart")
def depart_vehicle(vehicle_id: str, auth_info=Depends(require_admin_or_vehicle_fleet_manager), conn=Depends(get_db)):
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Vehicles SET vehicle_status = %s WHERE vehicle_id = %s AND is_deleted = 0",
            ("运输中", vehicle_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到车辆记录")
        conn.commit()
        return {"detail": "车辆已发车"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="车辆发车失败") from e



@router.delete("/api/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(vehicle_id: str, auth_info=Depends(require_admin), conn=Depends(get_db)):
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE Vehicles SET is_deleted = 1 WHERE vehicle_id = %s", (vehicle_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到车辆记录")
        conn.commit()
        return {"detail": "车辆已删除"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="删除车辆失败") from e
    
# 确认送达api，状态改为空闲
@router.post("/api/vehicles/{vehicle_id}/deliver")
def deliver_vehicle(vehicle_id: str, auth_info=Depends(require_admin_or_vehicle_fleet_manager), conn=Depends(get_db)):
    try:
        cursor = conn.cursor()
        # 更新车辆状态为空闲
        cursor.execute(
            "UPDATE Vehicles SET vehicle_status = %s WHERE vehicle_id = %s AND is_deleted = 0",
            ("空闲", vehicle_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到车辆记录")
        conn.commit()
        return {"detail": "车辆已送达，订单状态更新为已完成"}
    except Exception as e:
        # 打印报错信息以便调试
        print(f"Error occurred: {e}")
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="wtf车辆送达确认失败") from e

# 定义一个新的返回模型，匹配前端的 data.available 和 data.unavailable
class CenterVehicleResourcesResponse(BaseModel):
    available: list[Vehicle]
    unavailable: list[Vehicle]

@router.get("/api/distribution-centers/{center_id}/vehicle-resources", response_model=CenterVehicleResourcesResponse)
def get_vehicles_of_center(center_id: int, auth_info=Depends(require_admin), conn=Depends(get_db)):
    try:
        cursor = conn.cursor()
        query = """
            SELECT 
                rs.vehicle_id,
                rs.max_weight,
                rs.max_volume,
                rs.remaining_weight,
                rs.remaining_volume,
                v.vehicle_status,
                v.fleet_id
            FROM View_VehicleResourceStatus rs
            JOIN Vehicles v ON rs.vehicle_id = v.vehicle_id
            JOIN Fleets f ON v.fleet_id = f.fleet_id
            WHERE f.center_id = %s AND v.is_deleted = 0
        """
        cursor.execute(query, (center_id,))
        rows = cursor.fetchall()
        
        all_vehicles = [Vehicle(**r) for r in rows]

        # 核心逻辑：根据业务规则分类 
        # “可用”：状态为空闲或者装货中，且剩余载重 > 0
        # “不可用”：状态为异常、维修中或满载（剩余载重 <= 0）
        available = [v for v in all_vehicles if (v.vehicle_status == '空闲' and (v.remaining_weight or 0) > 0) or (v.vehicle_status == '装货中' and (v.remaining_weight or 0) > 0)]
        unavailable = [v for v in all_vehicles if v not in available]

        return {
            "available": available,
            "unavailable": unavailable
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


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
    cursor.execute("SELECT COUNT(*) AS total FROM View_VehicleResourceStatus WHERE fleet_id = %s AND (vehicle_id LIKE %s)", (fleet_id, f"%{q}%"))
    total = cursor.fetchone()["total"]

    cursor.execute("SELECT vehicle_id, max_weight, max_volume, remaining_weight, remaining_volume, vehicle_status, fleet_id, driver_name FROM View_VehicleResourceStatus WHERE fleet_id = %s AND (vehicle_id LIKE %s) ORDER BY vehicle_id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY", (fleet_id, f"%{q}%", offset, limit))
    rows = cursor.fetchall()
    data = [Vehicle(**r) for r in rows]

    return VehiclesSelect(data=data, total=total)


@router.get("/api/vehicles")
def get_vehicles(
    q: str | None = Query(""), 
    limit: int = Query(10, ge=1), 
    offset: int = Query(0, ge=0), 
    auth_info=Depends(require_admin), 
    conn=Depends(get_db)
):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM View_VehicleResourceStatus WHERE (vehicle_id LIKE %s)", (f"%{q}%",))
    total = cursor.fetchone()["total"]

    cursor.execute("SELECT vehicle_id, max_weight, max_volume, remaining_weight, remaining_volume, vehicle_status, fleet_id, driver_name FROM View_VehicleResourceStatus WHERE (vehicle_id LIKE %s) ORDER BY vehicle_id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY", (f"%{q}%", offset, limit))
    rows = cursor.fetchall()
    data = [Vehicle(**r) for r in rows]

    return VehiclesSelect(data=data, total=total)

@router.post("/api/vehicles/{vehicle_id}/driver")
def assign_or_free_driver_to_vehicle(
    vehicle_id: str,
    driver_id: str | None = Query(None, description="司机 ID，格式为 D+数字，如 D1；传入 null 表示解绑司机"),
    auth_info=Depends(require_admin_or_vehicle_fleet_manager),
    conn=Depends(get_db),
):
    cursor = conn.cursor(as_dict=False)

    # 兼容 query 传空字符串（例如 ?driver_id= ）：按未传处理
    driver_id = driver_id or None

    if driver_id:
        if not driver_id or driver_id[0].upper() != "D" or not driver_id[1:].isdigit():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="driver_id 格式错误，应为 D+数字（如 D1）")
        driver_person_id = int(driver_id[1:])

        cursor.execute("SELECT 1 FROM Assignments WHERE person_id = %s OR vehicle_id = %s", (driver_person_id, vehicle_id))
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该司机或车辆已被分配，无法重复分配")

        try:
            cursor.execute(
                "INSERT INTO Assignments (person_id, vehicle_id) VALUES (%s, %s)",
                (driver_person_id, vehicle_id),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到司机或车辆记录")
            conn.commit()
            return {"detail": "司机分配成功"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"分配司机失败: {e}") from e
    else:
        try:
            cursor.execute(
                "DELETE FROM Assignments WHERE vehicle_id = %s",
                (vehicle_id,),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到车辆记录或车辆未分配司机")
            conn.commit()
            return {"detail": "司机解绑成功"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="解绑司机失败") from e

