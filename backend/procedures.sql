USE FleetSync;
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

    -- 2. 统计该车队在该月内发生的异常，排除掉已取消的异常
    SELECT 
        @TotalIncidents = COUNT(i.incident_id),
        @TotalFines = ISNULL(SUM(i.fine_amount), 0.00)
    FROM Incidents i
    JOIN Vehicles v ON i.vehicle_id = v.vehicle_id
    WHERE v.fleet_id = @FleetID 
      AND YEAR(i.occurrence_time) = @Year 
      AND MONTH(i.occurrence_time) = @Month
      AND i.is_deleted = 0;

    -- 3. 返回结果集
    SELECT 
        @TotalOrders AS Total_Orders,
        @TotalIncidents AS Total_Incidents,
        @TotalFines AS Total_Fine_Amount;
END;
GO