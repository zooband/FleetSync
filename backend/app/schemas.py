from datetime import date

from pydantic import BaseModel, Field


class DriverBase(BaseModel):
    driver_name: str
    driver_contact: str | None = None
    driver_license: str
    driver_status: str


class DriverOptional(BaseModel):
    driver_name: str | None = None
    driver_contact: str | None = None
    driver_license: str | None = None
    driver_status: str | None = None


class Vehicle(BaseModel):
    vehicle_id: str
    vehicle_load_capacity: float
    vehicle_volumn_capacity: float
    vehicle_status: str
    fleet_id: int | None = None
    driver_id: int | None = None


class VehicleView(Vehicle):
    driver_name: str | None = None
    fleet_name: str | None = None
    remaining_load_capacity: float | None = None
    remaining_volumn_capacity: float | None = None
    active_order_id: int | None = None
    active_order_status: str | None = None


class Order(BaseModel):
    order_id: int
    origin: str
    destination: str
    weight: float
    volume: float
    status: str  # ['待处理', '装货中', '运输中', '已完成', '已取消']
    vehicle_id: str | None = None
    created_at: date = Field(default_factory=date.today)
    completed_at: date | None = None


class Incident(BaseModel):
    incident_id: int
    driver_id: int
    vehicle_id: str
    timestamp: date
    type: str
    fine_amount: float
    description: str
    status: str


class Fleet(BaseModel):
    fleet_id: int
    fleet_name: str
    manager_id: int
    center_id: int
    manager_name: str


class DistributionCenter(BaseModel):
    center_id: int
    center_name: str


class Personnel(BaseModel):
    person_id: int
    person_name: str
    person_role: str
    person_contact: str | None = None


class Manager(Personnel):
    fleet_id: int


class Driver(Personnel):
    driver_license: str
    driver_status: str
    fleet_id: int
