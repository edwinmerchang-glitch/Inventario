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

    # Tabla de usuarios
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        nombre TEXT,
        rol TEXT DEFAULT 'inventario'
    )
    ''')

    # Tabla de marcas (nueva)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS marcas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE,
        activo INTEGER DEFAULT 1
    )
    ''')

    # Insertar usuario admin por defecto
    cursor.execute("INSERT OR IGNORE INTO usuarios(username, nombre, rol) VALUES('admin', 'Administrador', 'admin')")

    # Insertar marcas por defecto
    marcas_default = ['GENVEN', 'LETI', 'OTROS', 'SIN MARCA']
    for marca in marcas_default:
        cursor.execute("INSERT OR IGN INTO marcas(nombre) VALUES(?)", (marca,))

    conn.commit()
    conn.close()


def guardar_producto(codigo, producto, marca, area, stock):
    """Guardar un producto individual"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO productos 
    (codigo, producto, marca, area, stock_sistema, fecha_actualizacion)
    VALUES (?,?,?,?,?,?)
    """, (codigo, producto, marca, area, stock, datetime.now()))

    conn.commit()
    conn.close()


def guardar_productos_batch(productos_lista):
    """Guardar múltiples productos en batch (optimizado)"""
    if not productos_lista:
        return 0
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Preparar datos para inserción masiva
    datos = []
    ahora = datetime.now()
    
    for prod in productos_lista:
        datos.append((
            prod['codigo'],
            prod['producto'],
            prod.get('marca', 'SIN MARCA'),
            prod.get('area', ''),
            int(prod.get('stock_sistema', 0)),
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
    """Obtener un producto por código"""
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


def obtener_todos_productos(marca_filtro="Todas"):
    """Obtener todos los productos activos, opcionalmente filtrados por marca"""
    conn = get_connection()
    
    if marca_filtro and marca_filtro != "Todas":
        df = pd.read_sql_query(
            "SELECT * FROM productos WHERE activo=1 AND marca=? ORDER BY codigo", 
            conn, 
            params=(marca_filtro,)
        )
    else:
        df = pd.read_sql_query("SELECT * FROM productos WHERE activo=1 ORDER BY codigo", conn)
    
    conn.close()
    return df


def obtener_todas_marcas():
    """Obtener todas las marcas disponibles"""
    conn = get_connection()
    df = pd.read_sql_query("SELECT nombre FROM marcas WHERE activo=1 ORDER BY nombre", conn)
    conn.close()
    
    if not df.empty:
        return df['nombre'].tolist()
    return ['SIN MARCA', 'GENVEN', 'LETI', 'OTROS']


def crear_marca(nombre_marca):
    """Crear una nueva marca si no existe"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT OR IGNORE INTO marcas(nombre) VALUES(?)", (nombre_marca.upper(),))
        conn.commit()
        success = cursor.rowcount > 0
    except:
        success = False
    finally:
        conn.close()
    
    return success


def registrar_conteo(usuario, codigo, producto, marca, area, stock_sistema, conteo_fisico):
    """Registrar un conteo en la base de datos"""
    diferencia = conteo_fisico - stock_sistema
    
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
        datetime.now(), usuario, codigo, producto, marca, area,
        stock_sistema, conteo_fisico, diferencia, tipo
    ))
    
    conn.commit()
    conn.close()


def obtener_resumen_por_marca():
    """Obtener resumen estadístico por marca"""
    conn = get_connection()
    
    query = """
    WITH conteos_agrupados AS (
        SELECT 
            p.marca,
            p.codigo,
            p.producto,
            p.stock_sistema,
            COALESCE((
                SELECT SUM(c.conteo_fisico) 
                FROM conteos c 
                WHERE c.codigo_producto = p.codigo 
                AND DATE(c.fecha) = DATE('now', 'localtime')
            ), 0) as conteo_fisico,
            CASE WHEN EXISTS (
                SELECT 1 FROM conteos c 
                WHERE c.codigo_producto = p.codigo 
                AND DATE(c.fecha) = DATE('now', 'localtime')
            ) THEN 1 ELSE 0 END as fue_contado
        FROM productos p
        WHERE p.activo = 1
    )
    SELECT 
        marca,
        COUNT(*) as total_productos,
        SUM(fue_contado) as productos_contados,
        SUM(CASE WHEN fue_contado = 0 THEN 1 ELSE 0 END) as productos_no_escaneados,
        ROUND(100.0 * SUM(fue_contado) / COUNT(*), 1) as porcentaje_avance,
        SUM(stock_sistema) as stock_total_sistema,
        SUM(conteo_fisico) as total_contado,
        SUM(conteo_fisico - stock_sistema) as diferencia_neta
    FROM conteos_agrupados
    GROUP BY marca
    ORDER BY marca
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        return pd.DataFrame(columns=['marca', 'total_productos', 'productos_contados', 
                                    'productos_no_escaneados', 'porcentaje_avance', 
                                    'stock_total_sistema', 'total_contado', 'diferencia_neta'])
    
    # Llenar valores nulos
    df = df.fillna({
        'productos_contados': 0,
        'productos_no_escaneados': 0,
        'porcentaje_avance': 0,
        'stock_total_sistema': 0,
        'total_contado': 0,
        'diferencia_neta': 0
    })
    
    return df


def obtener_detalle_productos_por_marca(marca, solo_no_escaneados=False):
    """Obtener detalle de productos para una marca específica"""
    conn = get_connection()
    
    # Obtener conteos de hoy
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    query = """
    WITH ultimos_conteos AS (
        SELECT 
            codigo_producto,
            MAX(fecha) as ultima_fecha,
            SUM(conteo_fisico) as total_conteo,
            usuario as ultimo_usuario
        FROM conteos
        WHERE DATE(fecha) = ?
        GROUP BY codigo_producto
    )
    SELECT 
        p.codigo,
        p.producto,
        p.area,
        p.stock_sistema,
        COALESCE(uc.total_conteo, 0) as conteo_fisico,
        COALESCE(uc.total_conteo, 0) - p.stock_sistema as diferencia,
        CASE 
            WHEN uc.codigo_producto IS NULL THEN 'NO_ESCANEADO'
            WHEN (COALESCE(uc.total_conteo, 0) - p.stock_sistema) = 0 THEN 'OK'
            WHEN ABS(COALESCE(uc.total_conteo, 0) - p.stock_sistema) <= 2 THEN 'LEVE'
            ELSE 'CRITICA'
        END as estado,
        uc.ultima_fecha as ultimo_escaneo,
        uc.ultimo_usuario
    FROM productos p
    LEFT JOIN ultimos_conteos uc ON p.codigo = uc.codigo_producto
    WHERE p.activo = 1 AND p.marca = ?
    """
    
    params = [hoy, marca]
    
    if solo_no_escaneados:
        query += " AND uc.codigo_producto IS NULL"
    
    query += " ORDER BY p.producto"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    return df


def obtener_estadisticas_marca(marca):
    """Obtener estadísticas detalladas para una marca"""
    conn = get_connection()
    
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    query = """
    WITH conteos_del_dia AS (
        SELECT 
            p.codigo,
            p.stock_sistema,
            COALESCE((
                SELECT SUM(c.conteo_fisico) 
                FROM conteos c 
                WHERE c.codigo_producto = p.codigo 
                AND DATE(c.fecha) = ?
            ), 0) as conteo_fisico
        FROM productos p
        WHERE p.activo = 1 AND p.marca = ?
    )
    SELECT 
        COUNT(*) as total_productos,
        SUM(CASE WHEN conteo_fisico > 0 THEN 1 ELSE 0 END) as productos_contados,
        SUM(CASE WHEN conteo_fisico = 0 THEN 1 ELSE 0 END) as productos_no_contados,
        SUM(stock_sistema) as stock_total,
        SUM(conteo_fisico) as total_contado,
        SUM(conteo_fisico - stock_sistema) as diferencia_neta,
        SUM(CASE WHEN (conteo_fisico - stock_sistema) = 0 AND conteo_fisico > 0 THEN 1 ELSE 0 END) as exactos,
        SUM(CASE WHEN (conteo_fisico - stock_sistema) > 0 AND (conteo_fisico - stock_sistema) <= 2 THEN 1 ELSE 0 END) as sobrantes_leves,
        SUM(CASE WHEN (conteo_fisico - stock_sistema) < 0 AND (conteo_fisico - stock_sistema) >= -2 THEN 1 ELSE 0 END) as faltantes_leves,
        SUM(CASE WHEN ABS(conteo_fisico - stock_sistema) > 2 THEN 1 ELSE 0 END) as diferencias_criticas
    FROM conteos_del_dia
    """
    
    df = pd.read_sql_query(query, conn, params=[hoy, marca])
    conn.close()
    
    if not df.empty:
        return df.iloc[0].to_dict()
    return {
        'total_productos': 0,
        'productos_contados': 0,
        'productos_no_contados': 0,
        'stock_total': 0,
        'total_contado': 0,
        'diferencia_neta': 0,
        'exactos': 0,
        'sobrantes_leves': 0,
        'faltantes_leves': 0,
        'diferencias_criticas': 0
    }