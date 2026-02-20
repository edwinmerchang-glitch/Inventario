# database.py
import sqlite3
import pandas as pd
from datetime import datetime
import os

DB_NAME = "inventario.db"

def get_connection():
    """Crear y retornar conexión a la base de datos con optimizaciones"""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    # Optimizaciones para mejor rendimiento
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA journal_mode = MEMORY")
    conn.execute("PRAGMA cache_size = 10000")
    return conn

def init_database():
    """Inicializar la base de datos con las tablas necesarias"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de productos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            codigo TEXT PRIMARY KEY,
            producto TEXT NOT NULL,
            marca TEXT,
            area TEXT NOT NULL,
            stock_sistema INTEGER DEFAULT 0,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activo BOOLEAN DEFAULT 1
        )
    ''')
    
    # Verificar columna marca
    cursor.execute("PRAGMA table_info(productos)")
    columnas = [columna[1] for columna in cursor.fetchall()]
    if 'marca' not in columnas:
        cursor.execute("ALTER TABLE productos ADD COLUMN marca TEXT")
    
    # Tabla de conteos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conteos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TIMESTAMP NOT NULL,
            usuario TEXT NOT NULL,
            codigo_producto TEXT NOT NULL,
            producto TEXT NOT NULL,
            marca TEXT,
            area TEXT NOT NULL,
            stock_sistema INTEGER NOT NULL,
            conteo_fisico INTEGER NOT NULL,
            diferencia INTEGER NOT NULL,
            tipo_diferencia TEXT CHECK(tipo_diferencia IN ('OK', 'LEVE', 'CRITICA', 'NO_REGISTRADO', 'NO_ESCANEADO')),
            FOREIGN KEY (codigo_producto) REFERENCES productos(codigo)
        )
    ''')
    
    # Verificar columna marca en conteos
    cursor.execute("PRAGMA table_info(conteos)")
    columnas_conteos = [columna[1] for columna in cursor.fetchall()]
    if 'marca' not in columnas_conteos:
        cursor.execute("ALTER TABLE conteos ADD COLUMN marca TEXT")
    
    # Tabla de marcas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS marcas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            activo BOOLEAN DEFAULT 1,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insertar marcas por defecto (solo si no existen)
    marcas_default = ['GENVEN', 'LETI', 'OTROS', 'SIN MARCA']
    for marca in marcas_default:
        cursor.execute('INSERT OR IGNORE INTO marcas (nombre) VALUES (?)', (marca,))
    
    # Tabla de usuarios
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
    
    # Insertar usuario admin
    cursor.execute('''
        INSERT OR IGNORE INTO usuarios (username, nombre, rol) 
        VALUES (?, ?, ?)
    ''', ('admin', 'Administrador', 'admin'))
    
    # Índices para mejor performance
    indices = [
        'CREATE INDEX IF NOT EXISTS idx_productos_area ON productos(area)',
        'CREATE INDEX IF NOT EXISTS idx_productos_marca ON productos(marca)',
        'CREATE INDEX IF NOT EXISTS idx_conteos_fecha ON conteos(fecha)',
        'CREATE INDEX IF NOT EXISTS idx_conteos_usuario ON conteos(usuario)',
        'CREATE INDEX IF NOT EXISTS idx_conteos_marca ON conteos(marca)',
        'CREATE INDEX IF NOT EXISTS idx_conteos_diferencia ON conteos(diferencia)',
        'CREATE INDEX IF NOT EXISTS idx_conteos_fecha_marca ON conteos(fecha, marca)'
    ]
    
    for idx in indices:
        try:
            cursor.execute(idx)
        except:
            pass  # Ignorar errores de índices
    
    conn.commit()
    conn.close()

# Inicializar DB
init_database()

def limpiar_codigo(codigo):
    """Limpiar código de producto"""
    return str(codigo).strip().replace("\n", "").replace("\r", "") if codigo else ""

# Funciones para marcas
def obtener_todas_marcas():
    """Obtener todas las marcas activas"""
    try:
        conn = get_connection()
        df = pd.read_sql_query('SELECT nombre FROM marcas WHERE activo = 1 ORDER BY nombre', conn)
        conn.close()
        return df['nombre'].tolist() if not df.empty else ['GENVEN', 'LETI', 'OTROS', 'SIN MARCA']
    except:
        return ['GENVEN', 'LETI', 'OTROS', 'SIN MARCA']

def crear_marca(nombre):
    """Crear nueva marca"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO marcas (nombre) VALUES (?)', (nombre.upper(),))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# Funciones para productos
