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
    
    # Tabla de productos (stock del sistema) - AGREGAMOS COLUMNA MARCA
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
    
    # Verificar si la columna 'marca' existe, si no, agregarla
    cursor.execute("PRAGMA table_info(productos)")
    columnas = [columna[1] for columna in cursor.fetchall()]
    if 'marca' not in columnas:
        cursor.execute("ALTER TABLE productos ADD COLUMN marca TEXT")
    
    # Tabla de conteos físicos - AGREGAMOS COLUMNA MARCA
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
            tipo_diferencia TEXT CHECK(tipo_diferencia IN ('OK', 'LEVE', 'CRITICA', 'NO_REGISTRADO', 'NO_ESCOANEADO')),
            FOREIGN KEY (codigo_producto) REFERENCES productos(codigo)
        )
    ''')
    
    # Verificar columnas en conteos
    cursor.execute("PRAGMA table_info(conteos)")
    columnas_conteos = [columna[1] for columna in cursor.fetchall()]
    if 'marca' not in columnas_conteos:
        cursor.execute("ALTER TABLE conteos ADD COLUMN marca TEXT")
    
    # Tabla de marcas (nueva)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS marcas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            activo BOOLEAN DEFAULT 1,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insertar marcas por defecto
    marcas_default = ['GENVEN', 'LETI', 'OTROS', 'SIN MARCA']
    for marca in marcas_default:
        cursor.execute('INSERT OR IGNORE INTO marcas (nombre) VALUES (?)', (marca,))
    
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
    cursor.execute('CREATE INDEX IF NULLS NOT EXISTS idx_productos_marca ON productos(marca)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conteos_fecha ON conteos(fecha)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conteos_usuario ON conteos(usuario)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conteos_marca ON conteos(marca)')
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

# Funciones para marcas
def obtener_todas_marcas():
    """Obtener todas las marcas activas"""
    conn = get_connection()
    df = pd.read_sql_query('SELECT nombre FROM marcas WHERE activo = 1 ORDER BY nombre', conn)
    conn.close()
    return df['nombre'].tolist() if not df.empty else ['GENVEN', 'LETI', 'OTROS', 'SIN MARCA']

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
            'marca': producto[2] if len(producto) > 2 else None,
            'area': producto[3] if len(producto) > 3 else None,
            'stock_sistema': producto[4] if len(producto) > 4 else 0,
            'fecha_actualizacion': producto[5] if len(producto) > 5 else None,
            'activo': bool(producto[6] if len(producto) > 6 else 1)
        }
    return None

def guardar_producto(codigo, producto, marca, area, stock_sistema):
    """Guardar o actualizar producto"""
    conn = get_connection()
    cursor = conn.cursor()
    codigo_limpio = limpiar_codigo(codigo)
    
    cursor.execute('''
        INSERT OR REPLACE INTO productos 
        (codigo, producto, marca, area, stock_sistema, fecha_actualizacion)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (codigo_limpio, producto, marca, area, stock_sistema, datetime.now()))
    
    conn.commit()
    conn.close()

def obtener_todos_productos(marca=None):
    """Obtener todos los productos activos, opcionalmente filtrados por marca"""
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

