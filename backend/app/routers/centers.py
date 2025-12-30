from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.db import get_db
from app.auth_core import require_admin

router = APIRouter()


class DistributionCenter(BaseModel):
    center_id: int
    center_name: str


class DistributionCenterSelect(BaseModel):
    data: list[DistributionCenter]
    total: int


class DistributionCenterCreate(BaseModel):
    center_name: str


class DistributionCenterUpdate(BaseModel):
    center_name: str | None = None


@router.post("/api/distribution-centers", response_model=DistributionCenter, status_code=status.HTTP_201_CREATED)
def insert_distribution_center(center: DistributionCenterCreate, auth_info=Depends(require_admin), conn=Depends(get_db)):
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO DistributionCenters (center_name) VALUES (%s); SELECT SCOPE_IDENTITY() AS new_id;", (center.center_name,))
        new_id = int(cursor.fetchone()["new_id"])
        conn.commit()
        return {"detail": "配送中心创建成功", "center_id": new_id, "center_name": center.center_name}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="创建配送中心失败") from e


@router.get("/api/distribution-centers", response_model=DistributionCenterSelect)
def get_distribution_centers(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0), auth_info=Depends(require_admin), conn=Depends(get_db)):
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM DistributionCenters WHERE is_deleted = 0")
    total = cursor.fetchone()["total"]

    cursor.execute("SELECT center_id, center_name FROM DistributionCenters WHERE is_deleted = 0 ORDER BY center_id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY", (offset, limit))
    rows = cursor.fetchall()
    data = [DistributionCenter(**r) for r in rows]

    return DistributionCenterSelect(data=data, total=total)


@router.get("/api/distribution-centers/{center_id}", response_model=DistributionCenter)
def get_distribution_center(center_id: int, auth_info=Depends(require_admin), conn=Depends(get_db)):    
    cursor = conn.cursor()

    cursor.execute("SELECT center_id, center_name FROM DistributionCenters WHERE center_id = %s AND is_deleted = 0", (center_id,))
    row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"找不到配送中心 ID={center_id} 的记录")

    return DistributionCenter(**row)


@router.patch("/api/distribution-centers/{center_id}")
def update_distribution_center(center_id: int, updates: DistributionCenterUpdate, auth_info=Depends(require_admin), conn=Depends(get_db)):
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        return {"detail": "没有提供更新内容"}

    if update_data.get("center_name") is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="配送中心名不能为空")
    try:
        cursor = conn.cursor()
        set_clause = ", ".join(f"{k} = %s" for k in update_data)
        values = list(update_data.values()) + [center_id]
        cursor.execute(
            f"UPDATE DistributionCenters SET {set_clause} WHERE center_id = %s AND is_deleted = 0",
            values,
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"找不到配送中心 ID={center_id} 的记录")
        conn.commit()
        return {"detail": "配送中心信息更新成功"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="更新配送中心失败") from e


@router.delete("/api/distribution-centers/{center_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_distribution_center(center_id: int, auth_info=Depends(require_admin), conn=Depends(get_db)):
    cursor = conn.cursor(as_dict=False)
    cursor.execute("SELECT 1 FROM DistributionCenters WHERE center_id = %s AND is_deleted = 0", (center_id,))
    if cursor.fetchone() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"找不到配送中心 ID={center_id} 的记录")

    try:
        cursor.execute("UPDATE Fleets SET is_deleted = 1 WHERE center_id = %s AND is_deleted = 0", (center_id,))
        cursor.execute("UPDATE v SET v.is_deleted = 1 FROM Vehicles v JOIN Fleets f ON v.fleet_id = f.fleet_id WHERE f.center_id = %s AND v.is_deleted = 0", (center_id,))
        cursor.execute("UPDATE d SET d.is_deleted = 1 FROM Drivers d JOIN Fleets f ON d.fleet_id = f.fleet_id WHERE f.center_id = %s AND d.is_deleted = 0", (center_id,))
        cursor.execute("UPDATE m SET m.is_deleted = 1 FROM Managers m JOIN Fleets f ON m.fleet_id = f.fleet_id WHERE f.center_id = %s AND m.is_deleted = 0", (center_id,))
        cursor.execute("UPDATE DistributionCenters SET is_deleted = 1 WHERE center_id = %s AND is_deleted = 0", (center_id,))

        conn.commit()
        return {"detail": "配送中心删除成功"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="删除配送中心时发生错误") from e