def obtener_producto(codigo):
    """Obtener producto por código"""
    codigo_limpio = limpiar_codigo(codigo)
    if not codigo_limpio:
        return None
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM productos WHERE codigo = ?', (codigo_limpio,))
    producto = cursor.fetchone()
    conn.close()
    
    if producto:
        return {
            'codigo': producto[0],
            'producto': producto[1],
            'marca': producto[2] if len(producto) > 2 else None,
            'area': producto[3] if len(producto) > 3 else None,
            'stock_sistema': producto[4] if len(producto) > 4 else 0,
            'fecha_actualizacion': producto[5] if len(producto) > 5 else None,
            'activo': bool(producto[6] if len(producto) > 6 else 1)
        }
    return None

def guardar_producto(codigo, producto, marca, area, stock_sistema):
    """Guardar o actualizar producto"""
    codigo_limpio = limpiar_codigo(codigo)
    if not codigo_limpio or not producto:
        return False
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO productos 
        (codigo, producto, marca, area, stock_sistema, fecha_actualizacion)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (codigo_limpio, producto, marca, area, stock_sistema, datetime.now()))
    
    conn.commit()
    conn.close()
    return True

def guardar_productos_batch(productos_list):
    """Guardar múltiples productos en batch (mucho más rápido)"""
    if not productos_list:
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Usar transacción para batch insert
    cursor.execute("BEGIN TRANSACTION")
    
    for prod in productos_list:
        cursor.execute('''
            INSERT OR REPLACE INTO productos 
            (codigo, producto, marca, area, stock_sistema, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (prod['codigo'], prod['producto'], prod['marca'], 
              prod['area'], prod['stock_sistema'], datetime.now()))
    
    cursor.execute("COMMIT")
    conn.close()

def obtener_todos_productos(marca=None):
    """Obtener todos los productos activos"""
    conn = get_connection()
    
    query = '''
        SELECT codigo, producto, marca, area, stock_sistema, fecha_actualizacion 
        FROM productos 
        WHERE activo = 1 
    '''
    params = []
    
    if marca and marca != "Todas":
        query += " AND marca = ?"
        params.append(marca)
    
    query += " ORDER BY marca, area, producto"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

# Funciones para conteos
def registrar_conteo(usuario, codigo, producto, marca, area, stock_sistema, conteo_fisico):
    """Registrar un conteo físico"""
    diferencia = conteo_fisico - stock_sistema
    
    # Determinar tipo de diferencia
    if diferencia == 0:
        tipo_diferencia = "OK"
    elif abs(diferencia) <= 2:
        tipo_diferencia = "LEVE"
    else:
        tipo_diferencia = "CRITICA"
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO conteos 
        (fecha, usuario, codigo_producto, producto, marca, area, 
         stock_sistema, conteo_fisico, diferencia, tipo_diferencia)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.now(), usuario, codigo, producto, marca, area, 
          stock_sistema, conteo_fisico, diferencia, tipo_diferencia))
    
    conn.commit()
    conn.close()
    
    return diferencia, tipo_diferencia

def obtener_resumen_por_marca():
    """Obtener resumen completo por marca - VERSIÓN CORREGIDA"""
    conn = get_connection()
    
    # Query optimizada que hace todo en una sola consulta
    query = '''
        WITH conteos_hoy AS (
            SELECT codigo_producto, 
                   COALESCE(SUM(conteo_fisico), 0) as total_contado,
                   COUNT(*) as veces_contado,
                   COALESCE(SUM(diferencia), 0) as dif_total
            FROM conteos
            WHERE DATE(fecha) = DATE('now')
            GROUP BY codigo_producto
        )
        SELECT 
            COALESCE(p.marca, 'SIN MARCA') as marca,
            COUNT(*) as total_productos,
            COALESCE(SUM(p.stock_sistema), 0) as stock_total_sistema,
            COUNT(ch.codigo_producto) as productos_contados,
            COALESCE(SUM(ch.total_contado), 0) as total_contado,
            COALESCE(SUM(ch.dif_total), 0) - 
                SUM(CASE WHEN ch.codigo_producto IS NULL THEN p.stock_sistema ELSE 0 END) as diferencia_neta,
            SUM(CASE WHEN ch.codigo_producto IS NOT NULL AND ch.dif_total = 0 THEN 1 ELSE 0 END) as exactos,
            SUM(CASE WHEN ch.codigo_producto IS NOT NULL AND ABS(ch.dif_total) <= 2 AND ch.dif_total != 0 THEN 1 ELSE 0 END) as leves,
            SUM(CASE WHEN ch.codigo_producto IS NOT NULL AND ABS(ch.dif_total) > 2 THEN 1 ELSE 0 END) as criticas
        FROM productos p
        LEFT JOIN conteos_hoy ch ON p.codigo = ch.codigo_producto
        WHERE p.activo = 1
        GROUP BY COALESCE(p.marca, 'SIN MARCA')
        ORDER BY marca
    '''
    
    try:
        df = pd.read_sql_query(query, conn)
        
        if not df.empty:
            # Convertir a tipos numéricos explícitamente
            numeric_cols = ['total_productos', 'stock_total_sistema', 'productos_contados', 
                           'total_contado', 'diferencia_neta', 'exactos', 'leves', 'criticas']
            
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            
            # Calcular productos no escaneados y porcentaje de avance
            df['productos_no_escaneados'] = df['total_productos'] - df['productos_contados']
            df['porcentaje_avance'] = (df['productos_contados'] / df['total_productos'] * 100).round(1)
            
            # Llenar NaN de manera segura
            df = df.fillna(0)
            
            # Asegurar tipos de datos
            df['productos_no_escaneados'] = df['productos_no_escaneados'].astype(int)
            df['porcentaje_avance'] = df['porcentaje_avance'].astype(float)
        
        conn.close()
        return df
        
    except Exception as e:
        print(f"Error en obtener_resumen_por_marca: {e}")
        conn.close()
        return pd.DataFrame()

def obtener_detalle_productos_por_marca(marca, solo_no_escaneados=False):
    """Obtener detalle de productos por marca - VERSIÓN CORREGIDA"""
    conn = get_connection()
    
    # Query optimizada
    query = '''
        SELECT 
            p.codigo,
            p.producto,
            COALESCE(p.marca, 'SIN MARCA') as marca,
            p.area,
            p.stock_sistema,
            COALESCE(ch.total_contado, 0) as conteo_fisico,
            CASE 
                WHEN ch.total_contado IS NULL THEN -p.stock_sistema
                ELSE COALESCE(ch.total_contado, 0) - p.stock_sistema
            END as diferencia,
            CASE 
                WHEN ch.total_contado IS NULL THEN 'NO_ESCANEADO'
                WHEN COALESCE(ch.total_contado, 0) - p.stock_sistema = 0 THEN 'OK'
                WHEN ABS(COALESCE(ch.total_contado, 0) - p.stock_sistema) <= 2 THEN 'LEVE'
                ELSE 'CRITICA'
            END as estado,
            MAX(c.fecha) as ultimo_escaneo,
            MAX(c.usuario) as ultimo_usuario
        FROM productos p
        LEFT JOIN (
            SELECT codigo_producto, SUM(conteo_fisico) as total_contado
            FROM conteos
            WHERE DATE(fecha) = DATE('now')
            GROUP BY codigo_producto
        ) ch ON p.codigo = ch.codigo_producto
        LEFT JOIN conteos c ON p.codigo = c.codigo_producto 
            AND DATE(c.fecha) = DATE('now')
        WHERE p.activo = 1 AND COALESCE(p.marca, 'SIN MARCA') = ?
    '''
    
    params = [marca]
    
    if solo_no_escaneados:
        query += " AND ch.total_contado IS NULL"
    
    query += " GROUP BY p.codigo ORDER BY p.area, p.producto"
    
    try:
        df = pd.read_sql_query(query, conn, params=params)
        
        if not df.empty:
            # Convertir a tipos numéricos
            df['stock_sistema'] = pd.to_numeric(df['stock_sistema'], errors='coerce').fillna(0).astype(int)
            df['conteo_fisico'] = pd.to_numeric(df['conteo_fisico'], errors='coerce').fillna(0).astype(int)
            df['diferencia'] = pd.to_numeric(df['diferencia'], errors='coerce').fillna(0).astype(int)
            
            # Formatear fecha
            if 'ultimo_escaneo' in df.columns:
                df['ultimo_escaneo'] = pd.to_datetime(df['ultimo_escaneo'], errors='coerce')
        
        conn.close()
        return df
        
    except Exception as e:
        print(f"Error en obtener_detalle_productos_por_marca: {e}")
        conn.close()
        return pd.DataFrame()