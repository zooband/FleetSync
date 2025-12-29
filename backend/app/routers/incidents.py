from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app import schemas, store

router = APIRouter()


class CreateIncident(BaseModel):
    driver_id: int
    vehicle_id: str
    timestamp: date
    type: str
    fine_amount: float
    description: str
    status: str | None = None


@router.post("/api/incidents", response_model=schemas.Incident, status_code=status.HTTP_201_CREATED)
def insert_incident(incident: CreateIncident):
    new_id = store.get_next_incident_id()
    new_incident = schemas.Incident(
        incident_id=new_id,
        driver_id=incident.driver_id,
        vehicle_id=incident.vehicle_id,
        timestamp=incident.timestamp,
        description=incident.description,
        type=incident.type,
        fine_amount=incident.fine_amount,
        status=incident.status or "未处理",
    )
    store.incidents_db.append(new_incident)
    return new_incident


class UpdateIncident(BaseModel):
    driver_id: int | None = None
    vehicle_id: str | None = None
    timestamp: date | None = None
    type: str | None = None
    fine_amount: float | None = None
    description: str | None = None
    status: str | None = None


@router.patch("/api/incidents/{incident_id}")
def update_incident_status(incident_id: int, updates: UpdateIncident):
    for i, inc in enumerate(store.incidents_db):
        if inc.incident_id == incident_id:
            update_data = updates.model_dump(exclude_unset=True)
            updated_incident = inc.model_copy(update=update_data)
            store.incidents_db[i] = updated_incident
            return updated_incident
    raise HTTPException(status_code=404, detail=f"找不到id为{incident_id}的异常记录")


class SelectIncident(BaseModel):
    data: list[schemas.Incident]
    total: int


@router.get("/api/incidents", response_model=SelectIncident)
def list_incidents(limit: int = Query(10, ge=1), offset: int = Query(0, ge=0)):
    return SelectIncident(data=store.incidents_db, total=len(store.incidents_db))


@router.delete("/api/incidents/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_incident(incident_id: int):
    for i, inc in enumerate(store.incidents_db):
        if inc.incident_id == incident_id:
            store.incidents_db.pop(i)
            return
    raise HTTPException(status_code=404, detail=f"找不到id为{incident_id}的异常记录")