def desactivar_producto(codigo):
    """Desactivar producto (borrado lógico)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE productos SET activo = 0 WHERE codigo = ?', (codigo,))
    conn.commit()
    conn.close()

# Funciones para conteos
def registrar_conteo(usuario, codigo, producto, marca, area, stock_sistema, conteo_fisico, tipo_diferencia=None):
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
        (fecha, usuario, codigo_producto, producto, marca, area, 
         stock_sistema, conteo_fisico, diferencia, tipo_diferencia)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.now(), usuario, codigo, producto, marca, area, 
          stock_sistema, conteo_fisico, diferencia, tipo_diferencia))
    
    conn.commit()
    conn.close()
    
    return diferencia, tipo_diferencia

def obtener_conteos(fecha_inicio=None, fecha_fin=None, marca=None, area=None, usuario=None):
    """Obtener conteos con filtros"""
    conn = get_connection()
    
    query = '''
        SELECT fecha, usuario, codigo_producto, producto, marca, area,
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
    
    if marca and marca != "Todas":
        query += " AND marca = ?"
        params.append(marca)
    
    if area and area != "Todas":
        query += " AND area = ?"
        params.append(area)
    
    if usuario:
        query += " AND usuario = ?"
        params.append(usuario)
    
    query += " ORDER BY fecha DESC"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def obtener_resumen_por_marca():
    """Obtener resumen completo por marca, incluyendo productos no escaneados"""
    conn = get_connection()
    
    # Primero, obtener todos los productos agrupados por marca
    query_productos = '''
        SELECT 
            marca,
            COUNT(*) as total_productos,
            SUM(stock_sistema) as stock_total_sistema
        FROM productos
        WHERE activo = 1
        GROUP BY marca
        ORDER BY marca
    '''
    
    df_productos = pd.read_sql_query(query_productos, conn)
    
    # Luego, obtener los conteos por marca
    query_conteos = '''
        SELECT 
            p.marca,
            COUNT(DISTINCT c.codigo_producto) as productos_contados,
            SUM(c.conteo_fisico) as total_contado,
            SUM(c.diferencia) as diferencia_neta,
            SUM(CASE WHEN c.tipo_diferencia = 'OK' THEN 1 ELSE 0 END) as exactos,
            SUM(CASE WHEN c.tipo_diferencia = 'LEVE' THEN 1 ELSE 0 END) as leves,
            SUM(CASE WHEN c.tipo_diferencia = 'CRITICA' THEN 1 ELSE 0 END) as criticas
        FROM productos p
        LEFT JOIN conteos c ON p.codigo = c.codigo_producto 
            AND DATE(c.fecha) = DATE('now')
        WHERE p.activo = 1
        GROUP BY p.marca
    '''
    
    df_conteos = pd.read_sql_query(query_conteos, conn)
    conn.close()
    
    # Combinar los datos
    if not df_productos.empty:
        if not df_conteos.empty:
            df_resumen = pd.merge(df_productos, df_conteos, on='marca', how='left')
        else:
            df_resumen = df_productos.copy()
            df_resumen['productos_contados'] = 0
            df_resumen['total_contado'] = 0
            df_resumen['diferencia_neta'] = 0
            df_resumen['exactos'] = 0
            df_resumen['leves'] = 0
            df_resumen['criticas'] = 0
        
        # Calcular productos no escaneados
        df_resumen['productos_no_escaneados'] = df_resumen['total_productos'] - df_resumen['productos_contados'].fillna(0)
        df_resumen['porcentaje_avance'] = (df_resumen['productos_contados'].fillna(0) / df_resumen['total_productos'] * 100).round(1)
        
        # Llenar NaN
        df_resumen = df_resumen.fillna(0)
        
        return df_resumen
    
    return pd.DataFrame()

def obtener_detalle_productos_por_marca(marca, solo_no_escaneados=False):
    """Obtener detalle de productos por marca, incluyendo estado de conteo"""
    conn = get_connection()
    
    query = '''
        SELECT 
            p.codigo,
            p.producto,
            p.marca,
            p.area,
            p.stock_sistema,
            COALESCE(c.conteo_fisico, 0) as conteo_fisico,
            COALESCE(c.diferencia, 0 - p.stock_sistema) as diferencia,
            CASE 
                WHEN c.id IS NULL THEN 'NO_ESCANEADO'
                ELSE COALESCE(c.tipo_diferencia, 'PENDIENTE')
            END as estado,
            c.fecha as ultimo_escaneo,
            c.usuario as ultimo_usuario
        FROM productos p
        LEFT JOIN (
            SELECT * FROM conteos 
            WHERE DATE(fecha) = DATE('now')
            ORDER BY fecha DESC
        ) c ON p.codigo = c.codigo_producto
        WHERE p.activo = 1 AND p.marca = ?
    '''
    
    params = [marca]
    
    if solo_no_escaneados:
        query += " AND c.id IS NULL"
    
    query += " ORDER BY p.area, p.producto"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # Para productos no escaneados, calcular diferencia correctamente
    df.loc[df['estado'] == 'NO_ESCANEADO', 'diferencia'] = -df['stock_sistema']
    
    return df

def obtener_estadisticas_marca(marca):
    """Obtener estadísticas detalladas de una marca específica"""
    conn = get_connection()
    
    query = '''
        SELECT 
            COUNT(*) as total_productos,
            SUM(stock_sistema) as stock_total,
            SUM(CASE WHEN c.id IS NOT NULL THEN 1 ELSE 0 END) as productos_contados,
            SUM(CASE WHEN c.id IS NULL THEN 1 ELSE 0 END) as productos_no_contados,
            COALESCE(SUM(c.conteo_fisico), 0) as total_contado,
            COALESCE(SUM(CASE WHEN c.diferencia = 0 THEN 1 ELSE 0 END), 0) as exactos,
            COALESCE(SUM(CASE WHEN c.diferencia > 0 AND c.diferencia <= 2 THEN 1 ELSE 0 END), 0) as sobrantes_leves,
            COALESCE(SUM(CASE WHEN c.diferencia < 0 AND c.diferencia >= -2 THEN 1 ELSE 0 END), 0) as faltantes_leves,
            COALESCE(SUM(CASE WHEN ABS(c.diferencia) > 2 THEN 1 ELSE 0 END), 0) as diferencias_criticas,
            COALESCE(SUM(c.diferencia), 0) - SUM(CASE WHEN c.id IS NULL THEN stock_sistema ELSE 0 END) as diferencia_neta
        FROM productos p
        LEFT JOIN conteos c ON p.codigo = c.codigo_producto 
            AND DATE(c.fecha) = DATE('now')
        WHERE p.activo = 1 AND p.marca = ?
    '''
    
    df = pd.read_sql_query(query, conn, params=[marca])
    conn.close()
    
    if not df.empty:
        return df.iloc[0].to_dict()
    return {}

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