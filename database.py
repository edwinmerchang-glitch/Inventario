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

    # Verificar estructura de usuarios
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios'")
    table_exists = cursor.fetchone()
    
    if table_exists:
        cursor.execute("PRAGMA table_info(usuarios)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
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


# ======================================================
# FUNCIONES PARA PRODUCTOS
# ======================================================

def guardar_producto(codigo, producto, marca, area, stock_sistema):
    """Guardar o actualizar un producto"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT OR REPLACE INTO productos (codigo, producto, marca, area, stock_sistema, fecha_actualizacion)
    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (codigo, producto, marca, area, stock_sistema))
    
    conn.commit()
    conn.close()


def guardar_productos_batch(productos):
    """Guardar múltiples productos en batch"""
    conn = get_connection()
    cursor = conn.cursor()
    
    for producto in productos:
        cursor.execute('''
        INSERT OR REPLACE INTO productos (codigo, producto, marca, area, stock_sistema, fecha_actualizacion)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            producto['codigo'],
            producto['producto'],
            producto['marca'],
            producto['area'],
            producto['stock_sistema']
        ))
    
    conn.commit()
    conn.close()


def obtener_todos_productos(marca_filtro='Todas'):
    """Obtener todos los productos activos"""
    conn = get_connection()
    
    if marca_filtro and marca_filtro != 'Todas':
        query = "SELECT codigo, producto, marca, area, stock_sistema FROM productos WHERE activo = 1 AND marca = ?"
        df = pd.read_sql_query(query, conn, params=(marca_filtro,))
    else:
        query = "SELECT codigo, producto, marca, area, stock_sistema FROM productos WHERE activo = 1"
        df = pd.read_sql_query(query, conn)
    
    conn.close()
    return df


def obtener_producto_por_codigo(codigo):
    """Obtener un producto por su código"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT codigo, producto, marca, area, stock_sistema 
    FROM productos 
    WHERE codigo = ? AND activo = 1
    ''', (codigo,))
    
    resultado = cursor.fetchone()
    conn.close()
    
    if resultado:
        return {
            'codigo': resultado[0],
            'producto': resultado[1],
            'marca': resultado[2],
            'area': resultado[3],
            'stock_sistema': resultado[4]
        }
    return None


# ======================================================
# FUNCIONES PARA MARCAS
# ======================================================

def obtener_todas_marcas():
    """Obtener todas las marcas activas"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT nombre FROM marcas WHERE activo = 1 ORDER BY nombre")
    marcas = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return marcas


def crear_marca(nombre):
    """Crear una nueva marca"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO marcas (nombre) VALUES (?)", (nombre.upper(),))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


# ======================================================
# FUNCIONES PARA CONTEO
# ======================================================

def registrar_conteo(usuario, codigo_producto, producto, marca, area, stock_sistema, conteo_fisico):
    """Registrar un conteo en la base de datos"""
    conn = get_connection()
    cursor = conn.cursor()
    
    fecha = datetime.now()
    diferencia = conteo_fisico - stock_sistema
    
    if diferencia > 0:
        tipo_diferencia = 'SOBRANTE'
    elif diferencia < 0:
        tipo_diferencia = 'FALTANTE'
    else:
        tipo_diferencia = 'EXACTO'
    
    cursor.execute('''
    INSERT INTO conteos (fecha, usuario, codigo_producto, producto, marca, area, stock_sistema, conteo_fisico, diferencia, tipo_diferencia)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (fecha, usuario, codigo_producto, producto, marca, area, stock_sistema, conteo_fisico, diferencia, tipo_diferencia))
    
    conn.commit()
    conn.close()


def obtener_conteos_por_usuario(usuario, fecha=None):
    """Obtener conteos de un usuario específico"""
    conn = get_connection()
    
    if fecha:
        query = "SELECT * FROM conteos WHERE usuario = ? AND DATE(fecha) = ?"
        df = pd.read_sql_query(query, conn, params=(usuario, fecha))
    else:
        query = "SELECT * FROM conteos WHERE usuario = ?"
        df = pd.read_sql_query(query, conn, params=(usuario,))
    
    conn.close()
    return df


