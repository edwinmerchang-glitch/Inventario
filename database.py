import os
from supabase import create_client, Client
import sqlite3
import pandas as pd
import streamlit as st

supabase: Client = None

def init_supabase():
    global supabase
    if supabase is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            print("⚠️ Usando SQLite local")
            return None
        
        try:
            supabase = create_client(url, key)
            # Verificar conexión
            supabase.table("users").select("*").limit(1).execute()
            print("✅ Conectado a Supabase correctamente")
        except Exception as e:
            print(f"❌ Error conectando a Supabase: {e}")
            supabase = None
            
    return supabase

def get_connection():
    """Obtiene conexión compatible con el código existente"""
    client = init_supabase()
    if client is None:
        # Usar /tmp para escritura en Azure (read-write)
        db_path = "/tmp/inventario.db"
        conn = sqlite3.connect(db_path, check_same_thread=False)
        
        # Crear tablas si no existen
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS productos
                    (codigo TEXT PRIMARY KEY, 
                     producto TEXT, 
                     marca TEXT, 
                     area TEXT, 
                     stock_sistema INTEGER)''')
        
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
        
        c.execute('''CREATE TABLE IF NOT EXISTS usuarios
                    (username TEXT PRIMARY KEY,
                     nombre TEXT,
                     password TEXT,
                     rol TEXT,
                     activo TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS marcas
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     nombre TEXT UNIQUE)''')
        
        conn.commit()
        return conn
    
    return client

# ======================================================
# FUNCIONES PARA PRODUCTOS
# ======================================================

def obtener_todos_productos(marca_filtro='Todas'):
    """
    Obtener todos los productos como DataFrame
    Si marca_filtro no es 'Todas', filtra por esa marca
    """
    conn = get_connection()
    
    if isinstance(conn, sqlite3.Connection):
        if marca_filtro != 'Todas':
            query = "SELECT codigo, producto, marca, area, stock_sistema FROM productos WHERE marca = ?"
            df = pd.read_sql_query(query, conn, params=[marca_filtro])
        else:
            df = pd.read_sql_query("SELECT codigo, producto, marca, area, stock_sistema FROM productos", conn)
        conn.close()
    else:
        # Supabase
        try:
            if marca_filtro != 'Todas':
                response = conn.table("productos").select("*").eq("marca", marca_filtro).execute()
            else:
                response = conn.table("productos").select("*").execute()
            
            if response.data:
                df = pd.DataFrame(response.data)
            else:
                df = pd.DataFrame(columns=["codigo", "producto", "marca", "area", "stock_sistema"])
        except Exception as e:
            print(f"Error en Supabase: {e}")
            df = pd.DataFrame(columns=["codigo", "producto", "marca", "area", "stock_sistema"])
    
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
    
    if isinstance(conn, sqlite3.Connection):
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO productos 
                    (codigo, producto, marca, area, stock_sistema) 
                    VALUES (?, ?, ?, ?, ?)''',
                 (codigo, producto, marca, area, stock_sistema))
        conn.commit()
        conn.close()
    else:
        # Supabase
        data = {
            "codigo": codigo,
            "producto": producto,
            "marca": marca,
            "area": area,
            "stock_sistema": stock_sistema
        }
        try:
            conn.table("productos").upsert(data, on_conflict="codigo").execute()
        except Exception as e:
            print(f"Error en Supabase: {e}")

def guardar_productos_batch(productos_list):
    """Guardar múltiples productos en batch"""
    if not productos_list:
        return
    
    conn = get_connection()
    
    if isinstance(conn, sqlite3.Connection):
        c = conn.cursor()
        for prod in productos_list:
            c.execute('''INSERT OR REPLACE INTO productos 
                        (codigo, producto, marca, area, stock_sistema) 
                        VALUES (?, ?, ?, ?, ?)''',
                     (prod['codigo'], prod['producto'], prod['marca'], 
                      prod['area'], prod['stock_sistema']))
        conn.commit()
        conn.close()
    else:
        # Supabase - batch insert
        try:
            conn.table("productos").upsert(productos_list, on_conflict="codigo").execute()
        except Exception as e:
            print(f"Error en Supabase batch: {e}")

