USE master;
GO

ALTER DATABASE FleetSync SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
GO

DROP DATABASE FleetSync;
GO

CREATE DATABASE FleetSync;
GO

USE FleetSync

-- 配送中心表
CREATE TABLE DistributionCenters (
    center_id INT PRIMARY KEY IDENTITY(1,1),
    center_name NVARCHAR(50) NOT NULL,
    is_deleted BIT DEFAULT 0 NOT NULL,
);

-- 车队表
CREATE TABLE Fleets (
    fleet_id INT PRIMARY KEY IDENTITY(1,1),
    fleet_name NVARCHAR(50) NOT NULL,
    center_id INT NOT NULL,
    is_deleted BIT DEFAULT 0 NOT NULL,
    CONSTRAINT FK_Fleets_Centers FOREIGN KEY (center_id) REFERENCES DistributionCenters(center_id)
);

-- 司机表
CREATE TABLE Drivers (
    person_id INT PRIMARY KEY IDENTITY(1,1),
    person_name NVARCHAR(50) NOT NULL,
    person_contact NVARCHAR(50),
    driver_license CHAR(2) NOT NULL CHECK (driver_license IN ('A2', 'B2', 'C1', 'C2', 'C3', 'C4', 'C6')),
    driver_status NVARCHAR(3) DEFAULT '空闲' CHECK (driver_status IN ('空闲', '运输中', '休息中')) NOT NULL,
    fleet_id INT NOT NULL,
    is_deleted BIT DEFAULT 0 NOT NULL,
    CONSTRAINT FK_Drivers_Fleets FOREIGN KEY (fleet_id) REFERENCES Fleets(fleet_id)
);

-- 主管表
CREATE TABLE Managers (
    person_id INT PRIMARY KEY IDENTITY(1,1),
    person_name NVARCHAR(20) NOT NULL,
    person_contact NVARCHAR(15),
    fleet_id INT NOT NULL,
    is_deleted BIT DEFAULT 0 NOT NULL,
    CONSTRAINT FK_Managers_Fleets FOREIGN KEY (fleet_id) REFERENCES Fleets(fleet_id)
);

-- 车辆表
CREATE TABLE Vehicles (
    vehicle_id NVARCHAR(10) PRIMARY KEY,
    max_weight DECIMAL(10,2) NOT NULL,
    max_volume DECIMAL(10,2) NOT NULL,
    vehicle_status NVARCHAR(10) DEFAULT '空闲' CHECK (vehicle_status IN ('空闲', '装货中', '运输中', '维修中', '异常')) NOT NULL,
    fleet_id INT NOT NULL,
    is_deleted BIT DEFAULT 0 NOT NULL,
    CONSTRAINT FK_Vehicles_Fleets FOREIGN KEY (fleet_id) REFERENCES Fleets(fleet_id)
);

-- 运单表
CREATE TABLE Orders (
    order_id INT PRIMARY KEY IDENTITY(1,1),
    weight DECIMAL(10,2) NOT NULL,
    volume DECIMAL(10,2) NOT NULL,
    origin NVARCHAR(100) NOT NULL,
    destination NVARCHAR(100) NOT NULL,
    order_status NCHAR(3) DEFAULT '待处理' CHECK (order_status IN ('待处理', '装货中', '运输中', '已完成', '已取消')) NOT NULL,
    vehicle_id NVARCHAR(10),
    is_deleted BIT DEFAULT 0 NOT NULL,
    CONSTRAINT FK_Orders_Vehicles FOREIGN KEY (vehicle_id) REFERENCES Vehicles(vehicle_id)
);

-- 异常记录表
CREATE TABLE Incidents (
    incident_id INT PRIMARY KEY IDENTITY(1,1),
    vehicle_id NVARCHAR(10) NOT NULL,
    driver_id INT NOT NULL,
    incident_type NVARCHAR(20) NOT NULL,
    incident_description NVARCHAR(255) NOT NULL,
    fine_amount DECIMAL(10,2) DEFAULT 0.00 NOT NULL,
    handle_status NCHAR(3) DEFAULT '未处理' CHECK (handle_status IN ('已处理', '未处理')) NOT NULL,
    occurrence_time DATE NOT NULL,
    is_deleted BIT DEFAULT 0 NOT NULL,
    CONSTRAINT FK_Incidents_Vehicles FOREIGN KEY (vehicle_id) REFERENCES Vehicles(vehicle_id),
    CONSTRAINT FK_Incidents_Drivers FOREIGN KEY (driver_id) REFERENCES Drivers(person_id)
);

-- 审计日志表
CREATE TABLE History_Log (
    log_id INT PRIMARY KEY IDENTITY(1,1),
    table_name NVARCHAR(20),
    target_id NVARCHAR(20),
    old_data NVARCHAR(MAX),
    change_time DATETIME DEFAULT GETDATE()
);

create table Assignments(
    person_id int primary key,
    vehicle_id nvarchar(10) not null unique,
    constraint fk_assignments_drivers foreign key(person_id) references Drivers(person_id),
    constraint fk_assignments_vehicles foreign key(vehicle_id) references Vehicles(vehicle_id),
);


CREATE TABLE CompletedOrder (
    order_id INT NOT NULL,
    person_id INT NOT NULL,
    completed_at DATE NOT NULL,
    CONSTRAINT FK_CompletedOrder_Orders FOREIGN KEY (order_id) REFERENCES Orders(order_id)
);