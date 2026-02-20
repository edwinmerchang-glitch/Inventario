# database.py
import sqlite3
import pandas as pd
from datetime import datetime
import hashlib

DB_NAME = "inventario.db"

def get_connection():
    """Crear y retornar conexión a la base de datos"""
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Inicializar la base de datos con todas las tablas necesarias"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de usuarios (para autenticación)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            password TEXT NOT NULL,
            rol TEXT CHECK(rol IN ('admin', 'inventario', 'consulta')) DEFAULT 'inventario',
            activo BOOLEAN DEFAULT 1
        )
    ''')
    
    # Tabla de marcas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS marcas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            activo BOOLEAN DEFAULT 1
        )
    ''')
    
    # Insertar marcas por defecto
    marcas_default = ['GENVEN', 'LETI', 'OTROS', 'SIN MARCA']
    for marca in marcas_default:
        cursor.execute('INSERT OR IGNORE INTO marcas (nombre) VALUES (?)', (marca,))
    
    # Tabla de productos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            codigo TEXT PRIMARY KEY,
            producto TEXT NOT NULL,
            marca TEXT,
            area TEXT NOT NULL,
            stock_sistema INTEGER DEFAULT 0,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activo BOOLEAN DEFAULT 1,
            FOREIGN KEY (marca) REFERENCES marcas(nombre)
        )
    ''')
    
    # Tabla de conteos/escaneos (UNIFICADA)
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
            cantidad_escaneada INTEGER NOT NULL,
            total_acumulado INTEGER NOT NULL,
            diferencia INTEGER NOT NULL,
            tipo_operacion TEXT DEFAULT 'ESCANEO',
            FOREIGN KEY (codigo_producto) REFERENCES productos(codigo),
            FOREIGN KEY (usuario) REFERENCES usuarios(username)
        )
    ''')
    
    # Insertar usuario admin por defecto
    admin_password = hashlib.sha256("admin123".encode()).hexdigest()
    cursor.execute('''
        INSERT OR IGNORE INTO usuarios (username, nombre, password, rol) 
        VALUES (?, ?, ?, ?)
    ''', ('admin', 'Administrador', admin_password, 'admin'))
    
    # Insertar usuario inventario por defecto
    inv_password = hashlib.sha256("inventario123".encode()).hexdigest()
    cursor.execute('''
        INSERT OR IGNORE INTO usuarios (username, nombre, password, rol) 
        VALUES (?, ?, ?, ?)
    ''', ('inventario', 'Operador Inventario', inv_password, 'inventario'))
    
    # Insertar usuario consulta por defecto
    cons_password = hashlib.sha256("consulta123".encode()).hexdigest()
    cursor.execute('''
        INSERT OR IGNORE INTO usuarios (username, nombre, password, rol) 
        VALUES (?, ?, ?, ?)
    ''', ('consulta', 'Usuario Consulta', cons_password, 'consulta'))
    
    # Índices para mejorar rendimiento
    indices = [
        'CREATE INDEX IF NOT EXISTS idx_conteos_fecha ON conteos(fecha)',
        'CREATE INDEX IF NOT EXISTS idx_conteos_usuario ON conteos(usuario)',
        'CREATE INDEX IF NOT EXISTS idx_conteos_codigo ON conteos(codigo_producto)',
        'CREATE INDEX IF NOT EXISTS idx_conteos_marca ON conteos(marca)',
        'CREATE INDEX IF NOT EXISTS idx_productos_marca ON productos(marca)'
    ]
    
    for idx in indices:
        try:
            cursor.execute(idx)
        except:
            pass
    
    conn.commit()
    conn.close()

# Inicializar DB al importar
init_database()

