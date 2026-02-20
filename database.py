import sqlite3
import pandas as pd
from datetime import datetime
import os

DB_NAME = "inventario.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

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

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        nombre TEXT,
        rol TEXT DEFAULT 'inventario'
    )
    ''')

    cursor.execute("INSERT OR IGNORE INTO usuarios(username,nombre,rol) VALUES('admin','Administrador','admin')")

    conn.commit()
    conn.close()


def guardar_producto(codigo, producto, marca, area, stock):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO productos 
    (codigo, producto, marca, area, stock_sistema, fecha_actualizacion)
    VALUES (?,?,?,?,?,?)
    """, (codigo, producto, marca, area, stock, datetime.now()))

    conn.commit()
    conn.close()


def guardar_productos_masivo(df):
    """
    Guarda múltiples productos de una sola vez usando inserción por lotes
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Preparar los datos para inserción masiva
    datos = []
    ahora = datetime.now()
    
    for _, row in df.iterrows():
        datos.append((
            str(row["codigo"]),
            row["producto"],
            row.get("marca", ""),
            row.get("area", ""),
            int(row.get("stock_sistema", 0)),
            ahora
        ))
    
    # Inserción masiva
    cursor.executemany("""
    INSERT OR REPLACE INTO productos 
    (codigo, producto, marca, area, stock_sistema, fecha_actualizacion)
    VALUES (?,?,?,?,?,?)
    """, datos)
    
    conn.commit()
    conn.close()
    
    return len(datos)


def obtener_producto(codigo):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM productos WHERE codigo=?", (codigo,))
    row = cursor.fetchone()

    conn.close()

    if row:
        return {
            "codigo": row[0],
            "producto": row[1],
            "marca": row[2],
            "area": row[3],
            "stock_sistema": row[4]
        }
    return None


def obtener_productos():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM productos WHERE activo=1", conn)
    conn.close()
    return df


def registrar_conteo(usuario, prod, cantidad):
    diferencia = cantidad - prod["stock_sistema"]

    if diferencia == 0:
        tipo = "OK"
    elif abs(diferencia) <= 2:
        tipo = "LEVE"
    else:
        tipo = "CRITICA"

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO conteos
    (fecha, usuario, codigo_producto, producto, marca, area, stock_sistema, conteo_fisico, diferencia, tipo_diferencia)
    VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        datetime.now(), usuario, prod["codigo"], prod["producto"],
        prod["marca"], prod["area"], prod["stock_sistema"],
        cantidad, diferencia, tipo
    ))

    conn.commit()
    conn.close()