def eliminar_producto(codigo):
    """Eliminar un producto"""
    conn = get_connection()
    
    if isinstance(conn, sqlite3.Connection):
        c = conn.cursor()
        c.execute("DELETE FROM productos WHERE codigo = ?", (codigo,))
        conn.commit()
        conn.close()
    else:
        try:
            conn.table("productos").delete().eq("codigo", codigo).execute()
        except Exception as e:
            print(f"Error en Supabase: {e}")

# ======================================================
# FUNCIONES PARA MARCAS
# ======================================================

def obtener_todas_marcas():
    """Obtener lista de todas las marcas"""
    conn = get_connection()
    
    if isinstance(conn, sqlite3.Connection):
        try:
            df = pd.read_sql_query("SELECT DISTINCT marca FROM productos WHERE marca IS NOT NULL AND marca != '' ORDER BY marca", conn)
            conn.close()
            marcas = df['marca'].tolist() if not df.empty else []
        except:
            conn.close()
            marcas = []
    else:
        try:
            response = conn.table("productos").select("marca").execute()
            if response.data:
                marcas = list(set([item['marca'] for item in response.data if item.get('marca')]))
                marcas.sort()
            else:
                marcas = []
        except Exception as e:
            print(f"Error en Supabase: {e}")
            marcas = []
    
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
    
    if isinstance(conn, sqlite3.Connection):
        try:
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO marcas (nombre) VALUES (?)", (nombre_marca,))
            conn.commit()
            conn.close()
            return True
        except:
            conn.close()
            return False
    else:
        # En Supabase, las marcas se manejan directamente en productos
        # Esta función solo verifica si existe
        try:
            data = {"nombre": nombre_marca}
            conn.table("marcas").upsert(data, on_conflict="nombre").execute()
            return True
        except:
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
    
    if isinstance(conn, sqlite3.Connection):
        c = conn.cursor()
        c.execute('''INSERT INTO conteos 
                    (fecha, usuario, codigo, producto, marca, area, stock_sistema, conteo_fisico, diferencia) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (fecha, usuario, codigo, producto, marca, area, stock_sistema, conteo_fisico, diferencia))
        conn.commit()
        conn.close()
    else:
        data = {
            "fecha": fecha,
            "usuario": usuario,
            "codigo": codigo,
            "producto": producto,
            "marca": marca,
            "area": area,
            "stock_sistema": stock_sistema,
            "conteo_fisico": conteo_fisico,
            "diferencia": diferencia
        }
        try:
            conn.table("conteos").insert(data).execute()
        except Exception as e:
            print(f"Error en Supabase: {e}")

def obtener_conteos_usuario(usuario, fecha=None):
    """Obtener conteos de un usuario específico"""
    conn = get_connection()
    
    if isinstance(conn, sqlite3.Connection):
        if fecha:
            query = "SELECT * FROM conteos WHERE usuario = ? AND date(fecha) = date(?)"
            df = pd.read_sql_query(query, conn, params=[usuario, fecha])
        else:
            query = "SELECT * FROM conteos WHERE usuario = ?"
            df = pd.read_sql_query(query, conn, params=[usuario])
        conn.close()
    else:
        try:
            query = conn.table("conteos").select("*").eq("usuario", usuario)
            if fecha:
                query = query.eq("fecha", fecha)
            response = query.execute()
            if response.data:
                df = pd.DataFrame(response.data)
            else:
                df = pd.DataFrame()
        except Exception as e:
            print(f"Error en Supabase: {e}")
            df = pd.DataFrame()
    
    return df

def limpiar_todos_conteos():
    """Eliminar TODOS los registros de conteo"""
    conn = get_connection()
    
    if isinstance(conn, sqlite3.Connection):
        c = conn.cursor()
        c.execute("DELETE FROM conteos")
        conn.commit()
        conn.close()
    else:
        try:
            # En Supabase, necesitarías DELETE sin condición (peligroso)
            # Mejor implementar con precaución
            conn.table("conteos").delete().neq("id", 0).execute()
        except Exception as e:
            print(f"Error en Supabase: {e}")

# ======================================================
# FUNCIONES PARA REPORTES
# ======================================================

def obtener_resumen_por_marca():
    """Obtener resumen de conteos agrupado por marca"""
    conn = get_connection()
    
    if isinstance(conn, sqlite3.Connection):
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
    else:
        # Esta consulta es más compleja en Supabase, requeriría múltiples llamadas
        df = pd.DataFrame(columns=["marca", "total_productos", "productos_contados", 
                                   "total_contado", "stock_total", "diferencia_neta"])
    
    return df