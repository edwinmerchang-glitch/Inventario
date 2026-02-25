import os
from supabase import create_client, Client
import sqlite3
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
        
        conn.commit()
        return conn
    
    return client

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

# Similar para las otras funciones...