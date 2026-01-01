USE FleetSync;
GO

CREATE TRIGGER trg_UpdateVehicleToLoading
ON Orders
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF TRIGGER_NESTLEVEL() > 1 RETURN; -- 防递归
    -- 检查是否更新了 order_status 字段
    IF UPDATE(order_status)
    BEGIN
        -- 更新关联车辆的状态
        -- 逻辑：当订单状态从'待处理'变为'装货中'，且关联车辆当前为'空闲'时触发
        UPDATE v
        SET v.vehicle_status = N'装货中'
        FROM Vehicles v
        INNER JOIN inserted i ON v.vehicle_id = i.vehicle_id
        INNER JOIN deleted d ON i.order_id = d.order_id
        WHERE d.order_status = N'待处理'      -- 更新前状态
          AND i.order_status = N'装货中'      -- 更新后状态
          AND v.vehicle_status = N'空闲'     -- 前提条件：车辆必须空闲
          AND v.is_deleted = 0;             -- 排除逻辑删除的车辆

        -- 可选：如果车辆不是空闲状态，可以根据需求决定是否抛出错误（RAISERROR）
        -- 但通常此类自动流转建议保持静默更新，或通过存储过程预先检查。
    END
END;
GO

CREATE TRIGGER trg_AuditDriverKeyInfo
ON Drivers
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF TRIGGER_NESTLEVEL() > 1 RETURN; -- 防递归
    -- 检查关键字段中是否有任意一个被更新
    IF UPDATE(driver_license) OR UPDATE(person_contact) OR UPDATE(person_name)
    BEGIN
        INSERT INTO History_Log (table_name, target_id, old_data, change_time)
        SELECT 
            'Drivers', 
            CAST(d.person_id AS NVARCHAR(20)), 
            -- 记录变更前的完整旧数据
            'Name: ' + d.person_name + 
            ' | Contact: ' + ISNULL(d.person_contact, 'N/A') + 
            ' | License: ' + d.driver_license,
            GETDATE()
        FROM deleted d;
    END
END;
GO
CREATE TRIGGER trg_IncidentHandle_UpdateVehicleStatus
ON Incidents
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF TRIGGER_NESTLEVEL() > 1 RETURN; -- 防递归
    -- 只有处理状态从“未处理”变为“已处理”时触发
    IF UPDATE(handle_status)
    BEGIN
        -- 使用 CTE 或子查询判断车辆应回流的状态
        UPDATE v
        SET v.vehicle_status = 
            CASE 
                -- 如果该车目前还有其他正在进行的运单，则流转回“运输中”
                WHEN EXISTS (SELECT 1 FROM Orders o WHERE o.vehicle_id = v.vehicle_id AND o.order_status IN ('装货中', '运输中')) 
                THEN '运输中'
                -- 否则流转回“空闲”
                ELSE '空闲'
            END
        FROM Vehicles v
        JOIN inserted i ON v.vehicle_id = i.vehicle_id
        WHERE i.handle_status = '已处理' 
          AND v.vehicle_status = '异常'; -- 只有当前处于异常状态的车辆才执行此逻辑
    END
END;
GO

CREATE TRIGGER trg_CheckOverload
ON Orders
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    -- 检查新插入或修改后的运单是否导致超载
    -- 利用创建的View_VehicleResourceStatus视图来简化逻辑
    IF EXISTS (
        SELECT 1 
        FROM View_VehicleResourceStatus rs
        WHERE rs.remaining_weight < 0 OR rs.remaining_volume < 0
    )
    BEGIN
        -- 拒绝操作并回滚 
        RAISERROR ('超出最大载重或容积：该操作已被拒绝！', 16, 1);
        ROLLBACK TRANSACTION;
    END
END;
GO

CREATE TRIGGER trg_SyncOrderToTransit
ON Vehicles
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF TRIGGER_NESTLEVEL() > 1 RETURN; -- 防递归
    -- 检查是否有实际的行被更新（排除虚拟更新）
    IF NOT EXISTS (SELECT 1 FROM inserted) OR NOT EXISTS (SELECT 1 FROM deleted)
        RETURN;

    -- 1. 检查是否更新了 vehicle_status 字段
    IF UPDATE(vehicle_status)
    BEGIN
        -- 2. 同步更新订单状态
        -- 逻辑：当车辆状态变更为 '运输中'，
        -- 将该车辆下所有处于 '装货中' 的订单同步更新为 '运输中'
        UPDATE o
        SET o.order_status = N'运输中'
        FROM Orders o
        INNER JOIN inserted i ON o.vehicle_id = i.vehicle_id
        INNER JOIN deleted d ON i.vehicle_id = d.vehicle_id
        WHERE i.vehicle_status = N'运输中'     -- 更新后的车辆状态
          AND d.vehicle_status = N'装货中'     -- 更新前的车辆状态（确保是从装货完成到出发）
          AND o.order_status = N'装货中'       -- 仅针对正在装货的订单
          AND o.is_deleted = 0;
    END
END;
GO

