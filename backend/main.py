from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import date


# 数据格式
class Driver(BaseModel):
    pass


class Vehicle(BaseModel):
    pass


class Order(BaseModel):
    pass


class Incident(BaseModel):
    pass


class Fleet(BaseModel):
    pass


app = FastAPI()


# 录入司机信息
@app.post("/drivers")
def insert_driver(driver: Driver):
    pass


# 查询司机信息
@app.get("/drivers/{driver_id}/info")
def get_driver(driver_id: int):
    pass


# 查询司机绩效
@app.get("/drivers/{driver_id}/performance")
def get_driver_performance(driver_id: int, start_date: date, end_date: date):
    pass


# 录入车辆信息
@app.post("/vehicles")
def insert_vehicle(vehicle: Vehicle):
    pass


# 查询空闲车辆
@app.get("/vehicles/available")
def get_available_vehicles():
    pass


# 查询车辆信息
@app.get("/vehicles/{vehicle_id}/info")
def get_vehicle(vehicle_id: int):
    pass


# 录入运单信息
@app.post("/orders")
def insert_order(order: Order):
    pass


# 运单分配
@app.post("/orders/{order_id}/assign")
def assign_order(order_id: int, vehicle_id: int):
    pass


# 录入异常信息
@app.post("/incidents")
def insert_incident(incident: Incident):
    pass


# 更新异常状态
@app.put("/incidents/{incident_id}")
def update_incident_status(incident_id: int, status: bool):
    pass


# 查询异常状态
@app.get("/incidents/{incident_id}")
def get_incident_status(incident_id: int):
    pass


# 录入车队信息
@app.post("/fleets")
def insert_fleet(fleet: Fleet):
    pass


# 将车辆分配到车队
@app.post("/fleets/{fleet_id}/assign_vehicle")
def assign_vehicle_to_fleet(fleet_id: int, vehicle_id: int):
    pass


# 查询车队资源
@app.get("/fleets/{fleet_id}/resources")
def get_fleet(fleet_id: int):
    pass


# 查询车队月度统计
@app.get("/fleets/{fleet_id}/monthly_stat")
def get_fleet_statistics(fleet_id: int, month: date):
    pass
