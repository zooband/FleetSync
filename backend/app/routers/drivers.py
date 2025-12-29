from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app import schemas, store

router = APIRouter()


class DriverCreate(BaseModel):
    person_id: int
    driver_license: str


class DriversResponse(BaseModel):
    data: list[schemas.Driver]
    total: int


@router.post("/api/personnels/drivers", response_model=schemas.Driver, status_code=status.HTTP_201_CREATED)
def insert_driver(driver: DriverCreate):
    target_person: schemas.Personnel | None = None
    for p in store.personnel_db:
        if p.person_id == driver.person_id:
            target_person = p
            p.person_role = "司机"
            break
    if target_person is None:
        raise HTTPException(status_code=404, detail="Personnel not found")

    new_driver = schemas.Driver(
        person_id=target_person.person_id,
        person_name=target_person.person_name,
        person_role="司机",
        person_contact=target_person.person_contact,
        driver_license=driver.driver_license,
        driver_status="空闲",
        fleet_id=-1,
    )
    store.drivers_db.append(new_driver)
    return new_driver


@router.get("/api/personnels/drivers", response_model=DriversResponse)
def get_drivers(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    filtered = store.drivers_db
    total = len(filtered)
    paginated = filtered[offset : offset + limit]
    return DriversResponse(data=paginated, total=total)


@router.patch("/api/personnels/drivers/{driver_id}", response_model=schemas.Driver)
def update_driver(driver_id: int, updates: schemas.DriverOptional):
    for i, driver in enumerate(store.drivers_db):
        if driver.person_id == driver_id:
            update_data = updates.model_dump(exclude_unset=True)
            updated_driver = driver.model_copy(update=update_data)
            store.drivers_db[i] = updated_driver
            return updated_driver
    raise HTTPException(status_code=404, detail="Driver not found")


@router.delete("/api/personnels/drivers/{driver_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_driver(driver_id: int):
    found = False
    for i, driver in enumerate(store.drivers_db):
        if driver.person_id == driver_id:
            store.drivers_db.pop(i)
            found = True
            break
    for i, p in enumerate(store.personnel_db):
        if p.person_id == driver_id:
            store.personnel_db.pop(i)
            found = True
            break
    if found:
        return
    raise HTTPException(status_code=404, detail="Driver not found")
