"""Base de datos SQLite de la app.

No hay nada que instalar ni configurar: el archivo de la base se crea solo
la primera vez que arranca la app, en  instance/inventario.db
"""
import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
DB_PATH = os.environ.get('DB_PATH') or os.path.join(INSTANCE_DIR, 'inventario.db')


# --- Conversión de tipos (para que las plantillas funcionen igual que con MySQL) ---
def _convertir_timestamp(valor):
    texto = valor.decode()
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        return texto


sqlite3.register_converter('TIMESTAMP', _convertir_timestamp)
# Las fechas (sin hora) se quedan como texto 'AAAA-MM-DD'
sqlite3.register_converter('DATE', lambda valor: valor.decode())


def _filas_como_dict(cursor, fila):
    return {col[0]: fila[i] for i, col in enumerate(cursor.description)}


def conectar_bd():
    carpeta = os.path.dirname(DB_PATH)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = _filas_como_dict
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


ESQUEMA = """
CREATE TABLE IF NOT EXISTS equipos (
    equipo_id INTEGER PRIMARY KEY AUTOINCREMENT,
    denominacion TEXT NOT NULL,
    clasificacion TEXT,
    existencia INTEGER NOT NULL DEFAULT 0,
    area_asignada TEXT,
    condicion_actual TEXT NOT NULL DEFAULT 'Operativo'
        CHECK (condicion_actual IN ('Operativo', 'Asignado', 'Averiado', 'En taller')),
    fecha_adquisicion DATE,
    suministrador TEXT,
    notas_adicionales TEXT,
    fecha_alta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS revisiones_tecnicas (
    revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo_id INTEGER NOT NULL,
    fecha_servicio DATE NOT NULL,
    tipo_servicio TEXT,
    detalles TEXT,
    fecha_siguiente_revision DATE,
    tecnico_encargado TEXT,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (equipo_id) REFERENCES equipos(equipo_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS transacciones_stock (
    transaccion_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo_id INTEGER NOT NULL,
    tipo_operacion TEXT NOT NULL CHECK (tipo_operacion IN ('Ingreso', 'Egreso')),
    cantidad_operada INTEGER NOT NULL,
    operador TEXT,
    justificacion TEXT,
    fecha_transaccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (equipo_id) REFERENCES equipos(equipo_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- Ajusta las existencias automáticamente en cada ingreso / egreso
CREATE TRIGGER IF NOT EXISTS trg_ajustar_existencias
AFTER INSERT ON transacciones_stock
BEGIN
    UPDATE equipos SET existencia = existencia + NEW.cantidad_operada
     WHERE equipo_id = NEW.equipo_id AND NEW.tipo_operacion = 'Ingreso';
    UPDATE equipos SET existencia = existencia - NEW.cantidad_operada
     WHERE equipo_id = NEW.equipo_id AND NEW.tipo_operacion = 'Egreso';
END;

CREATE TABLE IF NOT EXISTS usuarios (
    usuario_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_completo TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password TEXT NOT NULL,
    rol TEXT NOT NULL CHECK (rol IN ('Administrador', 'Operador'))
);
"""


def init_db():
    """Crea las tablas si no existen (es seguro llamarla muchas veces)."""
    conn = conectar_bd()
    try:
        conn.executescript(ESQUEMA)
        conn.commit()
    finally:
        conn.close()
