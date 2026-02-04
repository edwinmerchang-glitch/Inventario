# database.py
import sqlite3
import pandas as pd
from datetime import datetime
import os

DB_NAME = "inventario.db"

def get_connection():
    """Crear y retornar conexión a la base de datos"""
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_database():
    """Inicializar la base de datos con las tablas necesarias"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de productos (stock del sistema)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            codigo TEXT PRIMARY KEY,
            producto TEXT NOT NULL,
            area TEXT NOT NULL,
            stock_sistema INTEGER DEFAULT 0,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activo BOOLEAN DEFAULT 1
        )
    ''')
    
    # Tabla de conteos físicos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conteos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TIMESTAMP NOT NULL,
            usuario TEXT NOT NULL,
            codigo_producto TEXT NOT NULL,
            producto TEXT NOT NULL,
            area TEXT NOT NULL,
            stock_sistema INTEGER NOT NULL,
            conteo_fisico INTEGER NOT NULL,
            diferencia INTEGER NOT NULL,
            tipo_diferencia TEXT CHECK(tipo_diferencia IN ('OK', 'LEVE', 'CRITICA', 'NO_REGISTRADO')),
            FOREIGN KEY (codigo_producto) REFERENCES productos(codigo)
        )
    ''')
    
    # Tabla de usuarios (para control de acceso)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            rol TEXT CHECK(rol IN ('admin', 'inventario', 'consulta')) DEFAULT 'inventario',
            activo BOOLEAN DEFAULT 1,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insertar usuario admin por defecto si no existe
    cursor.execute('''
        INSERT OR IGNORE INTO usuarios (username, nombre, rol) 
        VALUES (?, ?, ?)
    ''', ('admin', 'Administrador', 'admin'))
    
    # Índices para mejor performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_productos_area ON productos(area)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conteos_fecha ON conteos(fecha)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conteos_usuario ON conteos(usuario)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conteos_diferencia ON conteos(diferencia)')
    
    conn.commit()
    conn.close()

# Inicializar la base de datos al importar
init_database()

def limpiar_codigo(codigo):
    """Limpiar código de producto"""
    if codigo is None:
        return ""
    return str(codigo).strip().replace("\n", "").replace("\r", "")

# Funciones para productos
def obtener_producto(codigo):
    """Obtener producto por código"""
    conn = get_connection()
    cursor = conn.cursor()
    codigo_limpio = limpiar_codigo(codigo)
    
    cursor.execute('SELECT * FROM productos WHERE codigo = ?', (codigo_limpio,))
    producto = cursor.fetchone()
    conn.close()
    
    if producto:
        return {
            'codigo': producto[0],
            'producto': producto[1],
            'area': producto[2],
            'stock_sistema': producto[3],
            'fecha_actualizacion': producto[4],
            'activo': bool(producto[5])
        }
    return None

def guardar_producto(codigo, producto, area, stock_sistema):
    """Guardar o actualizar producto"""
    conn = get_connection()
    cursor = conn.cursor()
    codigo_limpio = limpiar_codigo(codigo)
    
    cursor.execute('''
        INSERT OR REPLACE INTO productos 
        (codigo, producto, area, stock_sistema, fecha_actualizacion)
        VALUES (?, ?, ?, ?, ?)
    ''', (codigo_limpio, producto, area, stock_sistema, datetime.now()))
    
    conn.commit()
    conn.close()

def obtener_todos_productos():
    """Obtener todos los productos activos"""
    conn = get_connection()
    df = pd.read_sql_query('''
        SELECT codigo, producto, area, stock_sistema, 
               fecha_actualizacion 
        FROM productos 
        WHERE activo = 1 
        ORDER BY area, producto
    ''', conn)
    conn.close()
    return df

def desactivar_producto(codigo):
    """Desactivar producto (borrado lógico)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE productos SET activo = 0 WHERE codigo = ?', (codigo,))
    conn.commit()
    conn.close()

# Funciones para conteos
def registrar_conteo(usuario, codigo, producto, area, stock_sistema, conteo_fisico, tipo_diferencia=None):
    """Registrar un conteo físico"""
    diferencia = conteo_fisico - stock_sistema
    
    # Determinar tipo de diferencia
    if not tipo_diferencia:
        if producto == "NO REGISTRADO":
            tipo_diferencia = "NO_REGISTRADO"
        elif diferencia == 0:
            tipo_diferencia = "OK"
        elif abs(diferencia) <= 2:
            tipo_diferencia = "LEVE"
        else:
            tipo_diferencia = "CRITICA"
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO conteos 
        (fecha, usuario, codigo_producto, producto, area, 
         stock_sistema, conteo_fisico, diferencia, tipo_diferencia)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.now(), usuario, codigo, producto, area, 
          stock_sistema, conteo_fisico, diferencia, tipo_diferencia))
    
    conn.commit()
    conn.close()
    
    return diferencia, tipo_diferencia

def obtener_conteos(fecha_inicio=None, fecha_fin=None, area=None, usuario=None):
    """Obtener conteos con filtros"""
    conn = get_connection()
    
    query = '''
        SELECT fecha, usuario, codigo_producto, producto, area,
               stock_sistema, conteo_fisico, diferencia, tipo_diferencia
        FROM conteos
        WHERE 1=1
    '''
    params = []
    
    if fecha_inicio:
        query += " AND DATE(fecha) >= DATE(?)"
        params.append(fecha_inicio)
    
    if fecha_fin:
        query += " AND DATE(fecha) <= DATE(?)"
        params.append(fecha_fin)
    
    if area:
        query += " AND area = ?"
        params.append(area)
    
    if usuario:
        query += " AND usuario = ?"
        params.append(usuario)
    
    query += " ORDER BY fecha DESC"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def obtener_resumen_diferencias():
    """Obtener resumen de diferencias"""
    conn = get_connection()
    
    query = '''
        SELECT 
            area,
            COUNT(*) as total_conteos,
            SUM(CASE WHEN tipo_diferencia = 'OK' THEN 1 ELSE 0 END) as correctos,
            SUM(CASE WHEN tipo_diferencia = 'LEVE' THEN 1 ELSE 0 END) as leves,
            SUM(CASE WHEN tipo_diferencia = 'CRITICA' THEN 1 ELSE 0 END) as criticas,
            SUM(CASE WHEN tipo_diferencia = 'NO_REGISTRADO' THEN 1 ELSE 0 END) as no_registrados,
            AVG(ABS(diferencia)) as promedio_diferencia
        FROM conteos
        GROUP BY area
        ORDER BY area
    '''
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# Funciones para usuarios
def verificar_usuario(username):
    """Verificar si usuario existe"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT nombre, rol FROM usuarios WHERE username = ? AND activo = 1', (username,))
    usuario = cursor.fetchone()
    conn.close()
    
    if usuario:
        return {'nombre': usuario[0], 'rol': usuario[1]}
    return None

def crear_usuario(username, nombre, rol='inventario'):
    """Crear nuevo usuario"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO usuarios (username, nombre, rol)
            VALUES (?, ?, ?)
        ''', (username, nombre, rol))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()