# ==============================================
# FUNCIONES PARA USUARIOS
# ==============================================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verificar_login(username, password):
    """Verificar credenciales de usuario"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT username, nombre, rol FROM usuarios 
        WHERE username = ? AND password = ? AND activo = 1
    ''', (username, hash_password(password)))
    
    usuario = cursor.fetchone()
    conn.close()
    
    if usuario:
        return True, usuario[0], usuario[1], usuario[2]
    return False, None, None, None

def crear_usuario(username, nombre, password, rol):
    """Crear nuevo usuario"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO usuarios (username, nombre, password, rol)
            VALUES (?, ?, ?, ?)
        ''', (username, nombre, hash_password(password), rol))
        conn.commit()
        return True, "Usuario creado correctamente"
    except sqlite3.IntegrityError:
        return False, "El nombre de usuario ya existe"
    finally:
        conn.close()

def obtener_todos_usuarios():
    """Obtener todos los usuarios"""
    conn = get_connection()
    df = pd.read_sql_query('''
        SELECT username, nombre, rol, activo FROM usuarios ORDER BY username
    ''', conn)
    conn.close()
    return df

# ==============================================
# FUNCIONES PARA MARCAS
# ==============================================

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

# ==============================================
# FUNCIONES PARA PRODUCTOS
# ==============================================

def limpiar_codigo(codigo):
    """Limpiar código de producto"""
    return str(codigo).strip().replace("\n", "").replace("\r", "") if codigo else ""

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
    """Guardar múltiples productos en batch"""
    if not productos_list:
        return
    
    conn = get_connection()
    cursor = conn.cursor()
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

def obtener_producto_por_codigo(codigo):
    """Obtener un producto por su código"""
    codigo_limpio = limpiar_codigo(codigo)
    conn = get_connection()
    
    query = '''
        SELECT codigo, producto, marca, area, stock_sistema 
        FROM productos 
        WHERE codigo = ? AND activo = 1
    '''
    df = pd.read_sql_query(query, conn, params=[codigo_limpio])
    conn.close()
    
    if not df.empty:
        return df.iloc[0].to_dict()
    return None

# ==============================================
# FUNCIONES PARA CONTEOS/ESCANEOS
# ==============================================

def registrar_escaneo(usuario, codigo, cantidad):
    """Registrar un escaneo individual"""
    codigo_limpio = limpiar_codigo(codigo)
    
    # Obtener producto
    producto = obtener_producto_por_codigo(codigo_limpio)
    if not producto:
        return False, "Producto no encontrado"
    
    # Calcular total acumulado del día para este producto
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT SUM(cantidad_escaneada) as total 
        FROM conteos 
        WHERE codigo_producto = ? AND usuario = ? AND DATE(fecha) = DATE('now')
    ''', (codigo_limpio, usuario))
    
    result = cursor.fetchone()
    total_anterior = result[0] if result[0] else 0
    nuevo_total = total_anterior + cantidad
    
    # Registrar el escaneo
    cursor.execute('''
        INSERT INTO conteos 
        (fecha, usuario, codigo_producto, producto, marca, area, 
         stock_sistema, cantidad_escaneada, total_acumulado, diferencia)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now(), 
        usuario, 
        codigo_limpio, 
        producto['producto'],
        producto['marca'],
        producto['area'],
        producto['stock_sistema'],
        cantidad,
        nuevo_total,
        nuevo_total - producto['stock_sistema']
    ))
    
    conn.commit()
    conn.close()
    
    return True, {
        'producto': producto,
        'total_anterior': total_anterior,
        'nuevo_total': nuevo_total,
        'diferencia': nuevo_total - producto['stock_sistema']
    }

def obtener_escaneos_hoy(usuario=None, codigo=None):
    """Obtener escaneos de hoy"""
    conn = get_connection()
    
    query = '''
        SELECT 
            fecha as timestamp,
            usuario,
            codigo_producto as codigo,
            producto,
            marca,
            area,
            cantidad_escaneada,
            total_acumulado,
            stock_sistema,
            diferencia,
            tipo_operacion
        FROM conteos 
        WHERE DATE(fecha) = DATE('now')
    '''
    params = []
    
    if usuario:
        query += " AND usuario = ?"
        params.append(usuario)
    
    if codigo:
        query += " AND codigo_producto = ?"
        params.append(codigo)
    
    query += " ORDER BY fecha DESC"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def obtener_total_escaneado_hoy(usuario, codigo):
    """Obtener total escaneado hoy para un usuario y producto"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT SUM(cantidad_escaneada) as total 
        FROM conteos 
        WHERE codigo_producto = ? AND usuario = ? AND DATE(fecha) = DATE('now')
    ''', (codigo, usuario))
    
    result = cursor.fetchone()
    conn.close()
    return result[0] if result[0] else 0

