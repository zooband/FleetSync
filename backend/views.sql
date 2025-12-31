USE FleetSync;
GO

CREATE VIEW View_VehicleResourceStatus AS
SELECT 
    v.vehicle_id,
    v.max_weight,
    v.max_volume,
    ISNULL(SUM(CASE WHEN o.order_status NOT IN ('已取消', '已完成', '待处理') THEN o.weight ELSE 0 END), 0) AS used_weight,
    ISNULL(SUM(CASE WHEN o.order_status NOT IN ('已取消', '已完成', '待处理') THEN o.volume ELSE 0 END), 0) AS used_volume,
    v.max_weight - ISNULL(SUM(CASE WHEN o.order_status NOT IN ('已取消', '已完成', '待处理') THEN o.weight ELSE 0 END), 0) AS remaining_weight,
    v.max_volume - ISNULL(SUM(CASE WHEN o.order_status NOT IN ('已取消', '已完成', '待处理') THEN o.volume ELSE 0 END), 0) AS remaining_volume, --订单完成后不用再手动更改车辆的剩余载重和体积，因为视图会动态计算
    v.fleet_id,
    v.vehicle_status,
    d.person_name AS driver_name
FROM Vehicles v
LEFT JOIN Orders o ON v.vehicle_id = o.vehicle_id
LEFT JOIN Assignments a ON v.vehicle_id = a.vehicle_id
LEFT JOIN Drivers d ON a.person_id = d.person_id
WHERE v.is_deleted = 0
GROUP BY v.vehicle_id, v.max_weight, v.max_volume, d.person_name, v.fleet_id, v.vehicle_status;
GO

CREATE VIEW View_WeeklyIncidentAlert AS
SELECT 
    f.fleet_name AS [车队名称],
    v.vehicle_id AS [车牌号],
    v.vehicle_status AS [车辆当前状态],
    d.person_name AS [司机姓名],
    d.person_contact AS [司机联系方式],
    i.incident_type AS [异常类型],
    i.incident_description AS [异常描述],
    i.fine_amount AS [罚款金额],
    i.occurrence_time AS [发生时间],
    i.handle_status AS [处理状态]
FROM Incidents i
JOIN Vehicles v ON i.vehicle_id = v.vehicle_id
JOIN Fleets f ON v.fleet_id = f.fleet_id
-- 通过 Assignments 表找到当前车辆绑定的司机
LEFT JOIN Assignments a ON v.vehicle_id = a.vehicle_id
LEFT JOIN Drivers d ON a.person_id = d.person_id
WHERE 
    -- 筛选本周的数据
    DATEDIFF(week, i.occurrence_time, GETDATE()) = 0;

GO