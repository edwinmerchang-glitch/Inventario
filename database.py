import sqlite3
import pandas as pd
from datetime import datetime
import os
import hashlib

DB_NAME = "inventario.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    # Tabla de productos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS productos (
        codigo TEXT PRIMARY KEY,
        producto TEXT NOT NULL,
        marca TEXT,
        area TEXT,
        stock_sistema INTEGER DEFAULT 0,
        fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        activo INTEGER DEFAULT 1
    )
    ''')

    # Tabla de conteos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS conteos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TIMESTAMP,
        usuario TEXT,
        codigo_producto TEXT,
        producto TEXT,
        marca TEXT,
        area TEXT,
        stock_sistema INTEGER,
        conteo_fisico INTEGER,
        diferencia INTEGER,
        tipo_diferencia TEXT
    )
    ''')

    # Tabla de marcas
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS marcas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE,
        activo INTEGER DEFAULT 1
    )
    ''')

    # IMPORTANTE: Verificar estructura de usuarios
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios'")
    table_exists = cursor.fetchone()
    
    if table_exists:
        # Verificar columnas
        cursor.execute("PRAGMA table_info(usuarios)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Si la tabla no tiene password, la eliminamos y recreamos
        if 'password' not in column_names:
            cursor.execute("DROP TABLE usuarios")
            cursor.execute('''
            CREATE TABLE usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                nombre TEXT,
                password TEXT,
                rol TEXT DEFAULT 'inventario',
                activo INTEGER DEFAULT 1
            )
            ''')
    else:
        # Crear tabla nueva
        cursor.execute('''
        CREATE TABLE usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            nombre TEXT,
            password TEXT,
            rol TEXT DEFAULT 'inventario',
            activo INTEGER DEFAULT 1
        )
        ''')

    # Insertar usuarios por defecto
    password_hash = hashlib.sha256("admin123".encode()).hexdigest()
    cursor.execute(
        "INSERT OR IGNORE INTO usuarios(username, nombre, password, rol, activo) VALUES(?,?,?,?,?)",
        ('admin', 'Administrador', password_hash, 'admin', 1)
    )
    
    password_hash_inv = hashlib.sha256("inventario123".encode()).hexdigest()
    cursor.execute(
        "INSERT OR IGNORE INTO usuarios(username, nombre, password, rol, activo) VALUES(?,?,?,?,?)",
        ('inventario', 'Operador Inventario', password_hash_inv, 'inventario', 1)
    )
    
    password_hash_con = hashlib.sha256("consulta123".encode()).hexdigest()
    cursor.execute(
        "INSERT OR IGNORE INTO usuarios(username, nombre, password, rol, activo) VALUES(?,?,?,?,?)",
        ('consulta', 'Usuario Consulta', password_hash_con, 'consulta', 1)
    )

    # Insertar marcas por defecto
    marcas_default = ['GENVEN', 'LETI', 'OTROS', 'SIN MARCA']
    for marca in marcas_default:
        cursor.execute("INSERT OR IGNORE INTO marcas(nombre) VALUES(?)", (marca,))

    conn.commit()
    conn.close()


# El resto de las funciones (guardar_producto, guardar_productos_batch, etc.) van aquí
# [Mantén todas las funciones que ya tenías]