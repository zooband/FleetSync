USE FleetSync;
GO


IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_Vehicles_Optimization')
    DROP INDEX IX_Vehicles_Optimization ON Vehicles;
GO


PRINT '========= 优化前：全表扫描 (Table Scan) =========';
SET STATISTICS IO ON;
GO

-- 模拟调度员查询：在特定车队中寻找所有空闲车辆
-- 我们查询 vehicle_id, vehicle_status 和 max_weight
SELECT vehicle_id, vehicle_status, max_weight 
FROM Vehicles 
WHERE fleet_id = 1 AND vehicle_status = N'空闲';
GO

SET STATISTICS IO OFF;
GO


PRINT '--------- 正在建立覆盖索引 ---------';
CREATE INDEX IX_Vehicles_Optimization 
ON Vehicles (fleet_id, vehicle_status) 
INCLUDE (vehicle_id, max_weight); 
GO


PRINT '========= 优化后：索引查找 + 覆盖 (Index Seek) =========';
SET STATISTICS IO ON;
GO

SELECT vehicle_id, vehicle_status, max_weight 
FROM Vehicles 
WHERE fleet_id = 1 AND vehicle_status = N'空闲';
GO

SET STATISTICS IO OFF;
GO


/*-- 1. 为车辆表的状态和车牌号建立索引
CREATE INDEX IX_Vehicles_Status_ID ON Vehicles (vehicle_status, vehicle_id);

-- 2. 为订单表的订单状态建立索引
CREATE INDEX IX_Orders_Status ON Orders (order_status);

-- 3. 为异常记录的时间和车辆 ID 建立索引
CREATE INDEX IX_Incidents_Time_Vehicle ON Incidents (occurrence_time, vehicle_id);*/