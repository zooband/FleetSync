from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from app import schemas, store
from app.routers.orders import SelectOrder
from app.routers.incidents import SelectIncident

router = APIRouter()


class PersonnelSelect(BaseModel):
    data: list[schemas.Personnel]
    total: int


class PersonnelUpdate(BaseModel):
    person_name: str | None = None
    person_contact: str | None = None
    driver_license: str | None = None


@router.get("/api/personnels", response_model=PersonnelSelect)
def list_personnels(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    filtered = store.personnel_db
    total = len(filtered)
    paginated_data = filtered[offset : offset + limit]
    return PersonnelSelect(data=paginated_data, total=total)


@router.patch("/api/personnels/{person_id}", response_model=schemas.Personnel)
def update_personnel(person_id: int, updates: PersonnelUpdate, request: Request):
    # 按需求：只有 admin 可以编辑任何人员信息（包括本人）
    if getattr(getattr(request, "state", None), "auth", {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    update_data = updates.model_dump(exclude_unset=True)

    # driver_license 只能用于司机
    is_driver = any(d.person_id == person_id for d in store.drivers_db)
    if ("driver_license" in update_data) and (not is_driver):
        raise HTTPException(status_code=400, detail="仅司机可修改驾照等级")

    # 先更新 personnel_db（基础信息）
    p_idx = next((i for i, p in enumerate(store.personnel_db) if p.person_id == person_id), None)
    if p_idx is None:
        raise HTTPException(status_code=404, detail="Personnel not found")

    base_patch = {k: v for k, v in update_data.items() if k in ("person_name", "person_contact")}
    if base_patch:
        store.personnel_db[p_idx] = store.personnel_db[p_idx].model_copy(update=base_patch)

    # 同步更新 drivers_db / managers_db（它们是 Personnel 的子结构，GET 详情时会优先读取）
    if is_driver:
        d_idx = next((i for i, d in enumerate(store.drivers_db) if d.person_id == person_id), None)
        if d_idx is not None:
            driver_patch: dict[str, object] = {}
            if "person_name" in update_data:
                driver_patch["person_name"] = update_data["person_name"]
            if "person_contact" in update_data:
                driver_patch["person_contact"] = update_data["person_contact"]
            if "driver_license" in update_data:
                driver_patch["driver_license"] = update_data["driver_license"]
            if driver_patch:
                store.drivers_db[d_idx] = store.drivers_db[d_idx].model_copy(update=driver_patch)

    is_manager = any(m.person_id == person_id for m in store.managers_db)
    if is_manager:
        m_idx = next((i for i, m in enumerate(store.managers_db) if m.person_id == person_id), None)
        if m_idx is not None:
            manager_patch: dict[str, object] = {}
            if "person_name" in update_data:
                manager_patch["person_name"] = update_data["person_name"]
            if "person_contact" in update_data:
                manager_patch["person_contact"] = update_data["person_contact"]
            if manager_patch:
                store.managers_db[m_idx] = store.managers_db[m_idx].model_copy(update=manager_patch)

            # 同步车队表上的 manager_name（便于车队列表/详情直接展示）
            if "person_name" in update_data:
                for i, f in enumerate(store.fleets_db):
                    if getattr(f, "manager_id", None) == person_id:
                        store.fleets_db[i] = f.model_copy(update={"manager_name": update_data["person_name"]})

    return store.personnel_db[p_idx]


@router.delete("/api/personnels/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_personnel(person_id: int):
    for i, person in enumerate(store.personnel_db):
        if person.person_id == person_id:
            store.personnel_db.pop(i)
            return
    raise HTTPException(status_code=404, detail="Personnel not found")


def _get_fleet_name(fleet_id: int | None) -> str | None:
    if fleet_id is None:
        return None
    for f in store.fleets_db:
        if f.fleet_id == fleet_id:
            return f.fleet_name
    return None


def _get_driver_vehicle_id(driver_id: int) -> str | None:
    for v in store.vehicles_db:
        if v.driver_id == driver_id:
            return v.vehicle_id
    return None


@router.get("/api/personnels/{person_id}")
def get_personnel_info(person_id: int):
    for d in store.drivers_db:
        if d.person_id == person_id:
            data = d.model_dump()
            data["fleet_name"] = _get_fleet_name(getattr(d, "fleet_id", None))
            data["vehicle_id"] = _get_driver_vehicle_id(d.person_id)
            return data

    for m in store.managers_db:
        if m.person_id == person_id:
            data = m.model_dump()
            data["fleet_name"] = _get_fleet_name(getattr(m, "fleet_id", None))
            return data

    for person in store.personnel_db:
        if person.person_id == person_id:
            return person

    raise HTTPException(status_code=404, detail="Personnel not found")


def _parse_ymd(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


@router.get("/api/personnels/{person_id}/orders", response_model=SelectOrder)
def get_person_orders(
    person_id: int,
    start: str | None = Query(None),
    end: str | None = Query(None),
    limit: int = Query(10, ge=1),
    offset: int = Query(0, ge=0),
):
    start_d = _parse_ymd(start)
    end_d = _parse_ymd(end)

    driver = next((d for d in store.drivers_db if d.person_id == person_id), None)
    if driver is None:
        return SelectOrder(data=[], total=0)

    fid = getattr(driver, "fleet_id", None)
    if fid is None:
        return SelectOrder(data=[], total=0)

    fleet_vehicle_ids = {v.vehicle_id for v in store.vehicles_db if v.fleet_id == fid}
    filtered = [o for o in store.orders_db if o.vehicle_id is not None and o.vehicle_id in fleet_vehicle_ids]
    if start_d:
        filtered = [o for o in filtered if o.created_at >= start_d]
    if end_d:
        filtered = [o for o in filtered if o.created_at <= end_d]

    total = len(filtered)
    paginated = filtered[offset : offset + limit]
    return SelectOrder(data=paginated, total=total)


@router.get("/api/personnels/{person_id}/incidents", response_model=SelectIncident)
def get_person_incidents(
    person_id: int,
    start: str | None = Query(None),
    end: str | None = Query(None),
    limit: int = Query(10, ge=1),
    offset: int = Query(0, ge=0),
):
    start_d = _parse_ymd(start)
    end_d = _parse_ymd(end)

    filtered = [i for i in store.incidents_db if i.driver_id == person_id]
    if start_d:
        filtered = [i for i in filtered if i.timestamp >= start_d]
    if end_d:
        filtered = [i for i in filtered if i.timestamp <= end_d]

    total = len(filtered)
    paginated = filtered[offset : offset + limit]
    return SelectIncident(data=paginated, total=total)
