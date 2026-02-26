import sqlite3
import pandas as pd
import os

# ======================================================
# CONEXIÓN A BASE DE DATOS SQLITE
# ======================================================

def get_connection():
    """Obtiene conexión a SQLite"""
    # Usar /tmp para escritura en Azure (read-write)
    db_path = "/tmp/inventario.db"
    conn = sqlite3.connect(db_path, check_same_thread=False)
    
    # Crear tablas si no existen
    c = conn.cursor()
    
    # Tabla de productos
    c.execute('''CREATE TABLE IF NOT EXISTS productos
                (codigo TEXT PRIMARY KEY, 
                 producto TEXT, 
                 marca TEXT, 
                 area TEXT, 
                 stock_sistema INTEGER)''')
    
    # Tabla de conteos
    c.execute('''CREATE TABLE IF NOT EXISTS conteos
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 fecha TEXT,
                 usuario TEXT,
                 codigo TEXT,
                 producto TEXT,
                 marca TEXT,
                 area TEXT,
                 stock_sistema INTEGER,
                 conteo_fisico INTEGER,
                 diferencia INTEGER)''')
    
    # Tabla de usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios
                (username TEXT PRIMARY KEY,
                 nombre TEXT,
                 password TEXT,
                 rol TEXT,
                 activo TEXT)''')
    
    # Tabla de marcas
    c.execute('''CREATE TABLE IF NOT EXISTS marcas
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 nombre TEXT UNIQUE)''')
    
    conn.commit()
    return conn

# ======================================================
# FUNCIONES PARA PRODUCTOS
# ======================================================

def obtener_todos_productos(marca_filtro='Todas'):
    """
    Obtener todos los productos como DataFrame
    Si marca_filtro no es 'Todas', filtra por esa marca
    """
    conn = get_connection()
    
    if marca_filtro != 'Todas':
        query = "SELECT codigo, producto, marca, area, stock_sistema FROM productos WHERE marca = ?"
        df = pd.read_sql_query(query, conn, params=[marca_filtro])
    else:
        df = pd.read_sql_query("SELECT codigo, producto, marca, area, stock_sistema FROM productos", conn)
    
    conn.close()
    
    # Asegurar tipos de datos
    if not df.empty:
        df['codigo'] = df['codigo'].astype(str)
        df['stock_sistema'] = pd.to_numeric(df['stock_sistema'], errors='coerce').fillna(0).astype(int)
        if 'marca' not in df.columns:
            df['marca'] = 'SIN MARCA'
        else:
            df['marca'] = df['marca'].fillna('SIN MARCA')
    
    return df

def guardar_producto(codigo, producto, marca, area, stock_sistema):
    """Guardar o actualizar un producto"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO productos 
                (codigo, producto, marca, area, stock_sistema) 
                VALUES (?, ?, ?, ?, ?)''',
             (codigo, producto, marca, area, stock_sistema))
    conn.commit()
    conn.close()

def guardar_productos_batch(productos_list):
    """Guardar múltiples productos en batch"""
    if not productos_list:
        return
    
    conn = get_connection()
    c = conn.cursor()
    
    for prod in productos_list:
        c.execute('''INSERT OR REPLACE INTO productos 
                    (codigo, producto, marca, area, stock_sistema) 
                    VALUES (?, ?, ?, ?, ?)''',
                 (prod['codigo'], prod['producto'], prod['marca'], 
                  prod['area'], prod['stock_sistema']))
    
    conn.commit()
    conn.close()

def eliminar_producto(codigo):
    """Eliminar un producto"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM productos WHERE codigo = ?", (codigo,))
    conn.commit()
    conn.close()

# ======================================================
# FUNCIONES PARA MARCAS
# ======================================================

def obtener_todas_marcas():
    """Obtener lista de todas las marcas"""
    conn = get_connection()
    
    try:
        # Intentar obtener marcas de la tabla productos
        df = pd.read_sql_query("SELECT DISTINCT marca FROM productos WHERE marca IS NOT NULL AND marca != '' ORDER BY marca", conn)
        marcas = df['marca'].tolist() if not df.empty else []
    except:
        marcas = []
    
    conn.close()
    
    # Agregar marcas por defecto si no hay ninguna
    if not marcas:
        marcas = ["SIN MARCA", "GENVEN", "LETI", "OTROS"]
    
    return marcas

def crear_marca(nombre_marca):
    """Crear una nueva marca"""
    if not nombre_marca or nombre_marca.strip() == "":
        return False
    
    nombre_marca = nombre_marca.upper().strip()
    
    conn = get_connection()
    
    try:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO marcas (nombre) VALUES (?)", (nombre_marca,))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

# ======================================================
# FUNCIONES PARA CONTEO
# ======================================================

def registrar_conteo(usuario, codigo, producto, marca, area, stock_sistema, conteo_fisico):
    """Registrar un conteo físico"""
    import datetime
    
    conn = get_connection()
    fecha = datetime.datetime.now().isoformat()
    diferencia = conteo_fisico - stock_sistema
    
    c = conn.cursor()
    c.execute('''INSERT INTO conteos 
                (fecha, usuario, codigo, producto, marca, area, stock_sistema, conteo_fisico, diferencia) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
             (fecha, usuario, codigo, producto, marca, area, stock_sistema, conteo_fisico, diferencia))
    conn.commit()
    conn.close()

def obtener_conteos_usuario(usuario, fecha=None):
    """Obtener conteos de un usuario específico"""
    conn = get_connection()
    
    if fecha:
        query = "SELECT * FROM conteos WHERE usuario = ? AND date(fecha) = date(?)"
        df = pd.read_sql_query(query, conn, params=[usuario, fecha])
    else:
        query = "SELECT * FROM conteos WHERE usuario = ?"
        df = pd.read_sql_query(query, conn, params=[usuario])
    
    conn.close()
    return df

def limpiar_todos_conteos():
    """Eliminar TODOS los registros de conteo"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM conteos")
    conn.commit()
    conn.close()

# ======================================================
# FUNCIONES PARA REPORTES
# ======================================================

def obtener_resumen_por_marca():
    """Obtener resumen de conteos agrupado por marca"""
    conn = get_connection()
    
    query = """
    SELECT 
        p.marca,
        COUNT(DISTINCT p.codigo) as total_productos,
        COUNT(DISTINCT c.codigo) as productos_contados,
        COALESCE(SUM(c.conteo_fisico), 0) as total_contado,
        COALESCE(SUM(p.stock_sistema), 0) as stock_total,
        COALESCE(SUM(c.diferencia), 0) as diferencia_neta
    FROM productos p
    LEFT JOIN conteos c ON p.codigo = c.codigo
    GROUP BY p.marca
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df