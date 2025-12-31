CREATE VIEW View_VehicleResourceStatus AS
SELECT 
    v.vehicle_id,
    v.max_weight,
    v.max_volume,
    ISNULL(SUM(CASE WHEN o.order_status NOT IN ('已取消', '已完成', '待处理') THEN o.weight ELSE 0 END), 0) AS used_weight,
    ISNULL(SUM(CASE WHEN o.order_status NOT IN ('已取消', '已完成', '待处理') THEN o.volume ELSE 0 END), 0) AS used_volume,
    v.max_weight - ISNULL(SUM(CASE WHEN o.order_status NOT IN ('已取消', '已完成', '待处理') THEN o.weight ELSE 0 END), 0) AS remaining_weight,
    v.max_volume - ISNULL(SUM(CASE WHEN o.order_status NOT IN ('已取消', '已完成', '待处理') THEN o.volume ELSE 0 END), 0) AS remaining_volume,
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
    i.descript AS [异常描述],
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

CREATE PROCEDURE GetFleetMonthlyPerformance
    @FleetID INT,
    @Year INT,
    @Month INT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @TotalOrders INT = 0;
    DECLARE @TotalIncidents INT = 0;
    DECLARE @TotalFines DECIMAL(10, 2) = 0.00;

    -- 1. 从 CompletedOrder 统计该车队在该月内已完成的运单总数
    SELECT @TotalOrders = COUNT(co.order_id)
    FROM CompletedOrder co
    JOIN Orders o ON co.order_id = o.order_id
    JOIN Vehicles v ON o.vehicle_id = v.vehicle_id
    WHERE v.fleet_id = @FleetID 
      AND YEAR(co.completed_at) = @Year 
      AND MONTH(co.completed_at) = @Month;

    -- 2. 统计该车队在该月内发生的异常
    SELECT 
        @TotalIncidents = COUNT(i.incident_id),
        @TotalFines = ISNULL(SUM(i.fine_amount), 0.00)
    FROM Incidents i
    JOIN Vehicles v ON i.vehicle_id = v.vehicle_id
    WHERE v.fleet_id = @FleetID 
      AND YEAR(i.occurrence_time) = @Year 
      AND MONTH(i.occurrence_time) = @Month;

    -- 3. 返回结果集
    SELECT 
        @TotalOrders AS Total_Orders,
        @TotalIncidents AS Total_Incidents,
        @TotalFines AS Total_Fine_Amount;
END;
GO

