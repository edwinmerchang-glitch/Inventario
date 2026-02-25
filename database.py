import os
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import streamlit as st

# Variable global para el cliente de Supabase
supabase: Client = None

def init_supabase():
    """Inicializar conexión a Supabase"""
    global supabase
    
    # Si ya está inicializado, retornar
    if supabase is not None:
        return supabase
    
    # Obtener credenciales de variables de entorno
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    
    # Mostrar estado para debugging
    print(f"SUPABASE_URL: {'Configurada' if url else 'No configurada'}")
    print(f"SUPABASE_KEY: {'Configurada' if key else 'No configurada'}")
    
    if not url or not key:
        print("⚠️ Variables de Supabase no configuradas")
        return None
    
    try:
        supabase = create_client(url, key)
        # Verificar conexión
        supabase.table("productos").select("*").limit(1).execute()
        print("✅ Conectado a Supabase correctamente")
        return supabase
    except Exception as e:
        print(f"❌ Error conectando a Supabase: {e}")
        supabase = None
        return None

def obtener_todos_productos(marca_filtro="Todas"):
    """Obtener todos los productos"""
    client = init_supabase()
    
    if client is None:
        return pd.DataFrame(columns=["codigo", "producto", "marca", "area", "stock_sistema"])
    
    try:
        query = client.table("productos").select("*")
        
        if marca_filtro != "Todas":
            query = query.eq("marca", marca_filtro)
        
        response = query.execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            # Asegurar tipos de datos
            if 'stock_sistema' in df.columns:
                df['stock_sistema'] = pd.to_numeric(df['stock_sistema'], errors='coerce').fillna(0).astype(int)
            return df
        else:
            return pd.DataFrame(columns=["codigo", "producto", "marca", "area", "stock_sistema"])
    except Exception as e:
        print(f"Error obteniendo productos: {e}")
        return pd.DataFrame(columns=["codigo", "producto", "marca", "area", "stock_sistema"])

def guardar_producto(codigo, producto, marca, area, stock_sistema):
    """Guardar o actualizar un producto"""
    client = init_supabase()
    
    if client is None:
        print("No hay conexión a Supabase")
        return False
    
    try:
        data = {
            "codigo": str(codigo).strip(),
            "producto": producto,
            "marca": marca,
            "area": area,
            "stock_sistema": int(stock_sistema)
        }
        
        response = client.table("productos").upsert(data, on_conflict="codigo").execute()
        print(f"Producto guardado: {codigo}")
        return True
    except Exception as e:
        print(f"Error guardando producto: {e}")
        return False

def guardar_productos_batch(productos_list):
    """Guardar múltiples productos en batch"""
    client = init_supabase()
    
    if client is None:
        return False
    
    try:
        # Limpiar datos
        for prod in productos_list:
            prod['codigo'] = str(prod['codigo']).strip()
            prod['stock_sistema'] = int(prod['stock_sistema'])
        
        response = client.table("productos").upsert(productos_list, on_conflict="codigo").execute()
        print(f"Batch insert: {len(productos_list)} productos")
        return True
    except Exception as e:
        print(f"Error en batch insert: {e}")
        return False

def obtener_todas_marcas():
    """Obtener todas las marcas únicas"""
    client = init_supabase()
    
    if client is None:
        return []
    
    try:
        response = client.table("productos").select("marca").execute()
        if response.data:
            marcas = list(set([item['marca'] for item in response.data if item['marca']]))
            marcas.sort()
            return marcas
        return []
    except Exception as e:
        print(f"Error obteniendo marcas: {e}")
        return []

def registrar_conteo(usuario, codigo, producto, marca, area, stock_sistema, conteo_fisico):
    """Registrar un conteo"""
    client = init_supabase()
    
    if client is None:
        return False
    
    try:
        data = {
            "fecha": datetime.now().isoformat(),
            "usuario": usuario,
            "codigo": str(codigo).strip(),
            "producto": producto,
            "marca": marca,
            "area": area,
            "stock_sistema": int(stock_sistema),
            "conteo_fisico": int(conteo_fisico),
            "diferencia": int(conteo_fisico) - int(stock_sistema)
        }
        
        response = client.table("conteos").insert(data).execute()
        return True
    except Exception as e:
        print(f"Error registrando conteo: {e}")
        return False

