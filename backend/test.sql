USE [FleetSync];
GO

-----------------------------------------------------------
-- 1. 彻底清理旧数据，防止主键冲突
-----------------------------------------------------------
DELETE FROM CompletedOrder;
DELETE FROM Incidents;
DELETE FROM Assignments;
DELETE FROM Orders;
DELETE FROM Drivers;
DELETE FROM Vehicles;
DELETE FROM Fleets;
DELETE FROM DistributionCenters;
-- 重置自增 ID
DBCC CHECKIDENT ('Drivers', RESEED, 0);
DBCC CHECKIDENT ('Orders', RESEED, 0);
GO

-----------------------------------------------------------
-- 2. 暂时禁用所有触发器，以便快速导入随机测试数据
-----------------------------------------------------------
EXEC sp_msforeachtable 'ALTER TABLE ? DISABLE TRIGGER ALL';
GO

-----------------------------------------------------------
-- 3. 填充基础数据
-----------------------------------------------------------
SET NOCOUNT ON;
PRINT '正在填充基础数据...';

INSERT INTO [dbo].[DistributionCenters] ([center_name]) VALUES (N'华东分拨中心'), (N'华南分拨中心'), (N'华北分拨中心');
INSERT INTO [dbo].[Fleets] ([fleet_name], [center_id]) VALUES (N'玄武一队',1), (N'秦淮二队',1), (N'南山三队',2), (N'福田四队',2);

DECLARE @i INT = 1;
DECLARE @char_pool CHAR(34) = 'ABCDEFGHJKLMNPQRSTUVWXYZ0123456789'; 
WHILE @i <= 500
BEGIN
    DECLARE @p1 CHAR(1) = SUBSTRING(@char_pool, ABS(CHECKSUM(NEWID())) % 24 + 1, 1);
    DECLARE @s1 CHAR(1) = SUBSTRING(@char_pool, ABS(CHECKSUM(NEWID())) % 34 + 1, 1);
    DECLARE @s2 CHAR(1) = SUBSTRING(@char_pool, ABS(CHECKSUM(NEWID())) % 34 + 1, 1);
    DECLARE @s3 CHAR(1) = SUBSTRING(@char_pool, ABS(CHECKSUM(NEWID())) % 34 + 1, 1);
    DECLARE @s4 CHAR(1) = SUBSTRING(@char_pool, ABS(CHECKSUM(NEWID())) % 34 + 1, 1);
    DECLARE @s5 CHAR(1) = SUBSTRING(@char_pool, ABS(CHECKSUM(NEWID())) % 34 + 1, 1);
    
    DECLARE @v_id NVARCHAR(10) = N'苏' + @p1 + @s1 + @s2 + @s3 + @s4 + @s5;
    DECLARE @f_id INT = (@i % 4) + 1;
    
    -- 插入车辆时给一个较大的载重，防止测试时频繁超载
    INSERT INTO [dbo].[Vehicles] ([vehicle_id], [max_weight], [max_volume], [fleet_id])
    VALUES (@v_id, 10000.00, 100.00, @f_id);

    INSERT INTO [dbo].[Drivers] ([person_name], [person_contact], [driver_license], [fleet_id])
    VALUES (N'司机' + CAST(@i AS VARCHAR), '13' + CAST(CAST(RAND()*1000000000 AS BIGINT) AS VARCHAR), 'A2', @f_id);

    INSERT INTO [dbo].[Assignments] ([person_id], [vehicle_id]) VALUES (@i, @v_id);
    SET @i = @i + 1;
END
GO

-----------------------------------------------------------
-- 4. 大规模订单数据 (20,000 条)
-----------------------------------------------------------
PRINT '正在插入 20,000 条订单...';
DECLARE @j INT = 1;
WHILE @j <= 20000
BEGIN
    DECLARE @rand_v_id NVARCHAR(10);
    SELECT TOP 1 @rand_v_id = vehicle_id FROM Vehicles WHERE vehicle_id LIKE N'苏%' ORDER BY NEWID();

    DECLARE @s_rand INT = ABS(CHECKSUM(NEWID())) % 100;
    DECLARE @status NVARCHAR(3) = 
        CASE WHEN @s_rand < 15 THEN N'待处理'
             WHEN @s_rand < 30 THEN N'装货中'
             WHEN @s_rand < 45 THEN N'运输中'
             WHEN @s_rand < 90 THEN N'已完成'
             ELSE N'已取消' END;

    INSERT INTO [dbo].[Orders] ([weight], [volume], [origin], [destination], [order_status], [vehicle_id])
    VALUES (RAND()*100, RAND()*1, N'仓库' + CAST(@j%20 AS VARCHAR), N'客户' + CAST(@j%50 AS VARCHAR), @status, @rand_v_id);

    IF @status = N'已完成'
    BEGIN
        DECLARE @oid INT = SCOPE_IDENTITY();
        INSERT INTO [dbo].[CompletedOrder] (order_id, person_id, completed_at)
        VALUES (@oid, (SELECT person_id FROM Assignments WHERE vehicle_id = @rand_v_id), DATEADD(DAY, -(ABS(CHECKSUM(NEWID())) % 30), GETDATE()));
    END
    SET @j = @j + 1;
END
GO

-----------------------------------------------------------
-- 5. 恢复触发器并打印完成
-----------------------------------------------------------
EXEC sp_msforeachtable 'ALTER TABLE ? ENABLE TRIGGER ALL';
PRINT '数据填充成功，触发器已重新开启。';
GO