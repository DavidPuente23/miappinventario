-- 1. NUEVA BASE DE DATOS
CREATE DATABASE IF NOT EXISTS control_activos_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_general_ci;

USE control_activos_db;

-- 2. TABLA PRINCIPAL: EQUIPOS
CREATE TABLE IF NOT EXISTS equipos (
    equipo_id INT AUTO_INCREMENT PRIMARY KEY,
    denominacion VARCHAR(100) NOT NULL,
    clasificacion VARCHAR(50),
    existencia INT NOT NULL DEFAULT 0,
    area_asignada VARCHAR(100),
    condicion_actual ENUM('Operativo', 'Asignado', 'Averiado', 'En taller') DEFAULT 'Operativo',
    fecha_adquisicion DATE,
    suministrador VARCHAR(100),
    notas_adicionales TEXT,
    fecha_alta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. TABLA: REVISIONES (Sustituye a mantenimientos)
CREATE TABLE IF NOT EXISTS revisiones_tecnicas (
    revision_id INT AUTO_INCREMENT PRIMARY KEY,
    equipo_id INT NOT NULL,
    fecha_servicio DATE NOT NULL,
    tipo_servicio VARCHAR(50),
    detalles TEXT,
    fecha_siguiente_revision DATE,
    tecnico_encargado VARCHAR(100),
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_revision_equipo
        FOREIGN KEY (equipo_id)
        REFERENCES equipos(equipo_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- 4. TABLA: TRANSACCIONES (Sustituye a movimientos)
CREATE TABLE IF NOT EXISTS transacciones_stock (
    transaccion_id INT AUTO_INCREMENT PRIMARY KEY,
    equipo_id INT NOT NULL,
    tipo_operacion ENUM('Ingreso', 'Egreso') NOT NULL,
    cantidad_operada INT NOT NULL,
    operador VARCHAR(100),
    justificacion TEXT,
    fecha_transaccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_transaccion_equipo
        FOREIGN KEY (equipo_id)
        REFERENCES equipos(equipo_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- 5. TRIGGER: ACTUALIZAR EXISTENCIAS (Ajustado a los nuevos nombres)
DELIMITER $$
DROP TRIGGER IF EXISTS trg_ajustar_existencias$$

CREATE TRIGGER trg_ajustar_existencias
AFTER INSERT ON transacciones_stock
FOR EACH ROW
BEGIN
    IF NEW.tipo_operacion = 'Ingreso' THEN
        UPDATE equipos
        SET existencia = existencia + NEW.cantidad_operada
        WHERE equipo_id = NEW.equipo_id;
    ELSEIF NEW.tipo_operacion = 'Egreso' THEN
        UPDATE equipos
        SET existencia = existencia - NEW.cantidad_operada
        WHERE equipo_id = NEW.equipo_id;
    END IF;
END$$
DELIMITER ;

-- 6. NUEVO USUARIO PARA LA WEB
CREATE USER IF NOT EXISTS 'admin_activos'@'localhost' IDENTIFIED BY 'admin1234';
GRANT ALL PRIVILEGES ON control_activos_db.* TO 'admin_activos'@'localhost';
FLUSH PRIVILEGES;

-- 7. DATOS INICIALES
INSERT INTO equipos (denominacion, clasificacion, existencia, area_asignada, condicion_actual, fecha_adquisicion, suministrador)
VALUES 
('Rotomartillo Industrial', 'Maquinaria', 3, 'Bodega Central', 'Operativo', '2025-02-10', 'Hilti'),
('Soldadora Inversora', 'Maquinaria', 1, 'Taller B', 'En taller', '2024-11-05', 'Lincoln Electric');

INSERT INTO revisiones_tecnicas (equipo_id, fecha_servicio, tipo_servicio, detalles, fecha_siguiente_revision, tecnico_encargado)
VALUES 
(1, '2025-02-15', 'Inspección', 'Todo en orden', '2026-03-10', 'Ing. Roberto'),
(2, '2026-03-20', 'Reparación', 'Falla en tarjeta electrónica', '2026-04-05', 'Ing. Roberto');

USE control_activos_db;

CREATE TABLE IF NOT EXISTS usuarios (
    usuario_id INT AUTO_INCREMENT PRIMARY KEY,
    nombre_completo VARCHAR(100) NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL,
    rol ENUM('Administrador', 'Operador') NOT NULL
);

-- Creamos dos usuarios de prueba iniciales
INSERT INTO usuarios (nombre_completo, username, password, rol) VALUES 
('Emiliano (Admin)', 'admin', 'admin123', 'Administrador'),
('Auxiliar de Almacén', 'operador', 'operador123', 'Operador');