def obtener_todos_conteos():
    """Obtener todos los conteos"""
    client = init_supabase()
    
    if client is None:
        return pd.DataFrame(columns=["fecha", "usuario", "codigo", "producto", "marca", "area", "stock_sistema", "conteo_fisico", "diferencia"])
    
    try:
        response = client.table("conteos").select("*").order("fecha", desc=True).execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame(columns=["fecha", "usuario", "codigo", "producto", "marca", "area", "stock_sistema", "conteo_fisico", "diferencia"])
    except Exception as e:
        print(f"Error obteniendo conteos: {e}")
        return pd.DataFrame(columns=["fecha", "usuario", "codigo", "producto", "marca", "area", "stock_sistema", "conteo_fisico", "diferencia"])

def guardar_escaneo(escaneo_data):
    """Guardar un escaneo"""
    client = init_supabase()
    
    if client is None:
        return False
    
    try:
        response = client.table("escaneos").insert(escaneo_data).execute()
        return True
    except Exception as e:
        print(f"Error guardando escaneo: {e}")
        return False

def obtener_todos_escaneos():
    """Obtener todos los escaneos"""
    client = init_supabase()
    
    if client is None:
        return pd.DataFrame(columns=["timestamp", "usuario", "codigo", "producto", "marca", "area", "cantidad_escaneada", "total_acumulado", "stock_sistema", "tipo_operacion"])
    
    try:
        response = client.table("escaneos").select("*").order("timestamp", desc=True).execute()
        if response.data:
            df = pd.DataFrame(response.data)
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        return pd.DataFrame(columns=["timestamp", "usuario", "codigo", "producto", "marca", "area", "cantidad_escaneada", "total_acumulado", "stock_sistema", "tipo_operacion"])
    except Exception as e:
        print(f"Error obteniendo escaneos: {e}")
        return pd.DataFrame(columns=["timestamp", "usuario", "codigo", "producto", "marca", "area", "cantidad_escaneada", "total_acumulado", "stock_sistema", "tipo_operacion"])

def obtener_total_escaneado_hoy(usuario, codigo):
    """Obtener total escaneado hoy por usuario y código"""
    client = init_supabase()
    
    if client is None:
        return 0
    
    try:
        hoy = datetime.now().strftime("%Y-%m-%d")
        response = client.table("escaneos") \
            .select("cantidad_escaneada") \
            .eq("usuario", usuario) \
            .eq("codigo", str(codigo).strip()) \
            .gte("timestamp", f"{hoy}T00:00:00") \
            .lte("timestamp", f"{hoy}T23:59:59") \
            .execute()
        
        if response.data:
            total = sum([item['cantidad_escaneada'] for item in response.data])
            return total
        return 0
    except Exception as e:
        print(f"Error obteniendo total escaneado: {e}")
        return 0

def obtener_total_escaneos_usuario_hoy(usuario):
    """Obtener total de escaneos de un usuario hoy"""
    client = init_supabase()
    
    if client is None:
        return 0
    
    try:
        hoy = datetime.now().strftime("%Y-%m-%d")
        response = client.table("escaneos") \
            .select("id") \
            .eq("usuario", usuario) \
            .gte("timestamp", f"{hoy}T00:00:00") \
            .lte("timestamp", f"{hoy}T23:59:59") \
            .execute()
        
        return len(response.data) if response.data else 0
    except Exception as e:
        print(f"Error obteniendo total escaneos usuario: {e}")
        return 0

def limpiar_todos_conteos():
    """Limpiar todos los registros de conteo"""
    client = init_supabase()
    
    if client is None:
        return False
    
    try:
        client.table("conteos").delete().neq("id", 0).execute()
        client.table("escaneos").delete().neq("id", 0).execute()
        return True
    except Exception as e:
        print(f"Error limpiando conteos: {e}")
        return False