def obtener_resumen_conteos_hoy():
    """Obtener resumen de conteos de hoy"""
    conn = get_connection()
    
    query = '''
        SELECT 
            usuario,
            codigo_producto as codigo,
            producto,
            marca,
            area,
            stock_sistema,
            MAX(total_acumulado) as conteo_fisico,
            SUM(cantidad_escaneada) as total_escaneado,
            MAX(total_acumulado) - stock_sistema as diferencia
        FROM conteos 
        WHERE DATE(fecha) = DATE('now')
        GROUP BY codigo_producto, usuario
        ORDER BY fecha DESC
    '''
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def obtener_historial_completo(limite=1000):
    """Obtener historial completo de escaneos"""
    conn = get_connection()
    
    query = '''
        SELECT 
            fecha as timestamp,
            usuario,
            codigo_producto as codigo,
            producto,
            marca,
            area,
            cantidad_escaneada,
            total_acumulado,
            stock_sistema,
            diferencia,
            tipo_operacion
        FROM conteos 
        ORDER BY fecha DESC
        LIMIT ?
    '''
    
    df = pd.read_sql_query(query, conn, params=[limite])
    conn.close()
    return df

# ==============================================
# FUNCIONES PARA REPORTES POR MARCA
# ==============================================

def obtener_resumen_por_marca():
    """Obtener resumen completo por marca"""
    conn = get_connection()
    
    query = '''
        WITH escaneos_hoy AS (
            SELECT 
                codigo_producto,
                SUM(cantidad_escaneada) as total_contado,
                COUNT(*) as veces_escaneado
            FROM conteos
            WHERE DATE(fecha) = DATE('now')
            GROUP BY codigo_producto
        )
        SELECT 
            COALESCE(p.marca, 'SIN MARCA') as marca,
            COUNT(*) as total_productos,
            COALESCE(SUM(p.stock_sistema), 0) as stock_total_sistema,
            COUNT(eh.codigo_producto) as productos_contados,
            COUNT(*) - COUNT(eh.codigo_producto) as productos_no_escaneados,
            COALESCE(SUM(eh.total_contado), 0) as total_contado,
            CASE 
                WHEN COUNT(*) > 0 
                THEN ROUND(COUNT(eh.codigo_producto) * 100.0 / COUNT(*), 1)
                ELSE 0 
            END as porcentaje_avance,
            COALESCE(SUM(eh.total_contado), 0) - COALESCE(SUM(p.stock_sistema), 0) as diferencia_neta
        FROM productos p
        LEFT JOIN escaneos_hoy eh ON p.codigo = eh.codigo_producto
        WHERE p.activo = 1
        GROUP BY COALESCE(p.marca, 'SIN MARCA')
        ORDER BY marca
    '''
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Asegurar tipos de datos
    if not df.empty:
        numeric_cols = ['total_productos', 'stock_total_sistema', 'productos_contados', 
                       'productos_no_escaneados', 'total_contado', 'diferencia_neta']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    
    return df