# ======================================================
# FUNCIONES PARA REPORTES POR MARCA
# ======================================================

def obtener_resumen_por_marca():
    """Obtener resumen de estadísticas por marca"""
    conn = get_connection()
    
    query = """
    WITH productos_por_marca AS (
        SELECT 
            p.marca,
            COUNT(DISTINCT p.codigo) as total_productos,
            SUM(p.stock_sistema) as stock_total_sistema,
            COUNT(DISTINCT CASE WHEN c.codigo_producto IS NOT NULL THEN p.codigo END) as productos_contados,
            SUM(CASE WHEN c.codigo_producto IS NOT NULL THEN c.conteo_fisico ELSE 0 END) as total_contado
        FROM productos p
        LEFT JOIN (
            SELECT DISTINCT codigo_producto, conteo_fisico
            FROM conteos 
            WHERE DATE(fecha) = DATE('now')
        ) c ON p.codigo = c.codigo_producto
        WHERE p.activo = 1
        GROUP BY p.marca
    )
    SELECT 
        marca,
        total_productos,
        productos_contados,
        total_productos - productos_contados as productos_no_escaneados,
        ROUND(CAST(productos_contados AS FLOAT) / total_productos * 100, 1) as porcentaje_avance,
        stock_total_sistema,
        total_contado,
        total_contado - stock_total_sistema as diferencia_neta
    FROM productos_por_marca
    ORDER BY marca
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def obtener_detalle_productos_por_marca(marca, solo_no_escaneados=False):
    """Obtener detalle de productos de una marca específica"""
    conn = get_connection()
    
    if solo_no_escaneados:
        query = """
        SELECT 
            p.codigo,
            p.producto,
            p.area,
            p.stock_sistema,
            COALESCE(c.conteo_fisico, 0) as conteo_fisico,
            COALESCE(c.conteo_fisico, 0) - p.stock_sistema as diferencia,
            CASE 
                WHEN c.conteo_fisico IS NULL THEN 'NO_ESCANEADO'
                WHEN COALESCE(c.conteo_fisico, 0) = p.stock_sistema THEN 'OK'
                WHEN ABS(COALESCE(c.conteo_fisico, 0) - p.stock_sistema) <= 2 THEN 'LEVE'
                ELSE 'CRITICA'
            END as estado,
            c.fecha as ultimo_escaneo,
            c.usuario as ultimo_usuario
        FROM productos p
        LEFT JOIN (
            SELECT codigo_producto, MAX(fecha) as fecha, conteo_fisico, usuario
            FROM conteos
            GROUP BY codigo_producto
        ) c ON p.codigo = c.codigo_producto
        WHERE p.marca = ? AND p.activo = 1 AND c.codigo_producto IS NULL
        ORDER BY p.codigo
        """
        df = pd.read_sql_query(query, conn, params=(marca,))
    else:
        query = """
        SELECT 
            p.codigo,
            p.producto,
            p.area,
            p.stock_sistema,
            COALESCE(c.conteo_fisico, 0) as conteo_fisico,
            COALESCE(c.conteo_fisico, 0) - p.stock_sistema as diferencia,
            CASE 
                WHEN c.conteo_fisico IS NULL THEN 'NO_ESCANEADO'
                WHEN COALESCE(c.conteo_fisico, 0) = p.stock_sistema THEN 'OK'
                WHEN ABS(COALESCE(c.conteo_fisico, 0) - p.stock_sistema) <= 2 THEN 'LEVE'
                ELSE 'CRITICA'
            END as estado,
            c.fecha as ultimo_escaneo,
            c.usuario as ultimo_usuario
        FROM productos p
        LEFT JOIN (
            SELECT codigo_producto, MAX(fecha) as fecha, conteo_fisico, usuario
            FROM conteos
            GROUP BY codigo_producto
        ) c ON p.codigo = c.codigo_producto
        WHERE p.marca = ? AND p.activo = 1
        ORDER BY 
            CASE 
                WHEN c.codigo_producto IS NULL THEN 0
                ELSE 1
            END,
            ABS(COALESCE(c.conteo_fisico, 0) - p.stock_sistema) DESC
        """
        df = pd.read_sql_query(query, conn, params=(marca,))
    
    conn.close()
    return df


def obtener_estadisticas_marca(marca):
    """Obtener estadísticas detalladas de una marca"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Total productos
    cursor.execute("SELECT COUNT(*) FROM productos WHERE marca = ? AND activo = 1", (marca,))
    total_productos = cursor.fetchone()[0]
    
    # Productos contados hoy
    cursor.execute("""
    SELECT COUNT(DISTINCT codigo_producto)
    FROM conteos 
    WHERE marca = ? AND DATE(fecha) = DATE('now')
    """, (marca,))
    productos_contados_hoy = cursor.fetchone()[0] or 0
    
    # Productos no contados
    cursor.execute("""
    SELECT COUNT(*)
    FROM productos p
    WHERE p.marca = ? AND p.activo = 1
    AND NOT EXISTS (
        SELECT 1 FROM conteos c
        WHERE c.codigo_producto = p.codigo AND DATE(c.fecha) = DATE('now')
    )
    """, (marca,))
    productos_no_contados = cursor.fetchone()[0]
    
    # Stock total
    cursor.execute("SELECT SUM(stock_sistema) FROM productos WHERE marca = ? AND activo = 1", (marca,))
    stock_total = cursor.fetchone()[0] or 0
    
    # Total contado
    cursor.execute("""
    SELECT SUM(conteo_fisico)
    FROM conteos 
    WHERE marca = ? AND DATE(fecha) = DATE('now')
    """, (marca,))
    total_contado = cursor.fetchone()[0] or 0
    
    # Diferencia neta
    diferencia_neta = total_contado - stock_total
    
    # Exactos
    cursor.execute("""
    SELECT COUNT(*)
    FROM conteos c
    WHERE c.marca = ? AND DATE(c.fecha) = DATE('now')
    AND c.conteo_fisico = (
        SELECT stock_sistema FROM productos p 
        WHERE p.codigo = c.codigo_producto AND p.activo = 1
    )
    """, (marca,))
    exactos = cursor.fetchone()[0]
    
    # Diferencias leves (1-2 unidades)
    cursor.execute("""
    SELECT COUNT(*)
    FROM conteos c
    WHERE c.marca = ? AND DATE(c.fecha) = DATE('now')
    AND ABS(c.conteo_fisico - (
        SELECT stock_sistema FROM productos p 
        WHERE p.codigo = c.codigo_producto AND p.activo = 1
    )) BETWEEN 1 AND 2
    """, (marca,))
    diferencias_leves = cursor.fetchone()[0]
    
    # Diferencias críticas (>2)
    cursor.execute("""
    SELECT COUNT(*)
    FROM conteos c
    WHERE c.marca = ? AND DATE(c.fecha) = DATE('now')
    AND ABS(c.conteo_fisico - (
        SELECT stock_sistema FROM productos p 
        WHERE p.codigo = c.codigo_producto AND p.activo = 1
    )) > 2
    """, (marca,))
    diferencias_criticas = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_productos': total_productos,
        'productos_contados': productos_contados_hoy,
        'productos_no_contados': productos_no_contados,
        'stock_total': stock_total,
        'total_contado': total_contado,
        'diferencia_neta': diferencia_neta,
        'exactos': exactos,
        'diferencias_leves': diferencias_leves,
        'diferencias_criticas': diferencias_criticas
    }


# Inicializar la base de datos al importar el módulo
init_database()