from typing import Any

# 全局“模拟数据库”（调试用）
drivers_db: list[Any] = []
vehicles_db: list[Any] = []
orders_db: list[Any] = []
incidents_db: list[Any] = []
fleets_db: list[Any] = []
distributioncenters_db: list[Any] = []
personnel_db: list[Any] = []
managers_db: list[Any] = []

_next_person_id = 1
_next_driver_id = 1
_next_order_id = 1
_next_incident_id = 1
_next_fleet_id = 1
_next_distributioncenter_id = 1


def get_next_driver_id() -> int:
    global _next_driver_id
    v = _next_driver_id
    _next_driver_id += 1
    return v


def get_next_order_id() -> int:
    global _next_order_id
    v = _next_order_id
    _next_order_id += 1
    return v


def get_next_incident_id() -> int:
    global _next_incident_id
    v = _next_incident_id
    _next_incident_id += 1
    return v


def get_next_fleet_id() -> int:
    global _next_fleet_id
    v = _next_fleet_id
    _next_fleet_id += 1
    return v


def get_next_distributioncenter_id() -> int:
    global _next_distributioncenter_id
    v = _next_distributioncenter_id
    _next_distributioncenter_id += 1
    return v


def get_next_person_id() -> int:
    global _next_person_id
    v = _next_person_id
    _next_person_id += 1
    return v