def obtener_detalle_productos_por_marca(marca, solo_no_escaneados=False):
    """Obtener detalle de productos por marca"""
    conn = get_connection()
    
    query = '''
        WITH ultimos_escaneos AS (
            SELECT 
                codigo_producto,
                MAX(fecha) as ultima_fecha,
                usuario as ultimo_usuario
            FROM conteos
            WHERE DATE(fecha) = DATE('now')
            GROUP BY codigo_producto
        ),
        totales_hoy AS (
            SELECT 
                codigo_producto,
                SUM(cantidad_escaneada) as conteo_fisico
            FROM conteos
            WHERE DATE(fecha) = DATE('now')
            GROUP BY codigo_producto
        )
        SELECT 
            p.codigo,
            p.producto,
            COALESCE(p.marca, 'SIN MARCA') as marca,
            p.area,
            p.stock_sistema,
            COALESCE(th.conteo_fisico, 0) as conteo_fisico,
            COALESCE(th.conteo_fisico, 0) - p.stock_sistema as diferencia,
            CASE 
                WHEN th.conteo_fisico IS NULL THEN 'NO_ESCANEADO'
                WHEN COALESCE(th.conteo_fisico, 0) - p.stock_sistema = 0 THEN 'OK'
                WHEN ABS(COALESCE(th.conteo_fisico, 0) - p.stock_sistema) <= 2 THEN 'LEVE'
                ELSE 'CRITICA'
            END as estado,
            ue.ultima_fecha as ultimo_escaneo,
            ue.ultimo_usuario
        FROM productos p
        LEFT JOIN totales_hoy th ON p.codigo = th.codigo_producto
        LEFT JOIN ultimos_escaneos ue ON p.codigo = ue.codigo_producto
        WHERE p.activo = 1 AND COALESCE(p.marca, 'SIN MARCA') = ?
    '''
    
    params = [marca]
    
    if solo_no_escaneados:
        query = query.replace(
            "WHERE p.activo = 1 AND COALESCE(p.marca, 'SIN MARCA') = ?",
            "WHERE p.activo = 1 AND COALESCE(p.marca, 'SIN MARCA') = ? AND th.conteo_fisico IS NULL"
        )
    
    query += " ORDER BY p.area, p.producto"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if not df.empty:
        df['stock_sistema'] = pd.to_numeric(df['stock_sistema'], errors='coerce').fillna(0).astype(int)
        df['conteo_fisico'] = pd.to_numeric(df['conteo_fisico'], errors='coerce').fillna(0).astype(int)
        df['diferencia'] = pd.to_numeric(df['diferencia'], errors='coerce').fillna(0).astype(int)
    
    return df

def obtener_estadisticas_marca(marca):
    """Obtener estadísticas detalladas de una marca"""
    conn = get_connection()
    
    query = '''
        WITH escaneos_hoy AS (
            SELECT 
                codigo_producto,
                SUM(cantidad_escaneada) as total_contado,
                SUM(cantidad_escaneada) - p.stock_sistema as dif
            FROM conteos c
            JOIN productos p ON c.codigo_producto = p.codigo
            WHERE DATE(c.fecha) = DATE('now')
            GROUP BY c.codigo_producto
        )
        SELECT 
            COUNT(*) as total_productos,
            COALESCE(SUM(stock_sistema), 0) as stock_total,
            COUNT(eh.codigo_producto) as productos_contados,
            COUNT(*) - COUNT(eh.codigo_producto) as productos_no_contados,
            COALESCE(SUM(eh.total_contado), 0) as total_contado,
            SUM(CASE WHEN eh.dif = 0 THEN 1 ELSE 0 END) as exactos,
            SUM(CASE WHEN eh.dif > 0 AND eh.dif <= 2 THEN 1 ELSE 0 END) as sobrantes_leves,
            SUM(CASE WHEN eh.dif < 0 AND eh.dif >= -2 THEN 1 ELSE 0 END) as faltantes_leves,
            SUM(CASE WHEN ABS(eh.dif) > 2 THEN 1 ELSE 0 END) as diferencias_criticas,
            COALESCE(SUM(eh.total_contado), 0) - COALESCE(SUM(stock_sistema), 0) as diferencia_neta
        FROM productos p
        LEFT JOIN escaneos_hoy eh ON p.codigo = eh.codigo_producto
        WHERE p.activo = 1 AND COALESCE(p.marca, 'SIN MARCA') = ?
        GROUP BY COALESCE(p.marca, 'SIN MARCA')
    '''
    
    df = pd.read_sql_query(query, conn, params=[marca])
    conn.close()
    
    if not df.empty:
        stats = df.iloc[0].to_dict()
        for key in stats:
            if pd.isna(stats[key]):
                stats[key] = 0
        return stats
    else:
        return {
            'total_productos': 0, 'stock_total': 0, 'productos_contados': 0,
            'productos_no_contados': 0, 'total_contado': 0, 'exactos': 0,
            'sobrantes_leves': 0, 'faltantes_leves': 0, 'diferencias_criticas': 0,
            'diferencia_neta': 0
        }