-- 当车辆状态从“运输中”变为“空闲”时，自动将该车辆下所有“运输中”的订单更新为“已完成”，同时
CREATE or ALTER TRIGGER trg_CompleteOrderOnVehicleIdle
ON Vehicles
AFTER UPDATE
AS BEGIN
    SET NOCOUNT ON;
    IF TRIGGER_NESTLEVEL() > 1 RETURN; -- 防递归

    -- 检查是否更新了 vehicle_status 字段
    IF UPDATE(vehicle_status)
    BEGIN
        -- 定义表变量，用于暂存本次真正被更新的订单
        DECLARE @JustFinishedOrders TABLE (
            order_id INT,
            vehicle_id NVARCHAR(50) -- 请确保长度与数据库定义一致
        );

        -- 1. 更新订单状态，同时将受影响的订单ID输出到表变量中
        UPDATE o
        SET o.order_status = N'已完成'
        OUTPUT inserted.order_id, inserted.vehicle_id INTO @JustFinishedOrders(order_id, vehicle_id)
        FROM Orders o
        INNER JOIN inserted i ON o.vehicle_id = i.vehicle_id
        INNER JOIN deleted d ON i.vehicle_id = d.vehicle_id
        WHERE i.vehicle_status = N'空闲'        -- 更新后的车辆状态
          AND d.vehicle_status = N'运输中'      -- 更新前的车辆状态
          AND o.order_status = N'运输中';       -- 仅针对正在运输的订单

        -- 2. 仅为刚刚完成的订单插入记录
        INSERT INTO CompletedOrder (order_id, person_id, completed_at)
        SELECT fo.order_id, a.person_id, CAST(GETDATE() AS DATE)
        FROM @JustFinishedOrders fo
        INNER JOIN Assignments a ON fo.vehicle_id = a.vehicle_id;
    END
END;
GO
-- 当某个订单取消的时候，检查该订单对应的车辆是否还有其他未完成的订单，如果没有，则将车辆状态改为“空闲”
CREATE TRIGGER trg_SetVehicleIdleOnOrderCancel
ON Orders
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF TRIGGER_NESTLEVEL() > 1 RETURN; -- 防递归
    -- 检查是否更新了 order_status 字段
    IF UPDATE(order_status)
    BEGIN
        -- 对于每个被取消订单的车辆，检查是否还有其他未完成订单
        DECLARE @VehicleID NVARCHAR(10);

        DECLARE CancelledOrdersCursor CURSOR FOR
        SELECT i.vehicle_id
        FROM inserted i
        INNER JOIN deleted d ON i.order_id = d.order_id
        WHERE d.order_status <> N'已取消' AND i.order_status = N'已取消';

        OPEN CancelledOrdersCursor;
        FETCH NEXT FROM CancelledOrdersCursor INTO @VehicleID;

        WHILE @@FETCH_STATUS = 0
        BEGIN
            -- 检查该车辆是否还有其他未完成订单
            IF NOT EXISTS (
                SELECT 1
                FROM Orders o
                WHERE o.vehicle_id = @VehicleID
                  AND o.order_status NOT IN (N'已完成', N'已取消')
                  AND o.is_deleted = 0
            )
            BEGIN
                -- 将车辆状态更新为“空闲”
                UPDATE Vehicles
                SET vehicle_status = N'空闲'
                WHERE vehicle_id = @VehicleID
                  AND is_deleted = 0;
            END

            FETCH NEXT FROM CancelledOrdersCursor INTO @VehicleID;
        END

        CLOSE CancelledOrdersCursor;
        DEALLOCATE CancelledOrdersCursor;
    END
END;

GO
CREATE TRIGGER trg_IncidentHandle_SyncVehicleStatus
ON Incidents
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    -- 只有当处理状态从“未处理”变为“已处理”时才触发
    IF UPDATE(handle_status)
    BEGIN
        -- 针对当前更新的每一条异常记录进行联动
        UPDATE v
        SET v.vehicle_status = 
            CASE 
                -- 逻辑 A：如果是运输中出的异常，处理完后恢复为“运输中”
                WHEN i.incident_type = N'运输中异常' THEN N'运输中'
                -- 逻辑 B：如果是空闲时出的异常，处理完后恢复为“空闲”
                WHEN i.incident_type = N'空闲时异常' THEN N'空闲'
                -- 兜底逻辑：如果不明确，根据订单表是否有未完成订单来判断
                ELSE 
                    CASE 
                        WHEN EXISTS (SELECT 1 FROM Orders o WHERE o.vehicle_id = v.vehicle_id AND o.order_status IN (N'装货中', N'运输中')) 
                        THEN N'运输中' 
                        ELSE N'空闲' 
                    END
            END
        FROM Vehicles v
        INNER JOIN inserted i ON v.vehicle_id = i.vehicle_id
        INNER JOIN deleted d ON i.incident_id = d.incident_id
        WHERE d.handle_status = N'未处理' 
          AND i.handle_status = N'已处理'
          AND v.vehicle_status = N'异常'; -- 只有当前车辆确实在“异常”状态才执行回转
    END
END;
GO