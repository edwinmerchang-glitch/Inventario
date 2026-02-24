import streamlit as st
import pandas as pd
import os
import hashlib
from datetime import datetime
import time
import database as db  # Importamos las funciones de database.py

# ======================================================
# CONFIGURACIÓN GENERAL
# ======================================================
st.set_page_config(
    page_title="Sistema de Conteo de Inventario",
    page_icon="📦",
    layout="wide",  # Cambiamos a wide para mejor visualización
    initial_sidebar_state="expanded"
)

# USAR LA MISMA RUTA EN TODO EL PROGRAMA
ARCHIVO_STOCK = "stock_sistema.csv"
ARCHIVO_CONTEOS = "conteos.csv"
ARCHIVO_USUARIOS = "usuarios.csv"
ARCHIVO_ESCANEOS = "escaneos_detallados.csv"

# ======================================================
# SISTEMA DE AUTENTICACIÓN Y PERMISOS
# ======================================================
def inicializar_sesion():
    """Inicializar variables de sesión"""
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False
        st.session_state.usuario = None
        st.session_state.nombre = None
        st.session_state.rol = None
        st.session_state.pagina_actual = "🏠 Dashboard"
    
    # Variables específicas para conteo físico
    if 'producto_actual_conteo' not in st.session_state:
        st.session_state.producto_actual_conteo = None
    if 'conteo_actual_session' not in st.session_state:
        st.session_state.conteo_actual_session = 0
    if 'total_escaneos_session' not in st.session_state:
        st.session_state.total_escaneos_session = 0
    if 'historial_escaneos' not in st.session_state:
        st.session_state.historial_escaneos = []
    if 'marca_seleccionada' not in st.session_state:
        st.session_state.marca_seleccionada = "Todas"

def hash_password(password):
    """Hashear contraseña para seguridad"""
    return hashlib.sha256(password.encode()).hexdigest()

def cargar_usuarios():
    """Cargar usuarios desde CSV"""
    if os.path.exists(ARCHIVO_USUARIOS):
        df = pd.read_csv(ARCHIVO_USUARIOS, dtype=str)
        return df
    else:
        usuarios_default = pd.DataFrame([
            ["admin", "Administrador", hash_password("admin123"), "admin", "1"],
            ["inventario", "Operador Inventario", hash_password("inventario123"), "inventario", "1"],
            ["consulta", "Usuario Consulta", hash_password("consulta123"), "consulta", "1"]
        ], columns=["username", "nombre", "password", "rol", "activo"])
        
        usuarios_default.to_csv(ARCHIVO_USUARIOS, index=False)
        return usuarios_default

def guardar_usuarios(df):
    """Guardar usuarios en CSV"""
    df.to_csv(ARCHIVO_USUARIOS, index=False)

def verificar_login(username, password):
    """Verificar credenciales de usuario"""
    usuarios_df = cargar_usuarios()
    
    if usuarios_df.empty:
        return False, None, None, None
    
    usuario_filtrado = usuarios_df[
        (usuarios_df["username"] == username) & 
        (usuarios_df["activo"] == "1")
    ]
    
    if usuario_filtrado.empty:
        return False, None, None, None
    
    usuario = usuario_filtrado.iloc[0]
    password_hash = hash_password(password)
    
    if usuario["password"] == password_hash:
        return True, usuario["username"], usuario["nombre"], usuario["rol"]
    
    return False, None, None, None

def crear_usuario(username, nombre, password, rol):
    """Crear nuevo usuario"""
    usuarios_df = cargar_usuarios()
    
    if username in usuarios_df["username"].values:
        return False, "El nombre de usuario ya existe"
    
    nuevo_usuario = pd.DataFrame([[username, nombre, hash_password(password), rol, "1"]], 
                                 columns=usuarios_df.columns)
    
    usuarios_df = pd.concat([usuarios_df, nuevo_usuario], ignore_index=True)
    guardar_usuarios(usuarios_df)
    
    return True, "Usuario creado correctamente"

def tiene_permiso(rol_requerido):
    """Verificar si el usuario tiene el permiso requerido"""
    if not st.session_state.autenticado:
        return False
    
    jerarquia = {
        "consulta": 1,
        "inventario": 2,
        "admin": 3
    }
    
    rol_actual = st.session_state.rol
    nivel_requerido = jerarquia.get(rol_requerido, 0)
    nivel_actual = jerarquia.get(rol_actual, 0)
    
    return nivel_actual >= nivel_requerido

# ======================================================
# FUNCIONES UTILITARIAS
# ======================================================
def limpiar_codigo(codigo):
    if codigo is None:
        return ""
    return str(codigo).strip().replace("\n", "").replace("\r", "")

def cargar_stock():
    """Cargar stock desde la base de datos asegurando columna marca"""
    df = db.obtener_todos_productos(st.session_state.get('marca_seleccionada', 'Todas'))
    
    # Asegurar que la columna 'marca' exista
    if 'marca' not in df.columns:
        df['marca'] = 'SIN MARCA'
    
    return df

def guardar_stock(df):
    """Guardar stock (adaptador para mantener compatibilidad)"""
    # Asegurar que la columna 'marca' exista
    if 'marca' not in df.columns:
        df['marca'] = 'SIN MARCA'
    
    for _, row in df.iterrows():
        db.guardar_producto(
            row['codigo'], 
            row['producto'], 
            row.get('marca', 'SIN MARCA'), 
            row['area'], 
            row['stock_sistema']
        )

def cargar_conteos():
    """Cargar conteos desde CSV (mantener compatibilidad)"""
    if os.path.exists(ARCHIVO_CONTEOS):
        df = pd.read_csv(ARCHIVO_CONTEOS)
        return df
    else:
        return pd.DataFrame(columns=["fecha", "usuario", "codigo", "producto", "area", "stock_sistema", "conteo_fisico", "diferencia"])

def guardar_conteos(df):
    """Guardar conteos en CSV (mantener compatibilidad)"""
    df.to_csv(ARCHIVO_CONTEOS, index=False)

def cargar_escaneos_detallados():
    """Cargar escaneos desde CSV"""
    if os.path.exists(ARCHIVO_ESCANEOS):
        try:
            df = pd.read_csv(ARCHIVO_ESCANEOS)
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            if 'cantidad_escaneada' in df.columns:
                df['cantidad_escaneada'] = pd.to_numeric(df['cantidad_escaneada'], errors='coerce').fillna(0).astype(int)
            if 'total_acumulado' in df.columns:
                df['total_acumulado'] = pd.to_numeric(df['total_acumulado'], errors='coerce').fillna(0).astype(int)
            if 'stock_sistema' in df.columns:
                df['stock_sistema'] = pd.to_numeric(df['stock_sistema'], errors='coerce').fillna(0).astype(int)
            return df
        except Exception as e:
            print(f"Error cargando escaneos: {e}")
            return pd.DataFrame(columns=["timestamp", "usuario", "codigo", "producto", "area", "cantidad_escaneada", "total_acumulado", "stock_sistema", "tipo_operacion"])
    else:
        return pd.DataFrame(columns=["timestamp", "usuario", "codigo", "producto", "area", "cantidad_escaneada", "total_acumulado", "stock_sistema", "tipo_operacion"])

# ======================================================
# FUNCIÓN CORREGIDA: GUARDAR ESCANEO DETALLADO CON MARCA
# ======================================================
def guardar_escaneo_detallado(escaneo_data):
    """Guardar UN escaneo individual PERMANENTEMENTE con marca incluida"""
    try:
        # Asegurar tipos de datos
        escaneo_data['cantidad_escaneada'] = int(escaneo_data['cantidad_escaneada'])
        escaneo_data['total_acumulado'] = int(escaneo_data['total_acumulado'])
        escaneo_data['stock_sistema'] = int(escaneo_data['stock_sistema'])
        
        # Asegurar que la marca esté presente
        if 'marca' not in escaneo_data:
            escaneo_data['marca'] = 'SIN MARCA'
        
        # Definir el orden de columnas para consistencia
        columnas_ordenadas = ['timestamp', 'usuario', 'codigo', 'producto', 'marca', 'area', 
                             'cantidad_escaneada', 'total_acumulado', 'stock_sistema', 'tipo_operacion']
        
        # Crear DataFrame con el orden correcto
        nuevo_registro = pd.DataFrame([{col: escaneo_data.get(col, None) for col in columnas_ordenadas}])
        
        if os.path.exists(ARCHIVO_ESCANEOS):
            df_existente = pd.read_csv(ARCHIVO_ESCANEOS)
            
            # Asegurar que el DataFrame existente tenga todas las columnas necesarias
            for col in columnas_ordenadas:
                if col not in df_existente.columns:
                    df_existente[col] = None
            
            # Reordenar columnas del df_existente
            df_existente = df_existente[columnas_ordenadas]
            
            # Concatenar
            df_final = pd.concat([df_existente, nuevo_registro], ignore_index=True)
        else:
            df_final = nuevo_registro
        
        # Guardar
        df_final.to_csv(ARCHIVO_ESCANEOS, index=False)
        
        # Actualizar sesión
        if 'historial_escaneos' not in st.session_state:
            st.session_state.historial_escaneos = []
        st.session_state.historial_escaneos.append(escaneo_data)
        
        return True, "Escaneo guardado permanentemente"
    except Exception as e:
        return False, f"Error al guardar escaneo: {str(e)}"

# ======================================================
# FUNCIÓN CORREGIDA: CARGAR ESCANEOS DETALLADOS
# ======================================================
def cargar_escaneos_detallados():
    """Cargar escaneos desde CSV asegurando columna marca"""
    columnas_requeridas = ["timestamp", "usuario", "codigo", "producto", "marca", "area", 
                          "cantidad_escaneada", "total_acumulado", "stock_sistema", "tipo_operacion"]
    
    if os.path.exists(ARCHIVO_ESCANEOS):
        try:
            df = pd.read_csv(ARCHIVO_ESCANEOS)
            
            # Asegurar que todas las columnas requeridas existan
            for col in columnas_requeridas:
                if col not in df.columns:
                    if col == 'marca':
                        df[col] = 'SIN MARCA'  # Valor por defecto para marca
                    else:
                        df[col] = None
            
            # Convertir tipos de datos
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            if 'cantidad_escaneada' in df.columns:
                df['cantidad_escaneada'] = pd.to_numeric(df['cantidad_escaneada'], errors='coerce').fillna(0).astype(int)
            if 'total_acumulado' in df.columns:
                df['total_acumulado'] = pd.to_numeric(df['total_acumulado'], errors='coerce').fillna(0).astype(int)
            if 'stock_sistema' in df.columns:
                df['stock_sistema'] = pd.to_numeric(df['stock_sistema'], errors='coerce').fillna(0).astype(int)
            
            return df
        except Exception as e:
            print(f"Error cargando escaneos: {e}")
            return pd.DataFrame(columns=columnas_requeridas)
    else:
        return pd.DataFrame(columns=columnas_requeridas)

# ======================================================
# FUNCIÓN CORREGIDA: ACTUALIZAR RESUMEN CONTEO (INCLUYE MARCA)
# ======================================================
def actualizar_resumen_conteo(usuario, codigo, producto, area, stock_sistema, nuevo_total, marca='SIN MARCA'):
    """Actualizar el resumen diario de conteos (ahora incluye marca)"""
    try:
        conteos_df = cargar_conteos()
        hoy = datetime.now().strftime("%Y-%m-%d")
        
        mask = ((conteos_df["usuario"] == usuario) & 
                (conteos_df["codigo"] == codigo) & 
                (conteos_df["fecha"].str.startswith(hoy)))
        
        if mask.any() and not conteos_df[mask].empty:
            conteos_df.loc[mask, ["conteo_fisico", "diferencia"]] = [nuevo_total, nuevo_total - stock_sistema]
        else:
            nuevo = pd.DataFrame([[
                f"{hoy} {datetime.now().strftime('%H:%M:%S')}", 
                usuario, 
                codigo, 
                producto,
                marca,  # Agregamos marca
                area, 
                stock_sistema, 
                nuevo_total, 
                nuevo_total - stock_sistema
            ]], columns=["fecha", "usuario", "codigo", "producto", "marca", "area", "stock_sistema", "conteo_fisico", "diferencia"])
            
            conteos_df = pd.concat([conteos_df, nuevo], ignore_index=True)
        
        guardar_conteos(conteos_df)
        return True
    except Exception as e:
        print(f"Error actualizando resumen: {e}")
        return False

# ======================================================
# FUNCIÓN CORREGIDA: CARGAR CONTEO (INCLUYE MARCA)
# ======================================================
def cargar_conteos():
    """Cargar conteos desde CSV con soporte para marca"""
    columnas_requeridas = ["fecha", "usuario", "codigo", "producto", "marca", "area", "stock_sistema", "conteo_fisico", "diferencia"]
    
    if os.path.exists(ARCHIVO_CONTEOS):
        df = pd.read_csv(ARCHIVO_CONTEOS)
        
        # Asegurar que todas las columnas requeridas existan
        for col in columnas_requeridas:
            if col not in df.columns:
                if col == 'marca':
                    df[col] = 'SIN MARCA'
                else:
                    df[col] = None
        
        return df
    else:
        return pd.DataFrame(columns=columnas_requeridas)

# ======================================================
# MODIFICAR LA FUNCIÓN mostrar_conteo_fisico PARA INCLUIR MARCA
# ======================================================
# Busca esta sección en mostrar_conteo_fisico (aproximadamente línea 680-700)
# y reemplázala con:

def procesar_escaneo_en_conteo(codigo_limpio, cantidad, producto_encontrado):
    """Función auxiliar para procesar escaneo (para mantener el código organizado)"""
    prod = producto_encontrado.iloc[0]
    
    # Obtener marca (asegurar que existe)
    marca = prod.get("marca", "SIN MARCA")
    if pd.isna(marca) or marca == "":
        marca = "SIN MARCA"
    
    # Calcular total anterior
    total_anterior = total_escaneado_hoy(st.session_state.nombre, codigo_limpio)
    nuevo_total = total_anterior + cantidad

    # --- GUARDAR ESCANEO CON MARCA ---
    timestamp_actual = datetime.now()
    
    escaneo_data = {
        "timestamp": timestamp_actual,
        "usuario": st.session_state.nombre,
        "codigo": codigo_limpio,
        "producto": prod["producto"],
        "marca": marca,  # ¡Importante!
        "area": prod["area"],
        "cantidad_escaneada": int(cantidad),
        "total_acumulado": int(nuevo_total),
        "stock_sistema": int(prod["stock_sistema"]),
        "tipo_operacion": "ESCANEO"
    }
    
    # Usar la función corregida
    guardar_escaneo_detallado(escaneo_data)

    # Registrar en base de datos (si aplica)
    db.registrar_conteo(
        st.session_state.nombre,
        codigo_limpio,
        prod["producto"],
        marca,  # Pasar marca
        prod["area"],
        int(prod["stock_sistema"]),
        nuevo_total
    )

    # Actualizar resumen de conteos con marca
    actualizar_resumen_conteo(
        st.session_state.nombre, 
        codigo_limpio, 
        prod["producto"],
        prod["area"], 
        int(prod["stock_sistema"]), 
        nuevo_total,
        marca  # Nuevo parámetro
    )

    # Actualizar sesión
    st.session_state.producto_actual_conteo = {
        'codigo': codigo_limpio,
        'nombre': prod["producto"],
        'marca': marca,
        'area': prod["area"],
        'stock_sistema': int(prod["stock_sistema"])
    }
    st.session_state.conteo_actual_session = nuevo_total
    st.session_state.total_escaneos_session += 1

    return True

# ======================================================
# PÁGINA DE LOGIN (CORREGIDA - TÍTULO CENTRADO)
# ======================================================
def mostrar_login():
    """Mostrar página de login con título centrado"""
    # Título centrado usando HTML + CSS
    st.markdown("""
        <h1 style='text-align: center; color: #1E88E5; font-size: 2.5rem; margin-bottom: 1rem;'>
            🔐 Sistema de Conteo de Inventario
        </h1>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            with st.form("login_form"):
                st.markdown("<h3 style='text-align: center;'>Inicio de Sesión</h3>", unsafe_allow_html=True)
                
                username = st.text_input("Usuario", placeholder="Ingrese su usuario")
                password = st.text_input("Contraseña", type="password", placeholder="Ingrese su contraseña")
                
                if st.form_submit_button("🚀 Ingresar", use_container_width=True):
                    if username and password:
                        autenticado, user, nombre, rol = verificar_login(username, password)
                        
                        if autenticado:
                            st.session_state.autenticado = True
                            st.session_state.usuario = user
                            st.session_state.nombre = nombre
                            st.session_state.rol = rol
                            st.session_state.pagina_actual = "🏠 Dashboard"
                            st.success(f"✅ Bienvenido, {nombre}!")
                            st.rerun()
                        else:
                            st.error("❌ Usuario o contraseña incorrectos")
                    else:
                        st.warning("⚠️ Complete todos los campos")
    
    st.markdown("---")
    st.markdown("<p style='text-align: center; color: gray;'>📦 Sistema de Conteo de Inventario • v2.0 creado por Edwin Merchan</p>", unsafe_allow_html=True)

# ======================================================
# BARRA LATERAL CON NAVEGACIÓN
# ======================================================
def mostrar_sidebar():
    """Mostrar barra lateral con navegación"""
    with st.sidebar:
        st.title(f"👤 {st.session_state.nombre}")
        st.write(f"**Rol:** {st.session_state.rol.upper()}")
        st.write(f"**Usuario:** {st.session_state.usuario}")
        st.markdown("---")
        
        st.subheader("📌 Navegación")
        
        opciones_disponibles = []
        opciones_disponibles.append("🏠 Dashboard")
        
        if tiene_permiso("inventario"):
            opciones_disponibles.append("📥 Carga Stock")
        
        if tiene_permiso("admin"):
            opciones_disponibles.append("📤 Importar Excel")
        
        if tiene_permiso("inventario"):
            opciones_disponibles.append("🔢 Conteo Físico")
        
        opciones_disponibles.append("📊 Reportes")
        opciones_disponibles.append("🏷️ Reporte por Marcas")  # Nueva opción
        
        if tiene_permiso("admin"):
            opciones_disponibles.append("👥 Gestión Usuarios")
        
        if tiene_permiso("admin"):
            opciones_disponibles.append("⚙️ Configuración")
        
        for opcion in opciones_disponibles:
            if st.button(opcion, use_container_width=True,
                        type="primary" if st.session_state.pagina_actual == opcion else "secondary"):
                st.session_state.pagina_actual = opcion
                st.rerun()
        
        st.markdown("---")
        
        stock_df = cargar_stock()
        conteos_df = cargar_conteos()
        
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.metric("📦 Productos", len(stock_df))
        with col_info2:
            st.metric("🔢 Conteos", len(conteos_df))
        
        st.markdown("---")
        
        if st.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# ======================================================
# 1️⃣ PÁGINA: DASHBOARD
# ======================================================
def mostrar_dashboard():
    """Mostrar dashboard principal"""
    st.title(f"🏠 Dashboard - Bienvenido {st.session_state.nombre}")
    st.markdown("---")
    
    stock_df = cargar_stock()
    conteos_df = cargar_conteos()
    escaneos_df = cargar_escaneos_detallados()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_productos = len(stock_df)
        st.metric("📦 Productos", total_productos)
    
    with col2:
        total_conteos = len(conteos_df)
        st.metric("🔢 Conteos", total_conteos)
    
    with col3:
        if not escaneos_df.empty:
            total_escaneos = len(escaneos_df)
            st.metric("📱 Escaneos totales", total_escaneos)
        else:
            st.metric("📱 Escaneos totales", 0)
    
    with col4:
        if not conteos_df.empty:
            exactos = len(conteos_df[conteos_df["diferencia"] == 0])
            porcentaje = (exactos / total_conteos) * 100 if total_conteos > 0 else 0
            st.metric("🎯 Precisión", f"{porcentaje:.1f}%")
        else:
            st.metric("🎯 Precisión", "0%")
    
    st.markdown("---")
    
    # ======================================================
    # NUEVA SECCIÓN: RESUMEN POR ESTADO (COMO EN LA IMAGEN)
    # ======================================================
    st.subheader("📊 Resumen de Conteos por Estado")
    
    # Calcular estadísticas de conteos
    if not conteos_df.empty and not stock_df.empty:
        # Obtener productos únicos que han sido contados
        productos_contados = conteos_df.groupby('codigo').agg({
            'conteo_fisico': 'max',
            'diferencia': 'first'
        }).reset_index()
        
        # Total productos en sistema
        total_productos_sistema = len(stock_df)
        
        # Productos contados (únicos)
        total_productos_contados = len(productos_contados)
        
        # No escaneados
        no_escaneados = total_productos_sistema - total_productos_contados
        
        # Stock total
        stock_total = stock_df['stock_sistema'].sum() if 'stock_sistema' in stock_df.columns else 0
        
        # Total contado
        total_contado = productos_contados['conteo_fisico'].sum() if 'conteo_fisico' in productos_contados.columns else 0
        
        # Diferencia neta
        diferencia_neta = productos_contados['diferencia'].sum() if 'diferencia' in productos_contados.columns else 0
        
        # Estado de productos
        exactos = len(productos_contados[productos_contados['diferencia'] == 0])
        diferencias_leves = len(productos_contados[(productos_contados['diferencia'].abs() > 0) & (productos_contados['diferencia'].abs() <= 5)])
        diferencias_criticas = len(productos_contados[productos_contados['diferencia'].abs() > 5])
        
        # Layout de dos columnas: izquierda (resumen numérico) y derecha (distribución por estado)
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            # Checkbox para filtrar
            st.checkbox("Mostrar solo productos NO escaneados", key="filtro_no_escaneados")
            
            # Métricas en formato de cuadrícula 2x2
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.metric("**Total Productos**", total_productos_sistema)
                st.metric("**Productos Contados**", total_productos_contados)
            
            with col_m2:
                st.metric("**No Escaneados**", no_escaneados)
                st.metric("**Stock Total**", stock_total)
            
            # Diferencia neta (centrada)
            st.metric("**Diferencia Neta**", f"{diferencia_neta:+,d}")
        
        with col_right:
            st.markdown("### Distribución por Estado")
            
            # Checkboxes para filtrar por estado
            col_cb1, col_cb2, col_cb3 = st.columns(3)
            with col_cb1:
                st.checkbox("✅ Exactos", value=True, key="filtro_exactos")
            with col_cb2:
                st.checkbox("🟡 Diferencias Leves", value=True, key="filtro_leves")
            with col_cb3:
                st.checkbox("🔴 Diferencias Críticas", value=True, key="filtro_criticas")
            
            # Contadores por estado
            col_est1, col_est2, col_est3 = st.columns(3)
            with col_est1:
                st.metric("✅ Exactos", exactos)
            with col_est2:
                st.metric("🟡 Leves", diferencias_leves)
            with col_est3:
                st.metric("🔴 Críticas", diferencias_criticas)
            
            # Barra de progreso visual
            st.markdown("**Estado General**")
            if total_productos_contados > 0:
                progress_data = {
                    "Exactos": exactos,
                    "Leves": diferencias_leves,
                    "Críticas": diferencias_criticas
                }
                # Crear barras de progreso horizontales
                for estado, valor in progress_data.items():
                    if valor > 0:
                        porcentaje = (valor / total_productos_contados) * 100
                        color = "green" if estado == "Exactos" else "orange" if estado == "Leves" else "red"
                        st.markdown(
                            f"<div style='display: flex; align-items: center; margin: 5px 0;'>"
                            f"<span style='width: 80px;'>{estado}:</span>"
                            f"<div style='flex-grow: 1; background-color: #f0f0f0; border-radius: 4px; margin-left: 10px;'>"
                            f"<div style='width: {porcentaje}%; background-color: {color}; height: 20px; border-radius: 4px; text-align: center; color: white; font-size: 12px; line-height: 20px;'>{valor}</div>"
                            f"</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
        
        st.markdown("---")
        
        # ======================================================
        # LISTADO DE PRODUCTOS (COMO EN LA IMAGEN)
        # ======================================================
        st.subheader("📋 Listado de Productos")
        
        # Combinar datos de stock con conteos
        productos_con_estado = stock_df.copy()
        productos_con_estado['conteo_fisico'] = 0
        productos_con_estado['diferencia'] = 0
        productos_con_estado['estado'] = 'NO ESCANEADO'
        
        # Actualizar con datos de conteos
        for _, row in productos_contados.iterrows():
            mask = productos_con_estado['codigo'] == row['codigo']
            if mask.any():
                productos_con_estado.loc[mask, 'conteo_fisico'] = row['conteo_fisico']
                productos_con_estado.loc[mask, 'diferencia'] = row['diferencia']
                if row['diferencia'] == 0:
                    productos_con_estado.loc[mask, 'estado'] = 'EXACTO'
                elif abs(row['diferencia']) <= 5:
                    productos_con_estado.loc[mask, 'estado'] = 'LEVE'
                else:
                    productos_con_estado.loc[mask, 'estado'] = 'CRÍTICO'
        
        # Aplicar filtros
        filtros_activos = []
        if st.session_state.get('filtro_no_escaneados', False):
            filtros_activos.append(productos_con_estado['estado'] == 'NO ESCANEADO')
        if st.session_state.get('filtro_exactos', True):
            filtros_activos.append(productos_con_estado['estado'] == 'EXACTO')
        if st.session_state.get('filtro_leves', True):
            filtros_activos.append(productos_con_estado['estado'] == 'LEVE')
        if st.session_state.get('filtro_criticas', True):
            filtros_activos.append(productos_con_estado['estado'] == 'CRÍTICO')
        
        if filtros_activos:
            mask_final = filtros_activos[0]
            for mask in filtros_activos[1:]:
                mask_final = mask_final | mask
            productos_filtrados = productos_con_estado[mask_final]
        else:
            productos_filtrados = productos_con_estado
        
        # Mostrar tabla
        st.dataframe(
            productos_filtrados[['codigo', 'producto', 'area', 'stock_sistema', 'conteo_fisico', 'diferencia', 'estado']],
            width='stretch',
            hide_index=True,
            column_config={
                'diferencia': st.column_config.NumberColumn(format="%+d")
            }
        )
        
        st.caption(f"Mostrando {len(productos_filtrados)} de {len(productos_con_estado)} productos")
        
    else:
        st.info("No hay datos de conteo disponibles")
    
    st.markdown("---")
    
    # Resto del código existente (últimos productos, conteos, etc.)
    col_left, col_center, col_right = st.columns(3)
    
    with col_left:
        st.subheader("📋 Últimos Productos")
        if not stock_df.empty:
            ultimos_productos = stock_df.tail(5)[["codigo", "producto", "marca", "area", "stock_sistema"]]
            st.dataframe(ultimos_productos, width='stretch', hide_index=True)
        else:
            st.info("No hay productos registrados")
    
    with col_center:
        st.subheader("📈 Últimos Conteos")
        if not conteos_df.empty:
            ultimos_conteos = conteos_df.tail(5)[["fecha", "producto", "diferencia"]].copy()
            ultimos_conteos["fecha"] = pd.to_datetime(ultimos_conteos["fecha"], errors='coerce').dt.strftime("%H:%M")
            st.dataframe(ultimos_conteos, width='stretch', hide_index=True)
        else:
            st.info("No hay conteos registrados")
    
    with col_right:
        st.subheader("📱 Últimos Escaneos")
        if not escaneos_df.empty:
            ultimos_escaneos = escaneos_df.tail(5)[["timestamp", "codigo", "cantidad_escaneada"]].copy()
            ultimos_escaneos["timestamp"] = pd.to_datetime(ultimos_escaneos["timestamp"], errors='coerce').dt.strftime("%H:%M:%S")
            st.dataframe(ultimos_escaneos, width='stretch', hide_index=True)
        else:
            st.info("No hay escaneos registrados")
    
    # ... resto del código existente ...
    
    # SECCIÓN ELIMINADA - El resumen por marcas ya no aparece aquí
    
    if tiene_permiso("inventario"):
        st.markdown("---")
        st.subheader(f"📊 Mis Estadísticas - {st.session_state.nombre}")
        
        mis_conteos = conteos_df[conteos_df["usuario"] == st.session_state.nombre]
        mis_escaneos = escaneos_df[escaneos_df["usuario"] == st.session_state.nombre] if not escaneos_df.empty else pd.DataFrame()
        
        if not mis_conteos.empty:
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            
            with col_stat1:
                st.metric("Mis conteos", len(mis_conteos))
            
            with col_stat2:
                mis_exactos = len(mis_conteos[mis_conteos["diferencia"] == 0])
                st.metric("Mis exactos", mis_exactos)
            
            with col_stat3:
                if len(mis_conteos) > 0:
                    mi_precision = (mis_exactos / len(mis_conteos)) * 100
                    st.metric("Mi precisión", f"{mi_precision:.1f}%")
            
            with col_stat4:
                if not mis_escaneos.empty:
                    st.metric("Mis escaneos", len(mis_escaneos))

# ======================================================
# 2️⃣ PÁGINA: CARGA DE STOCK (MODIFICADA PARA INCLUIR MARCA)
# ======================================================
def mostrar_carga_stock():
    """Mostrar página de carga de stock"""
    if not tiene_permiso("inventario"):
        st.error("⛔ No tienes permisos para acceder a esta sección")
        st.info("Solo usuarios con rol 'inventario' o 'admin' pueden acceder")
        return
    
    st.title("📥 Carga Manual de Stock")
    st.markdown("---")
    
    # Obtener marcas disponibles
    marcas = db.obtener_todas_marcas()
    
    # Opción para crear nueva marca
    with st.expander("➕ Agregar nueva marca", expanded=False):
        col1, col2 = st.columns([3, 1])
        with col1:
            nueva_marca = st.text_input("Nombre de la nueva marca", key="nueva_marca_input")
        with col2:
            if st.button("Crear Marca", use_container_width=True):
                if nueva_marca:
                    if db.crear_marca(nueva_marca):
                        st.success(f"Marca '{nueva_marca.upper()}' creada")
                        st.rerun()
                    else:
                        st.error("La marca ya existe")
                else:
                    st.warning("Ingrese un nombre")
    
    st.subheader("➕ Agregar/Editar Producto")
    
    with st.form("form_stock", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            codigo = st.text_input("Código del producto *", help="Escanea el código de barras o ingrésalo manualmente")
            producto = st.text_input("Nombre del producto *")
            marca = st.selectbox("Marca *", marcas, index=0)
        
        with col2:
            area = st.selectbox("Área *", ["Farmacia", "Cajas", "Pasillos", "Equipos médicos", "Bodega", "Otros"])
            stock = st.number_input("Stock en sistema *", min_value=0, step=1, value=0)
        
        guardar = st.form_submit_button("💾 Guardar Producto", use_container_width=True)
        
        if guardar:
            codigo_limpio = limpiar_codigo(codigo)
            if codigo_limpio and producto:
                # Guardar en base de datos
                db.guardar_producto(codigo_limpio, producto, marca, area, stock)
                st.success(f"✅ Producto guardado correctamente por {st.session_state.nombre}")
                st.rerun()
            else:
                st.error("❌ Código y nombre son obligatorios")
    
    st.markdown("---")
    
    st.subheader("📋 Stock Actual")
    
    stock_df = cargar_stock()
    
    if not stock_df.empty:
        col_filt1, col_filt2, col_filt3 = st.columns(3)
        
        with col_filt1:
            marca_filtro = st.selectbox("Filtrar por marca", ["Todas"] + marcas, key="filtro_marca_stock")
        
        with col_filt2:
            area_filtro = st.selectbox("Filtrar por área", ["Todas"] + sorted(stock_df["area"].unique().tolist()), key="filtro_area_stock")
        
        with col_filt3:
            buscar = st.text_input("Buscar por código o nombre", key="buscar_stock_input")
        
        df_filtrado = stock_df.copy()
        
        if marca_filtro != "Todas":
            df_filtrado = df_filtrado[df_filtrado["marca"] == marca_filtro]
        
        if area_filtro != "Todas":
            df_filtrado = df_filtrado[df_filtrado["area"] == area_filtro]
        
        if buscar:
            mask = df_filtrado["codigo"].astype(str).str.contains(buscar, case=False, na=False) | \
                   df_filtrado["producto"].astype(str).str.contains(buscar, case=False, na=False)
            df_filtrado = df_filtrado[mask]
        
        st.dataframe(df_filtrado, use_container_width=True)
        st.metric("Productos mostrados", len(df_filtrado))
    else:
        st.info("📭 No hay productos registrados")

# ======================================================
# 3️⃣ PÁGINA: IMPORTAR DESDE EXCEL (MODIFICADA)
# ======================================================
def mostrar_importar_excel():
    """Mostrar página de importación desde Excel - VERSIÓN OPTIMIZADA"""
    if not tiene_permiso("admin"):
        st.error("⛔ No tienes permisos para acceder a esta sección")
        st.info("Solo administradores pueden importar desde Excel")
        return
    
    st.title("📤 Importar Stock desde Excel")
    st.markdown("---")
    
    with st.expander("📋 Instrucciones de formato", expanded=True):
        st.info("""
        **El archivo Excel debe tener estas columnas:**
        
        1. **codigo** - Código único del producto
        2. **producto** - Nombre del producto
        3. **marca** - Marca del producto (opcional)
        4. **area** - Área de ubicación
        5. **stock_sistema** - Cantidad en sistema
        """)
        
        ejemplo = pd.DataFrame({
            "codigo": ["PROD001", "PROD002", "PROD003"],
            "producto": ["Paracetamol 500mg", "Jabón líquido", "Guantes latex"],
            "marca": ["GENVEN", "LETI", "OTROS"],
            "area": ["Farmacia", "Pasillos", "Equipos médicos"],
            "stock_sistema": [100, 50, 200]
        })
        
        st.dataframe(ejemplo, use_container_width=True)
    
    st.markdown("---")
    
    st.subheader("📁 Subir archivo Excel")
    
    archivo = st.file_uploader("Selecciona tu archivo Excel (.xlsx, .xls)", type=["xlsx", "xls"])
    
    if archivo is not None:
        try:
            with st.spinner("📊 Procesando archivo..."):
                # Leer solo las columnas necesarias para ser más rápido
                df_excel = pd.read_excel(archivo, dtype=str, usecols=lambda x: x.lower() in ['codigo', 'producto', 'marca', 'area', 'stock_sistema'])
            
            st.success(f"✅ Archivo cargado: {archivo.name}")
            
            with st.expander("👁️ Vista previa", expanded=True):
                st.dataframe(df_excel.head(10), use_container_width=True)
            
            # Verificar columnas requeridas
            columnas_requeridas = {"codigo", "producto", "area", "stock_sistema"}
            columnas_encontradas = set(df_excel.columns.str.lower() if hasattr(df_excel.columns, 'str') else set(df_excel.columns))
            
            # Normalizar nombres de columnas
            df_excel.columns = df_excel.columns.str.lower() if hasattr(df_excel.columns, 'str') else df_excel.columns
            
            if columnas_requeridas.issubset(columnas_encontradas):
                st.success("✅ Columnas verificadas correctamente")
                
                # Verificar si hay columna 'marca'
                if 'marca' not in df_excel.columns:
                    df_excel['marca'] = 'SIN MARCA'
                    st.info("ℹ️ No se encontró columna 'marca'. Se usará 'SIN MARCA' por defecto.")
                
                total_registros = len(df_excel)
                st.info(f"📊 Total de registros a importar: {total_registros}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🚀 Importar datos (Rápido)", type="primary", use_container_width=True):
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        try:
                            # Preparar datos
                            status_text.text("Preparando datos...")
                            
                            # Limpiar códigos y convertir stock
                            df_excel["codigo"] = df_excel["codigo"].apply(limpiar_codigo)
                            df_excel["stock_sistema"] = pd.to_numeric(df_excel["stock_sistema"], errors='coerce').fillna(0).astype(int)
                            
                            # Crear lista de productos para batch insert
                            productos_batch = []
                            marcas_unicas = set()
                            
                            for idx, row in df_excel.iterrows():
                                productos_batch.append({
                                    'codigo': row["codigo"],
                                    'producto': row["producto"],
                                    'marca': row["marca"],
                                    'area': row["area"],
                                    'stock_sistema': row["stock_sistema"]
                                })
                                marcas_unicas.add(row["marca"])
                                
                                # Actualizar progreso cada 100 registros
                                if idx % 100 == 0:
                                    progress = (idx + 1) / total_registros
                                    progress_bar.progress(progress)
                                    status_text.text(f"Procesando {idx + 1} de {total_registros}...")
                            
                            # Guardar en batch
                            status_text.text("Guardando en base de datos...")
                            db.guardar_productos_batch(productos_batch)
                            
                            # Crear marcas nuevas
                            status_text.text("Registrando marcas...")
                            for marca in marcas_unicas:
                                db.crear_marca(marca)
                            
                            progress_bar.progress(1.0)
                            status_text.text("¡Importación completada!")
                            
                            st.success(f"✅ {total_registros} productos importados correctamente")
                            st.balloons()
                            
                        except Exception as e:
                            st.error(f"❌ Error durante la importación: {str(e)}")
                
                with col2:
                    if st.button("📋 Ver muestra de datos", use_container_width=True):
                        st.dataframe(df_excel.head(20), use_container_width=True)
            else:
                st.error(f"❌ Faltan columnas requeridas. Necesitas: {columnas_requeridas}")
                st.write("Columnas encontradas:", list(columnas_encontradas))
                
        except Exception as e:
            st.error(f"❌ Error al leer el archivo: {str(e)}")

# ======================================================
# 4️⃣ PÁGINA: CONTEO FÍSICO (MODIFICADA PARA MARCAS)
# ======================================================
def mostrar_conteo_fisico():
    """Mostrar página de conteo físico"""
    if not tiene_permiso("inventario"):
        st.error("⛔ No tienes permisos para acceder a esta sección")
        st.info("Solo usuarios con rol 'inventario' o 'admin' pueden realizar conteos")
        return

    st.title("🔢 Conteo Físico")
    st.markdown("---")

    # Cargar datos
    stock_df = cargar_stock()
    usuario_actual = st.session_state.nombre
    hoy = datetime.now().strftime("%Y-%m-%d")
    
    # Selector de marca
    marcas = db.obtener_todas_marcas()
    marca_seleccionada = st.selectbox(
        "🏷️ Filtrar por marca",
        ["Todas"] + marcas,
        key="marca_conteo"
    )
    
    if marca_seleccionada != "Todas":
        stock_df = stock_df[stock_df["marca"] == marca_seleccionada]

    # --- FUNCIÓN PARA VER EL CSV ---
    def mostrar_contenido_csv():
        if os.path.exists(ARCHIVO_ESCANEOS):
            try:
                df = pd.read_csv(ARCHIVO_ESCANEOS)
                st.write(f"**Total de registros en CSV:** {len(df)}")
                st.dataframe(df.tail(10))
                return df
            except Exception as e:
                st.error(f"Error leyendo CSV: {e}")
        else:
            st.warning("⚠️ El archivo CSV NO EXISTE")
        return None

    # --- FUNCIÓN PARA CALCULAR TOTAL ---
    def total_escaneado_hoy(usuario, codigo):
        """Calcula el total escaneado hoy por un usuario para un código específico"""
        if not os.path.exists(ARCHIVO_ESCANEOS):
            return 0

        try:
            df = pd.read_csv(ARCHIVO_ESCANEOS)
            if df.empty or 'cantidad_escaneada' not in df.columns:
                return 0

            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df['fecha'] = df['timestamp'].dt.strftime('%Y-%m-%d')
            hoy = datetime.now().strftime('%Y-%m-%d')

            mask = (df['fecha'] == hoy) & (df['usuario'] == usuario) & (df['codigo'].astype(str) == str(codigo))
            df_filtrado = df[mask]

            if df_filtrado.empty:
                return 0

            total = pd.to_numeric(df_filtrado['cantidad_escaneada'], errors='coerce').fillna(0).sum()
            return int(total)
        except Exception as e:
            st.error(f"Error calculando total: {e}")
            return 0

    # --- Determinar producto actual ---
    if st.session_state.producto_actual_conteo:
        codigo_actual = st.session_state.producto_actual_conteo.get('codigo')
        producto_en_stock = stock_df[stock_df["codigo"].astype(str) == str(codigo_actual)]
        
        if not producto_en_stock.empty:
            prod = producto_en_stock.iloc[0]
            producto_info = {
                'codigo': prod["codigo"],
                'nombre': prod["producto"],
                'marca': prod.get("marca", "SIN MARCA"),
                'area': prod["area"],
                'stock_sistema': int(prod["stock_sistema"])
            }
            st.session_state.producto_actual_conteo = producto_info
        else:
            st.session_state.producto_actual_conteo = None

    # Si no hay producto en sesión, buscar el último escaneado
    if not st.session_state.producto_actual_conteo and os.path.exists(ARCHIVO_ESCANEOS):
        try:
            df_temp = pd.read_csv(ARCHIVO_ESCANEOS)
            if not df_temp.empty and 'timestamp' in df_temp.columns:
                df_temp['timestamp'] = pd.to_datetime(df_temp['timestamp'], errors='coerce')
                df_temp = df_temp[df_temp['usuario'] == usuario_actual]
                if not df_temp.empty:
                    ultimo = df_temp.sort_values('timestamp', ascending=False).iloc[0]
                    codigo_ultimo = str(ultimo['codigo']).strip() if 'codigo' in ultimo else None
                    
                    if codigo_ultimo:
                        producto_en_stock = stock_df[stock_df["codigo"].astype(str) == codigo_ultimo]
                        if not producto_en_stock.empty:
                            prod = producto_en_stock.iloc[0]
                            st.session_state.producto_actual_conteo = {
                                'codigo': prod["codigo"],
                                'nombre': prod["producto"],
                                'marca': prod.get("marca", "SIN MARCA"),
                                'area': prod["area"],
                                'stock_sistema': int(prod["stock_sistema"])
                            }
        except Exception as e:
            st.error(f"Error al buscar último escaneo: {e}")

    # Calcular total
    total_contado = 0
    if st.session_state.producto_actual_conteo:
        total_contado = total_escaneado_hoy(usuario_actual, st.session_state.producto_actual_conteo['codigo'])
        st.session_state.conteo_actual_session = total_contado

    # --- Panel de información ---
    if st.session_state.producto_actual_conteo:
        prod = st.session_state.producto_actual_conteo
        st.subheader("📊 Producto actual")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.info(f"**Producto:**\n{prod['nombre']}")
        with col2:
            st.info(f"**Código:**\n{prod['codigo']}")
        with col3:
            st.info(f"**Marca:**\n{prod['marca']}")
        with col4:
            st.info(f"**Área:**\n{prod['area']}")

        colm1, colm2, colm3, colm4 = st.columns(4)
        with colm1:
            st.metric("Stock sistema", prod['stock_sistema'])
        with colm2:
            st.metric("Contado hoy", total_contado)
        with colm3:
            diferencia = total_contado - prod['stock_sistema']
            st.metric("Diferencia", f"{diferencia:+d}", delta=diferencia)
        with colm4:
            # Total escaneos hoy del usuario
            total_hoy = 0
            if os.path.exists(ARCHIVO_ESCANEOS):
                try:
                    df_temp = pd.read_csv(ARCHIVO_ESCANEOS)
                    if not df_temp.empty and 'timestamp' in df_temp.columns:
                        df_temp['fecha'] = pd.to_datetime(df_temp['timestamp']).dt.strftime('%Y-%m-%d')
                        total_hoy = len(df_temp[(df_temp['fecha'] == hoy) & (df_temp['usuario'] == usuario_actual)])
                except:
                    pass
            st.metric("Mis escaneos hoy", total_hoy)

    # --- Formulario de escaneo ---
    st.markdown("---")
    st.subheader("📷 Escanear producto")

    with st.form("form_escaneo", clear_on_submit=True):
        codigo = st.text_input("Código del producto", placeholder="Escanee o ingrese el código")
        cantidad = st.number_input("Cantidad", min_value=1, value=1, step=1)

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            enviar = st.form_submit_button("✅ Registrar", type="primary", use_container_width=True)
        with col_btn2:
            enviar_1 = st.form_submit_button("⚡ +1", use_container_width=True)

    # Procesar escaneo
    if enviar or enviar_1:
        if enviar_1:
            cantidad = 1

        codigo_limpio = limpiar_codigo(codigo)

        if not codigo_limpio:
            st.error("❌ Ingrese un código")
        else:
            producto_encontrado = stock_df[stock_df["codigo"].astype(str) == str(codigo_limpio)]

            if producto_encontrado.empty:
                st.error(f"❌ Producto '{codigo_limpio}' no encontrado")
                # Opción para crear producto
                with st.expander("📝 Crear nuevo producto", expanded=True):
                    with st.form("nuevo_producto"):
                        nuevo_nombre = st.text_input("Nombre *")
                        nuevo_marca = st.selectbox("Marca", marcas)
                        nuevo_area = st.selectbox("Área", ["Farmacia", "Cajas", "Pasillos", "Equipos médicos", "Bodega", "Otros"])
                        nuevo_stock = st.number_input("Stock inicial", min_value=0, value=0, step=1)

                        if st.form_submit_button("💾 Guardar"):
                            if nuevo_nombre:
                                db.guardar_producto(codigo_limpio, nuevo_nombre, nuevo_marca, nuevo_area, nuevo_stock)
                                st.success(f"✅ Producto creado")
                                st.rerun()
            else:
                # Procesar escaneo
                prod = producto_encontrado.iloc[0]
                
                # Calcular total anterior
                total_anterior = total_escaneado_hoy(usuario_actual, codigo_limpio)
                nuevo_total = total_anterior + cantidad

                # --- GUARDAR ESCANEO ---
                timestamp_actual = datetime.now()
                
                # Crear DataFrame con TODAS las columnas necesarias
                nuevo_registro = pd.DataFrame([{
                    "timestamp": timestamp_actual,
                    "usuario": usuario_actual,
                    "codigo": codigo_limpio,
                    "producto": prod["producto"],
                    "marca": prod.get("marca", "SIN MARCA"),
                    "area": prod["area"],
                    "cantidad_escaneada": int(cantidad),
                    "total_acumulado": int(nuevo_total),
                    "stock_sistema": int(prod["stock_sistema"]),
                    "tipo_operacion": "ESCANEO"
                }])

                # Guardar en CSV
                if os.path.exists(ARCHIVO_ESCANEOS):
                    df_existente = pd.read_csv(ARCHIVO_ESCANEOS)
                    df_final = pd.concat([df_existente, nuevo_registro], ignore_index=True)
                else:
                    df_final = nuevo_registro

                df_final.to_csv(ARCHIVO_ESCANEOS, index=False)

                # Registrar en base de datos
                db.registrar_conteo(
                    usuario_actual,
                    codigo_limpio,
                    prod["producto"],
                    prod.get("marca", "SIN MARCA"),
                    prod["area"],
                    int(prod["stock_sistema"]),
                    nuevo_total
                )

                # Actualizar resumen de conteos
                actualizar_resumen_conteo(
                    usuario_actual, codigo_limpio, prod["producto"],
                    prod["area"], int(prod["stock_sistema"]), nuevo_total
                )

                # Actualizar sesión
                st.session_state.producto_actual_conteo = {
                    'codigo': codigo_limpio,
                    'nombre': prod["producto"],
                    'marca': prod.get("marca", "SIN MARCA"),
                    'area': prod["area"],
                    'stock_sistema': int(prod["stock_sistema"])
                }
                st.session_state.conteo_actual_session = nuevo_total
                st.session_state.total_escaneos_session += 1

                st.success(f"✅ +{cantidad} = {nuevo_total}")
                time.sleep(0.5)
                st.rerun()

    # --- Botones de acción con NUEVO BOTÓN DE LIMPIAR ---
    if st.session_state.producto_actual_conteo:
        st.markdown("---")
        col_acc1, col_acc2, col_acc3 = st.columns(3)  # Cambiamos a 3 columnas para el nuevo botón
        
        with col_acc1:
            if st.button("🔄 Cambiar producto", use_container_width=True):
                st.session_state.producto_actual_conteo = None
                st.session_state.conteo_actual_session = 0
                st.rerun()
        
        with col_acc2:
            if st.button("📋 Ver historial", use_container_width=True):
                if os.path.exists(ARCHIVO_ESCANEOS):
                    try:
                        df_temp = pd.read_csv(ARCHIVO_ESCANEOS)
                        if not df_temp.empty and 'timestamp' in df_temp.columns:
                            df_temp['timestamp'] = pd.to_datetime(df_temp['timestamp'])
                            historial = df_temp[
                                (df_temp['codigo'].astype(str) == str(st.session_state.producto_actual_conteo['codigo'])) &
                                (df_temp['usuario'] == usuario_actual)
                            ].tail(10)
                            if not historial.empty:
                                st.dataframe(historial[['timestamp', 'cantidad_escaneada', 'total_acumulado']])
                    except Exception as e:
                        st.error(f"Error al cargar historial: {e}")
        
        with col_acc3:
            # Botón de limpiar conteo actual
            if st.button("🧹 Limpiar conteo actual", type="primary", use_container_width=True):
                # Verificar si hay algo que limpiar
                if st.session_state.conteo_actual_session > 0:
                    st.session_state.mostrar_confirmacion_limpieza = True
                else:
                    st.info("El conteo ya está en 0")
        
        # Mostrar confirmación de limpieza si es necesario
        if st.session_state.get('mostrar_confirmacion_limpieza', False):
            st.warning(f"⚠️ Esto reiniciará el conteo de **{st.session_state.producto_actual_conteo['nombre']}** de {st.session_state.conteo_actual_session} a 0")
            
            col_conf1, col_conf2 = st.columns(2)
            with col_conf1:
                if st.button("✅ Sí, reiniciar", key="confirm_si_limpiar"):
                    # Eliminar escaneos del producto actual para hoy
                    if os.path.exists(ARCHIVO_ESCANEOS):
                        df_temp = pd.read_csv(ARCHIVO_ESCANEOS)
                        if not df_temp.empty:
                            # Filtrar para excluir los escaneos de hoy de este producto
                            hoy = datetime.now().strftime("%Y-%m-%d")
                            df_temp['fecha'] = pd.to_datetime(df_temp['timestamp']).dt.strftime('%Y-%m-%d')
                            mask = ~((df_temp['fecha'] == hoy) & 
                                    (df_temp['usuario'] == usuario_actual) & 
                                    (df_temp['codigo'].astype(str) == str(st.session_state.producto_actual_conteo['codigo'])))
                            df_temp_filtrado = df_temp[mask]
                            
                            # Eliminar columna fecha antes de guardar
                            if 'fecha' in df_temp_filtrado.columns:
                                df_temp_filtrado = df_temp_filtrado.drop('fecha', axis=1)
                            
                            df_temp_filtrado.to_csv(ARCHIVO_ESCANEOS, index=False)
                            
                            # Actualizar sesión
                            st.session_state.conteo_actual_session = 0
                            
                            # Actualizar resumen de conteos (eliminar registro)
                            conteos_df = cargar_conteos()
                            if not conteos_df.empty:
                                hoy = datetime.now().strftime("%Y-%m-%d")
                                mask_conteos = ~((conteos_df["usuario"] == usuario_actual) & 
                                               (conteos_df["codigo"] == str(st.session_state.producto_actual_conteo['codigo'])) & 
                                               (conteos_df["fecha"].str.startswith(hoy)))
                                conteos_df = conteos_df[mask_conteos]
                                guardar_conteos(conteos_df)
                            
                            st.session_state.mostrar_confirmacion_limpieza = False
                            st.success("✅ Conteo reiniciado exitosamente")
                            time.sleep(1)
                            st.rerun()
            
            with col_conf2:
                if st.button("❌ Cancelar", key="confirm_no_limpiar"):
                    st.session_state.mostrar_confirmacion_limpieza = False
                    st.rerun()

# ======================================================
# 5️⃣ PÁGINA: REPORTES POR MARCA (VERSIÓN CON TABLA EXACTA)
# ======================================================
def mostrar_reportes_marca():
    """Mostrar reportes detallados por marca - VERSIÓN CON TABLA EXACTA"""
    st.title("🏷️ Reporte por Marcas")
    st.markdown("---")
    
    try:
        # Cargar datos necesarios
        stock_df = cargar_stock()
        escaneos_df = cargar_escaneos_detallados()
        
        if stock_df.empty:
            st.warning("No hay productos en el sistema")
            return
        
        # Asegurar que los DataFrames tengan las columnas necesarias
        if 'marca' not in stock_df.columns:
            stock_df['marca'] = 'SIN MARCA'
        
        # CONVERTIR TODOS LOS CÓDIGOS A STRING
        stock_df['codigo'] = stock_df['codigo'].astype(str)
        if not escaneos_df.empty:
            escaneos_df['codigo'] = escaneos_df['codigo'].astype(str)
            if 'marca' not in escaneos_df.columns:
                escaneos_df['marca'] = 'SIN MARCA'
        
        # Obtener marcas únicas
        marcas = stock_df['marca'].unique().tolist()
        marcas = [m for m in marcas if pd.notna(m) and m != '']
        marcas.sort()
        
        if not marcas:
            st.warning("No hay marcas disponibles")
            return
        
        # Crear resumen por marca
        resumen_marcas = []
        
        for marca in marcas:
            productos_marca = stock_df[stock_df['marca'] == marca]
            
            if not escaneos_df.empty:
                escaneos_marca = escaneos_df[escaneos_df['marca'] == marca]
                productos_escaneados = escaneos_marca['codigo'].nunique()
                productos_no_escaneados = len(productos_marca) - productos_escaneados
                stock_total = productos_marca['stock_sistema'].sum()
                total_contado = escaneos_marca['cantidad_escaneada'].sum() if not escaneos_marca.empty else 0
                
                if not escaneos_marca.empty:
                    resumen_productos = escaneos_marca.groupby('codigo').agg({
                        'cantidad_escaneada': 'sum'
                    }).reset_index()
                    
                    stock_dict = dict(zip(productos_marca['codigo'], productos_marca['stock_sistema']))
                    resumen_productos['stock_sistema'] = resumen_productos['codigo'].map(stock_dict).fillna(0)
                    resumen_productos['diferencia'] = resumen_productos['cantidad_escaneada'] - resumen_productos['stock_sistema']
                    diferencia_neta = resumen_productos['diferencia'].sum()
                else:
                    diferencia_neta = 0
                
                porcentaje_avance = (productos_escaneados / len(productos_marca) * 100) if len(productos_marca) > 0 else 0
            else:
                productos_escaneados = 0
                productos_no_escaneados = len(productos_marca)
                stock_total = productos_marca['stock_sistema'].sum()
                total_contado = 0
                diferencia_neta = 0
                porcentaje_avance = 0
            
            resumen_marcas.append({
                'marca': marca,
                'total_productos': len(productos_marca),
                'productos_contados': productos_escaneados,
                'productos_no_escaneados': productos_no_escaneados,
                'porcentaje_avance': round(porcentaje_avance, 1),
                'stock_total_sistema': int(stock_total),
                'total_contado': int(total_contado),
                'diferencia_neta': int(diferencia_neta)
            })
        
        # Mostrar resumen general
        st.subheader("📊 Resumen General por Marcas")
        df_resumen = pd.DataFrame(resumen_marcas)
        df_display = df_resumen.copy()
        df_display['% Avance'] = df_display['porcentaje_avance'].apply(lambda x: f"{x}%")
        df_display['diferencia_neta'] = df_display['diferencia_neta'].apply(lambda x: f"{x:+,d}")
        
        st.dataframe(
            df_display[['marca', 'total_productos', 'productos_contados', 
                        'productos_no_escaneados', '% Avance', 'stock_total_sistema', 
                        'total_contado', 'diferencia_neta']],
            use_container_width=True,
            hide_index=True,
            column_config={
                'marca': 'Marca',
                'total_productos': 'Total Prod.',
                'productos_contados': 'Contados',
                'productos_no_escaneados': 'No Escaneados',
                '% Avance': 'Avance',
                'stock_total_sistema': 'Stock Sis.',
                'total_contado': 'Total Contado',
                'diferencia_neta': 'Dif. Neta'
            }
        )
        
        st.markdown("---")
        
        # Selector de marca para ver detalle
        if marcas:
            marca_seleccionada = st.selectbox("🔍 Seleccionar marca para ver detalle", marcas)
            
            if marca_seleccionada:
                st.subheader(f"📋 Detalle de productos - {marca_seleccionada}")
                
                # Checkbox para filtrar
                solo_no_escaneados = st.checkbox("Mostrar solo productos NO escaneados")
                
                # Obtener productos de la marca seleccionada
                productos_marca = stock_df[stock_df['marca'] == marca_seleccionada].copy()
                
                # Agregar información de conteo
                if not escaneos_df.empty:
                    escaneos_marca = escaneos_df[escaneos_df['marca'] == marca_seleccionada]
                    
                    if not escaneos_marca.empty:
                        escaneos_agrupados = escaneos_marca.groupby('codigo').agg({
                            'cantidad_escaneada': 'sum'
                        }).reset_index()
                        
                        conteo_dict = dict(zip(escaneos_agrupados['codigo'], escaneos_agrupados['cantidad_escaneada']))
                        productos_marca['conteo_fisico'] = productos_marca['codigo'].map(conteo_dict).fillna(0).astype(int)
                    else:
                        productos_marca['conteo_fisico'] = 0
                    
                    productos_marca['diferencia'] = productos_marca['conteo_fisico'] - productos_marca['stock_sistema']
                    productos_marca['estado'] = productos_marca['diferencia'].apply(
                        lambda x: '✅ Exacto' if x == 0 else ('⚠️ Sobrante' if x > 0 else '✅ Faltante')
                    )
                else:
                    productos_marca['conteo_fisico'] = 0
                    productos_marca['diferencia'] = 0
                    productos_marca['estado'] = 'NO ESCANEADO'
                
                # Aplicar filtro
                if solo_no_escaneados:
                    productos_marca = productos_marca[productos_marca['conteo_fisico'] == 0]
                
                if not productos_marca.empty:
                    # Calcular estadísticas
                    total_prod = len(productos_marca)
                    contados = len(productos_marca[productos_marca['conteo_fisico'] > 0])
                    no_escaneados = len(productos_marca[productos_marca['conteo_fisico'] == 0])
                    exactos = len(productos_marca[productos_marca['diferencia'] == 0])
                    sobrantes = len(productos_marca[productos_marca['diferencia'] > 0])
                    faltantes = len(productos_marca[productos_marca['diferencia'] < 0])
                    
                    # Mostrar métricas
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        st.metric("**Total Productos**", total_prod)
                    with col2:
                        st.metric("**Productos Contados**", contados)
                    with col3:
                        st.metric("**No Escaneados**", no_escaneados)
                    with col4:
                        st.metric("**Stock Total**", int(productos_marca['stock_sistema'].sum()))
                    with col5:
                        st.metric("**Diferencia Neta**", f"{int(productos_marca['diferencia'].sum()):+,d}")
                    
                    st.markdown("---")
                    
                    # Distribución por Estado
                    st.subheader("📊 Distribución por Estado")
                    col_est1, col_est2, col_est3 = st.columns(3)
                    with col_est1:
                        st.metric("✅ Exactos", exactos)
                    with col_est2:
                        st.metric("⚠️ Sobrantes", sobrantes)
                    with col_est3:
                        st.metric("✅ Faltantes", faltantes)
                    
                    st.markdown("---")
                    
                    # ======================================================
                    # TABLA DE PRODUCTOS CON EL FORMATO EXACTO DE LA IMAGEN
                    # ======================================================
                    st.subheader("📋 Listado de Productos")
                    
                    # Preparar DataFrame con las columnas exactas del image.png
                    df_tabla = productos_marca[[
                        'codigo', 'producto', 'marca', 'area', 
                        'stock_sistema', 'conteo_fisico', 'diferencia', 'estado'
                    ]].copy()
                    
                    # Renombrar columnas exactamente como en la imagen
                    df_tabla.columns = [
                        'Código', 'Producto', 'Marca', 'Área', 
                        'Stock Sis.', 'Conteo', 'Diferencia', 'Estado'
                    ]
                    
                    # Formatear la columna Diferencia para que muestre el signo
                    df_tabla['Diferencia'] = df_tabla['Diferencia'].apply(lambda x: f"{int(x):+d}")
                    
                    # Función para aplicar color al estado
                    def color_estado(val):
                        if 'Faltante' in val:
                            return 'color: red; font-weight: bold'
                        elif 'Sobrante' in val:
                            return 'color: orange; font-weight: bold'
                        elif 'Exacto' in val:
                            return 'color: green; font-weight: bold'
                        return ''
                    
                    # Aplicar estilo a la columna Estado
                    styled_df = df_tabla.style.applymap(color_estado, subset=['Estado'])
                    
                    # Mostrar la tabla
                    st.dataframe(
                        styled_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            'Código': st.column_config.TextColumn('Código', width='medium'),
                            'Producto': st.column_config.TextColumn('Producto', width='large'),
                            'Marca': st.column_config.TextColumn('Marca', width='medium'),
                            'Área': st.column_config.TextColumn('Área', width='medium'),
                            'Stock Sis.': st.column_config.NumberColumn('Stock Sis.', format="%d"),
                            'Conteo': st.column_config.NumberColumn('Conteo', format="%d"),
                            'Diferencia': st.column_config.TextColumn('Diferencia', width='small'),
                            'Estado': st.column_config.TextColumn('Estado', width='medium')
                        }
                    )
                    
                    # Mostrar total de productos
                    st.caption(f"📊 Mostrando {len(df_tabla)} productos")
                    
                    # Botón para exportar
                    if st.button("📥 Exportar detalle a CSV", use_container_width=True):
                        csv = productos_marca.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "⬇️ Descargar CSV",
                            data=csv,
                            file_name=f"detalle_{marca_seleccionada}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            mime="text/csv"
                        )
                else:
                    st.info(f"No hay productos para mostrar en la marca {marca_seleccionada}")
    
    except Exception as e:
        st.error(f"Error al cargar reportes por marca: {str(e)}")
        with st.expander("🔍 Detalles del error"):
            st.exception(e)

# ======================================================
# 6️⃣ PÁGINA: REPORTES GENERALES (ACTUALIZADA)
# ======================================================
def mostrar_reportes():
    """Mostrar página de reportes generales"""
    st.title("📊 Reportes de Conteo")
    st.markdown("---")
    
    # Pestañas para diferentes vistas
    tab1, tab2, tab3 = st.tabs(["📈 Resumen General", "🏷️ Por Marcas", "📋 Historial Completo"])
    
    with tab1:
        mostrar_resumen_general()
    
    with tab2:
        # Integrar el reporte por marcas
        mostrar_reportes_marca()
    
    with tab3:
        mostrar_historial_completo()

def mostrar_resumen_general():
    """Mostrar resumen general de conteos - CON MARCA INCLUIDA"""
    conteos_df = cargar_conteos()
    escaneos_df = cargar_escaneos_detallados()
    
    # ==============================================
    # SECCIÓN 1: TABLA DE PRODUCTOS (PRIMERO) - CON MARCA
    # ==============================================
    if not escaneos_df.empty:
        st.subheader("📋 Detalle de productos escaneados")
        
        # Asegurar que los códigos sean strings
        escaneos_df['codigo'] = escaneos_df['codigo'].astype(str)
        
        # Verificar si existe la columna 'marca' en escaneos_df
        if 'marca' not in escaneos_df.columns:
            escaneos_df['marca'] = 'SIN MARCA'
        
        # Crear resumen por producto (INCLUYENDO MARCA)
        resumen_precision = escaneos_df.groupby(['codigo', 'producto', 'marca', 'area']).agg({
            'cantidad_escaneada': 'sum'
        }).reset_index()
        
        resumen_precision.columns = ['codigo', 'producto', 'marca', 'area', 'conteo_fisico']
        
        # Cargar stock
        stock_df = cargar_stock()
        if not stock_df.empty:
            stock_df['codigo'] = stock_df['codigo'].astype(str)
            stock_df_subset = stock_df[['codigo', 'stock_sistema']].copy()
        else:
            stock_df_subset = pd.DataFrame(columns=['codigo', 'stock_sistema'])
        
        # Merge con stock
        if not stock_df_subset.empty:
            resumen_precision = resumen_precision.merge(
                stock_df_subset, 
                on='codigo', 
                how='left'
            )
        else:
            resumen_precision['stock_sistema'] = 0
        
        # Llenar valores nulos
        resumen_precision['stock_sistema'] = resumen_precision['stock_sistema'].fillna(0).astype(int)
        
        # Calcular diferencias
        resumen_precision['diferencia'] = resumen_precision['conteo_fisico'] - resumen_precision['stock_sistema']
        resumen_precision['estado'] = resumen_precision['diferencia'].apply(
            lambda x: '✅ Exacto' if x == 0 else ('⚠️ Sobrante' if x > 0 else '🔻 Faltante')
        )
        
        # Ordenar por diferencia absoluta (mayor primero)
        resumen_precision['abs_diferencia'] = resumen_precision['diferencia'].abs()
        resumen_precision = resumen_precision.sort_values('abs_diferencia', ascending=False).drop('abs_diferencia', axis=1)
        
        # Mostrar tabla de productos CON MARCA
        columnas_mostrar = ['codigo', 'producto', 'marca', 'area', 'stock_sistema', 'conteo_fisico', 'diferencia', 'estado']
        
        st.dataframe(
            resumen_precision[columnas_mostrar],
            use_container_width=True,
            hide_index=True,
            column_config={
                'codigo': 'Código',
                'producto': 'Producto',
                'marca': 'Marca',
                'area': 'Área',
                'stock_sistema': 'Stock Sis.',
                'conteo_fisico': 'Conteo',
                'diferencia': st.column_config.NumberColumn('Diferencia', format="%+d"),
                'estado': 'Estado'
            }
        )
        
        st.caption(f"📊 Mostrando {len(resumen_precision)} productos escaneados")
        
        # ==============================================
        # EXPANDER: VER SOLO PRODUCTOS CON DIFERENCIAS (CON MARCA)
        # ==============================================
        with st.expander("🔍 Ver solo productos con diferencias"):
            productos_con_diferencia = resumen_precision[resumen_precision['diferencia'] != 0].copy()
            if not productos_con_diferencia.empty:
                st.dataframe(
                    productos_con_diferencia[columnas_mostrar],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        'diferencia': st.column_config.NumberColumn(format="%+d")
                    }
                )
                st.caption(f"📊 Mostrando {len(productos_con_diferencia)} productos con diferencias")
            else:
                st.success("🎉 ¡Todos los productos tienen conteos exactos! No hay diferencias.")
        
        st.markdown("---")
    else:
        st.info("📭 No hay productos escaneados")
        st.markdown("---")
    
    # ==============================================
    # SECCIÓN 2: MÉTRICAS PRINCIPALES (sin cambios)
    # ==============================================
    st.subheader("📈 Métricas Principales")
    
    if escaneos_df.empty:
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.metric("📦 Productos contados", 0)
        with col_m2:
            st.metric("🔢 Total escaneos", 0)
        with col_m3:
            st.metric("📦 Unidades contadas", 0)
        with col_m4:
            st.metric("👥 Usuarios activos", 0)
    else:
        # Calcular métricas de escaneos
        total_escaneos = len(escaneos_df)
        productos_contados = escaneos_df['codigo'].nunique()
        total_unidades = escaneos_df['cantidad_escaneada'].sum()
        usuarios_activos = escaneos_df['usuario'].nunique()
        
        # Mostrar en 4 columnas
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        
        with col_m1:
            st.metric("📦 Productos contados", productos_contados, 
                     help="Número de productos diferentes que han sido escaneados")
        
        with col_m2:
            st.metric("🔢 Total escaneos", total_escaneos,
                     help="Número total de veces que se ha escaneado")
        
        with col_m3:
            st.metric("📦 Unidades contadas", total_unidades,
                     help="Suma total de todas las cantidades escaneadas")
        
        with col_m4:
            st.metric("👥 Usuarios activos", usuarios_activos,
                     help="Número de usuarios que han realizado escaneos")
    
    st.markdown("---")
    
    # ==============================================
    # SECCIÓN 3: ANÁLISIS DE PRECISIÓN (CON FILTRO POR MARCA)
    # ==============================================
    st.subheader("🎯 Análisis de Precisión")
    
    if not conteos_df.empty and not escaneos_df.empty and 'resumen_precision' in locals():
        # Agregar filtro por marca
        if 'marca' in resumen_precision.columns:
            marcas_disponibles = ['Todas'] + sorted(resumen_precision['marca'].unique().tolist())
            marca_filtro = st.selectbox("🏷️ Filtrar por marca", marcas_disponibles, key="filtro_marca_analisis")
            
            # Aplicar filtro
            if marca_filtro != 'Todas':
                resumen_filtrado = resumen_precision[resumen_precision['marca'] == marca_filtro]
            else:
                resumen_filtrado = resumen_precision
        else:
            resumen_filtrado = resumen_precision
            marca_filtro = 'Todas'
        
        total_productos = len(resumen_filtrado)
        exactos = len(resumen_filtrado[resumen_filtrado['diferencia'] == 0])
        sobrantes = len(resumen_filtrado[resumen_filtrado['diferencia'] > 0])
        faltantes = len(resumen_filtrado[resumen_filtrado['diferencia'] < 0])
        
        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        
        with col_p1:
            st.metric("✅ Conteos exactos", f"{exactos} de {total_productos}", 
                     f"{(exactos/total_productos*100):.1f}%" if total_productos > 0 else "0%")
        
        with col_p2:
            st.metric("⚠️ Sobrantes", sobrantes,
                     help="Productos con conteo físico MAYOR al stock del sistema")
        
        with col_p3:
            st.metric("🔻 Faltantes", faltantes,
                     help="Productos con conteo físico MENOR al stock del sistema")
        
        with col_p4:
            diferencia_neta = resumen_filtrado['diferencia'].sum()
            st.metric("📊 Diferencia neta", f"{diferencia_neta:+,d}",
                     help="Suma total de todas las diferencias (positivas y negativas)")
        
        # Resumen visual adicional
        with st.expander("📊 Ver resumen estadístico detallado"):
            col_res1, col_res2 = st.columns(2)
            
            with col_res1:
                st.write("**Distribución de productos:**")
                st.write(f"• Exactos: {exactos} ({(exactos/total_productos*100):.1f}%)")
                st.write(f"• Sobrantes: {sobrantes} ({(sobrantes/total_productos*100):.1f}%)")
                st.write(f"• Faltantes: {faltantes} ({(faltantes/total_productos*100):.1f}%)")
            
            with col_res2:
                st.write("**Magnitud de diferencias:**")
                if sobrantes > 0:
                    promedio_sobrante = resumen_filtrado[resumen_filtrado['diferencia'] > 0]['diferencia'].mean()
                    max_sobrante = resumen_filtrado[resumen_filtrado['diferencia'] > 0]['diferencia'].max()
                    st.write(f"• Promedio sobrante: +{promedio_sobrante:.1f}")
                    st.write(f"• Máximo sobrante: +{max_sobrante}")
                if faltantes > 0:
                    promedio_faltante = abs(resumen_filtrado[resumen_filtrado['diferencia'] < 0]['diferencia'].mean())
                    max_faltante = abs(resumen_filtrado[resumen_filtrado['diferencia'] < 0]['diferencia'].min())
                    st.write(f"• Promedio faltante: -{promedio_faltante:.1f}")
                    st.write(f"• Máximo faltante: -{max_faltante}")
    
    else:
        # Si no hay datos suficientes
        if escaneos_df.empty:
            st.info("📭 No hay escaneos registrados para analizar")
        elif 'resumen_precision' not in locals():
            st.info("📊 No hay suficientes datos para el análisis de precisión")
        else:
            # Mostrar métricas en cero
            col_p1, col_p2, col_p3, col_p4 = st.columns(4)
            with col_p1:
                st.metric("✅ Conteos exactos", "0 de 0", "0%")
            with col_p2:
                st.metric("⚠️ Sobrantes", 0)
            with col_p3:
                st.metric("🔻 Faltantes", 0)
            with col_p4:
                st.metric("📊 Diferencia neta", "+0")

def mostrar_historial_completo():
    """Mostrar historial completo de escaneos"""
    escaneos_df = cargar_escaneos_detallados()
    
    if not escaneos_df.empty:
        st.subheader("📋 Historial de Escaneos")
        
        # Filtros
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            fecha_inicio = st.date_input("Fecha inicio", datetime.now().date())
        with col_f2:
            fecha_fin = st.date_input("Fecha fin", datetime.now().date())
        with col_f3:
            if 'usuario' in escaneos_df.columns:
                usuarios = ["Todos"] + escaneos_df['usuario'].unique().tolist()
                usuario_filtro = st.selectbox("Usuario", usuarios)
        
        # Aplicar filtros
        df_filtrado = escaneos_df.copy()
        df_filtrado['fecha'] = pd.to_datetime(df_filtrado['timestamp']).dt.date
        
        mask_fecha = (df_filtrado['fecha'] >= fecha_inicio) & (df_filtrado['fecha'] <= fecha_fin)
        df_filtrado = df_filtrado[mask_fecha]
        
        if 'usuario_filtro' in locals() and usuario_filtro != "Todos":
            df_filtrado = df_filtrado[df_filtrado['usuario'] == usuario_filtro]
        
        st.dataframe(
            df_filtrado.sort_values('timestamp', ascending=False),
            use_container_width=True,
            hide_index=True
        )
        
        st.metric("Registros mostrados", len(df_filtrado))
        
        # Botón exportar
        if st.button("📥 Exportar historial filtrado", use_container_width=True):
            csv = df_filtrado.to_csv(index=False).encode('utf-8')
            st.download_button(
                "⬇️ Descargar CSV",
                data=csv,
                file_name=f"historial_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
    else:
        st.info("No hay historial de escaneos")

# ======================================================
# 7️⃣ PÁGINA: GESTIÓN DE USUARIOS (MODIFICADA CON EDICIÓN)
# ======================================================
def mostrar_gestion_usuarios():
    """Mostrar página de gestión de usuarios con opciones de edición"""
    if not tiene_permiso("admin"):
        st.error("⛔ No tienes permisos para acceder a esta sección")
        st.info("Solo administradores pueden gestionar usuarios")
        return
    
    st.title("👥 Gestión de Usuarios")
    st.markdown("---")
    
    usuarios_df = cargar_usuarios()
    
    # ======================================================
    # SECCIÓN: CREAR NUEVO USUARIO
    # ======================================================
    with st.expander("➕ Crear nuevo usuario", expanded=False):
        with st.form("form_nuevo_usuario_crear", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                nuevo_username = st.text_input("Nombre de usuario *")
                nuevo_nombre = st.text_input("Nombre completo *")
            
            with col2:
                nuevo_password = st.text_input("Contraseña *", type="password")
                nuevo_rol = st.selectbox("Rol *", ["admin", "inventario", "consulta"])
            
            if st.form_submit_button("👤 Crear Usuario", use_container_width=True):
                if nuevo_username and nuevo_nombre and nuevo_password:
                    exito, mensaje = crear_usuario(nuevo_username, nuevo_nombre, nuevo_password, nuevo_rol)
                    if exito:
                        st.success(mensaje)
                        st.rerun()
                    else:
                        st.error(mensaje)
                else:
                    st.error("❌ Todos los campos son obligatorios")
    
    st.markdown("---")
    
    # ======================================================
    # SECCIÓN: LISTA DE USUARIOS CON OPCIONES DE EDICIÓN
    # ======================================================
    st.subheader("📋 Usuarios del sistema")
    
    if not usuarios_df.empty:
        # Mostrar estadísticas
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        
        with col_stat1:
            total_usuarios = len(usuarios_df)
            st.metric("Total usuarios", total_usuarios)
        
        with col_stat2:
            activos = len(usuarios_df[usuarios_df["activo"] == "1"])
            st.metric("Usuarios activos", activos)
        
        with col_stat3:
            admins = len(usuarios_df[usuarios_df["rol"] == "admin"])
            st.metric("Administradores", admins)
        
        st.markdown("---")
        
        # Mostrar cada usuario con opciones de edición
        for idx, usuario in usuarios_df.iterrows():
            with st.expander(f"👤 {usuario['nombre']} (@{usuario['username']})", expanded=False):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.write(f"**Username:** {usuario['username']}")
                    st.write(f"**Nombre:** {usuario['nombre']}")
                
                with col2:
                    st.write(f"**Rol:** {usuario['rol']}")
                    st.write(f"**Estado:** {'✅ Activo' if usuario['activo'] == '1' else '❌ Inactivo'}")
                
                with col3:
                    # Botón para editar (abre formulario de edición)
                    if st.button("✏️ Editar", key=f"edit_{usuario['username']}", use_container_width=True):
                        st.session_state[f"editando_{usuario['username']}"] = True
                
                # Formulario de edición (se muestra si se hizo clic en Editar)
                if st.session_state.get(f"editando_{usuario['username']}", False):
                    st.markdown("---")
                    st.markdown("### 📝 Editar Usuario")
                    
                    with st.form(f"form_editar_{usuario['username']}"):
                        col_edit1, col_edit2 = st.columns(2)
                        
                        with col_edit1:
                            nuevo_nombre_edit = st.text_input("Nombre completo", value=usuario['nombre'])
                            nuevo_username_edit = st.text_input("Username", value=usuario['username'], disabled=True)  # No permitir cambiar username
                        
                        with col_edit2:
                            nuevo_rol_edit = st.selectbox("Rol", ["admin", "inventario", "consulta"], 
                                                         index=["admin", "inventario", "consulta"].index(usuario['rol']))
                            nuevo_estado_edit = st.selectbox("Estado", ["Activo", "Inactivo"],
                                                            index=0 if usuario['activo'] == '1' else 1)
                        
                        nueva_password_edit = st.text_input("Nueva contraseña (dejar en blanco para no cambiar)", type="password")
                        
                        col_btn1, col_btn2, col_btn3 = st.columns(3)
                        
                        with col_btn1:
                            if st.form_submit_button("💾 Guardar cambios", type="primary", use_container_width=True):
                                cambios_realizados = False
                                
                                # Actualizar datos
                                usuarios_df.loc[idx, 'nombre'] = nuevo_nombre_edit
                                usuarios_df.loc[idx, 'rol'] = nuevo_rol_edit
                                usuarios_df.loc[idx, 'activo'] = '1' if nuevo_estado_edit == "Activo" else '0'
                                
                                # Actualizar contraseña si se proporcionó una nueva
                                if nueva_password_edit:
                                    usuarios_df.loc[idx, 'password'] = hash_password(nueva_password_edit)
                                    cambios_realizados = True
                                
                                guardar_usuarios(usuarios_df)
                                st.session_state[f"editando_{usuario['username']}"] = False
                                st.success(f"✅ Usuario {usuario['username']} actualizado correctamente")
                                st.rerun()
                        
                        with col_btn2:
                            if st.form_submit_button("❌ Cancelar", use_container_width=True):
                                st.session_state[f"editando_{usuario['username']}"] = False
                                st.rerun()
                        
                        with col_btn3:
                            # Botón para eliminar usuario (solo si no es el último admin)
                            if usuario['rol'] == 'admin' and len(usuarios_df[usuarios_df['rol'] == 'admin']) == 1:
                                st.warning("⚠️ Último admin")
                            else:
                                if st.form_submit_button("🗑️ Eliminar", type="secondary", use_container_width=True):
                                    st.session_state[f"eliminar_{usuario['username']}"] = True
                    
                    # Confirmación de eliminación
                    if st.session_state.get(f"eliminar_{usuario['username']}", False):
                        st.warning(f"⚠️ ¿Estás seguro de eliminar al usuario **{usuario['nombre']}**?")
                        col_del1, col_del2 = st.columns(2)
                        
                        with col_del1:
                            if st.button("✅ Sí, eliminar", key=f"confirm_del_{usuario['username']}"):
                                # Eliminar usuario
                                usuarios_df = usuarios_df[usuarios_df['username'] != usuario['username']]
                                guardar_usuarios(usuarios_df)
                                st.session_state[f"eliminar_{usuario['username']}"] = False
                                st.success(f"✅ Usuario {usuario['username']} eliminado")
                                st.rerun()
                        
                        with col_del2:
                            if st.button("❌ No, cancelar", key=f"cancel_del_{usuario['username']}"):
                                st.session_state[f"eliminar_{usuario['username']}"] = False
                                st.rerun()
    else:
        st.info("No hay usuarios registrados")

# ======================================================
# FUNCIÓN ADICIONAL: CAMBIAR CONTRASEÑA (OPCIONAL)
# ======================================================
def mostrar_cambiar_password():
    """Función para que el usuario cambie su propia contraseña"""
    if not st.session_state.autenticado:
        return
    
    st.subheader("🔐 Cambiar mi contraseña")
    
    with st.form("form_cambiar_password"):
        password_actual = st.text_input("Contraseña actual", type="password")
        nueva_password = st.text_input("Nueva contraseña", type="password")
        confirmar_password = st.text_input("Confirmar nueva contraseña", type="password")
        
        if st.form_submit_button("🔄 Cambiar contraseña", use_container_width=True):
            if not password_actual or not nueva_password or not confirmar_password:
                st.error("❌ Todos los campos son obligatorios")
            elif nueva_password != confirmar_password:
                st.error("❌ Las contraseñas nuevas no coinciden")
            else:
                # Verificar contraseña actual
                usuarios_df = cargar_usuarios()
                usuario_actual = usuarios_df[usuarios_df['username'] == st.session_state.usuario].iloc[0]
                
                if usuario_actual['password'] == hash_password(password_actual):
                    # Actualizar contraseña
                    usuarios_df.loc[usuarios_df['username'] == st.session_state.usuario, 'password'] = hash_password(nueva_password)
                    guardar_usuarios(usuarios_df)
                    st.success("✅ Contraseña actualizada correctamente")
                    st.balloons()
                else:
                    st.error("❌ Contraseña actual incorrecta")

# Modificar la barra lateral para incluir cambio de contraseña
def mostrar_sidebar():
    """Mostrar barra lateral con navegación"""
    with st.sidebar:
        st.title(f"👤 {st.session_state.nombre}")
        st.write(f"**Rol:** {st.session_state.rol.upper()}")
        st.write(f"**Usuario:** {st.session_state.usuario}")
        
        # Botón para cambiar contraseña (siempre visible)
        if st.button("🔐 Cambiar contraseña", use_container_width=True, key="btn_cambiar_pass"):
            st.session_state.mostrar_cambiar_pass = True
        
        # Mostrar formulario de cambio de contraseña
        if st.session_state.get('mostrar_cambiar_pass', False):
            with st.container():
                st.markdown("---")
                with st.form("sidebar_cambiar_pass"):
                    pass_actual = st.text_input("Actual", type="password", key="side_pass_actual")
                    pass_nueva = st.text_input("Nueva", type="password", key="side_pass_nueva")
                    pass_confirm = st.text_input("Confirmar", type="password", key="side_pass_confirm")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("💾 Guardar", use_container_width=True):
                            if pass_actual and pass_nueva and pass_confirm:
                                if pass_nueva == pass_confirm:
                                    usuarios_df = cargar_usuarios()
                                    usuario_actual = usuarios_df[usuarios_df['username'] == st.session_state.usuario].iloc[0]
                                    
                                    if usuario_actual['password'] == hash_password(pass_actual):
                                        usuarios_df.loc[usuarios_df['username'] == st.session_state.usuario, 'password'] = hash_password(pass_nueva)
                                        guardar_usuarios(usuarios_df)
                                        st.success("✅ Contraseña actualizada")
                                        st.session_state.mostrar_cambiar_pass = False
                                        st.rerun()
                                    else:
                                        st.error("❌ Contraseña actual incorrecta")
                                else:
                                    st.error("❌ Las nuevas contraseñas no coinciden")
                            else:
                                st.error("❌ Complete todos los campos")
                    
                    with col2:
                        if st.form_submit_button("❌ Cancelar", use_container_width=True):
                            st.session_state.mostrar_cambiar_pass = False
                            st.rerun()
                st.markdown("---")
        
        st.markdown("---")
        
        st.subheader("📌 Navegación")
        
        opciones_disponibles = []
        opciones_disponibles.append("🏠 Dashboard")
        
        if tiene_permiso("inventario"):
            opciones_disponibles.append("📥 Carga Stock")
        
        if tiene_permiso("admin"):
            opciones_disponibles.append("📤 Importar Excel")
        
        if tiene_permiso("inventario"):
            opciones_disponibles.append("🔢 Conteo Físico")
        
        opciones_disponibles.append("📊 Reportes")
        opciones_disponibles.append("🏷️ Reporte por Marcas")
        
        if tiene_permiso("admin"):
            opciones_disponibles.append("👥 Gestión Usuarios")
        
        if tiene_permiso("admin"):
            opciones_disponibles.append("⚙️ Configuración")
        
        for opcion in opciones_disponibles:
            if st.button(opcion, use_container_width=True,
                        type="primary" if st.session_state.pagina_actual == opcion else "secondary"):
                st.session_state.pagina_actual = opcion
                st.rerun()
        
        st.markdown("---")
        
        stock_df = cargar_stock()
        conteos_df = cargar_conteos()
        
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.metric("📦 Productos", len(stock_df))
        with col_info2:
            st.metric("🔢 Conteos", len(conteos_df))
        
        st.markdown("---")
        
        if st.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# ======================================================
# 8️⃣ PÁGINA: CONFIGURACIÓN (ACTUALIZADA - SIN GESTIÓN DE MARCAS)
# ======================================================
def mostrar_configuracion():
    """Mostrar página de configuración"""
    if not tiene_permiso("admin"):
        st.error("⛔ No tienes permisos para acceder a esta sección")
        st.info("Solo administradores pueden acceder a la configuración")
        return
    
    st.title("⚙️ Configuración del Sistema")
    st.markdown("---")
    
    # Estadísticas del sistema
    st.subheader("📊 Estadísticas del Sistema")
    
    stock_df = cargar_stock()
    conteos_df = cargar_conteos()
    usuarios_df = cargar_usuarios()
    escaneos_df = cargar_escaneos_detallados()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Productos", len(stock_df))
    
    with col2:
        st.metric("Conteos", len(conteos_df))
    
    with col3:
        st.metric("Usuarios", len(usuarios_df))
        activos = len(usuarios_df[usuarios_df["activo"] == "1"])
        st.caption(f"Activos: {activos}")
    
    with col4:
        st.metric("Escaneos totales", len(escaneos_df) if not escaneos_df.empty else 0)
    
    st.markdown("---")
    
    st.subheader("💾 Backup del sistema")
    
    if st.button("📁 Crear backup completo", use_container_width=True):
        fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        stock_df.to_csv(f"backup_stock_{fecha}.csv", index=False)
        conteos_df.to_csv(f"backup_conteos_{fecha}.csv", index=False)
        usuarios_df.to_csv(f"backup_usuarios_{fecha}.csv", index=False)
        escaneos_df.to_csv(f"backup_escaneos_{fecha}.csv", index=False)
        
        st.success(f"✅ Backup creado: backup_{fecha}.csv")
        st.info("Se crearon 4 archivos de backup")
    
    st.markdown("---")
    
    # ======================================================
    # NUEVA SECCIÓN: LIMPIAR TODO EL CONTEO
    # ======================================================
    st.subheader("🧹 Limpiar todo el conteo")
    st.warning("⚠️ **Área de alto riesgo** - Estas acciones son irreversibles")
    
    with st.expander("🛑 Haga clic para ver opciones de limpieza total", expanded=False):
        st.markdown("""
        ### ⚠️ ADVERTENCIA
        - Esta acción eliminará **TODOS** los conteos y escaneos
        - Afectará a **TODOS** los usuarios
        - Los productos en stock **NO** se eliminarán
        - **No se puede deshacer**
        """)
        
        # Checkbox de confirmación
        confirmacion1 = st.checkbox("✅ Entiendo que esto eliminará TODOS los conteos y escaneos")
        
        if confirmacion1:
            st.markdown("---")
            st.markdown("### 🔴 Confirmación final")
            st.markdown("Para proceder, escriba **'ELIMINAR TODO'** en el campo de texto:")
            
            texto_confirmacion = st.text_input("Confirmación de seguridad", type="password")
            
            col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
            
            with col_btn1:
                if st.button("🧹 LIMPIAR TODO", type="primary", use_container_width=True, disabled=texto_confirmacion != "ELIMINAR TODO"):
                    if texto_confirmacion == "ELIMINAR TODO":
                        try:
                            # Crear backup automático antes de limpiar
                            fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
                            backup_dir = "backups_automaticos"
                            
                            # Crear directorio de backups si no existe
                            if not os.path.exists(backup_dir):
                                os.makedirs(backup_dir)
                            
                            # Guardar backups
                            if not stock_df.empty:
                                stock_df.to_csv(f"{backup_dir}/backup_stock_ANTES_LIMPIEZA_{fecha}.csv", index=False)
                            if not conteos_df.empty:
                                conteos_df.to_csv(f"{backup_dir}/backup_conteos_ANTES_LIMPIEZA_{fecha}.csv", index=False)
                            if not escaneos_df.empty:
                                escaneos_df.to_csv(f"{backup_dir}/backup_escaneos_ANTES_LIMPIEZA_{fecha}.csv", index=False)
                            
                            # LIMPIAR ARCHIVOS DE CONTEO
                            
                            # 1. Limpiar escaneos_detallados.csv
                            columnas_escaneos = ["timestamp", "usuario", "codigo", "producto", "area", "cantidad_escaneada", "total_acumulado", "stock_sistema", "tipo_operacion"]
                            df_vacio_escaneos = pd.DataFrame(columns=columnas_escaneos)
                            df_vacio_escaneos.to_csv(ARCHIVO_ESCANEOS, index=False)
                            
                            # 2. Limpiar conteos.csv
                            columnas_conteos = ["fecha", "usuario", "codigo", "producto", "area", "stock_sistema", "conteo_fisico", "diferencia"]
                            df_vacio_conteos = pd.DataFrame(columns=columnas_conteos)
                            df_vacio_conteos.to_csv(ARCHIVO_CONTEOS, index=False)
                            
                            # 3. Limpiar sesión del usuario actual
                            st.session_state.producto_actual_conteo = None
                            st.session_state.conteo_actual_session = 0
                            st.session_state.total_escaneos_session = 0
                            st.session_state.historial_escaneos = []
                            
                            # 4. Limpiar base de datos (si aplica)
                            try:
                                db.limpiar_todos_conteos()
                            except:
                                pass  # Si no existe la función, continuar
                            
                            st.success(f"✅ **¡TODOS LOS CONTEOS HAN SIDO ELIMINADOS!**")
                            st.info(f"📁 Se creó un backup automático en la carpeta '{backup_dir}' antes de la limpieza")
                            st.balloons()
                            
                            # Mostrar resumen de la limpieza
                            st.markdown("### 📊 Estado actual del sistema:")
                            col_res1, col_res2 = st.columns(2)
                            with col_res1:
                                st.metric("Productos en stock", len(stock_df))
                            with col_res2:
                                st.metric("Conteos actuales", 0)
                            
                            time.sleep(2)
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Error durante la limpieza: {str(e)}")
            
            with col_btn2:
                if st.button("❌ Cancelar", use_container_width=True):
                    st.rerun()

# ======================================================
# APLICACIÓN PRINCIPAL
# ======================================================
def main():
    """Función principal de la aplicación"""
    inicializar_sesion()
    
    if not st.session_state.autenticado:
        mostrar_login()
        return
    
    mostrar_sidebar()
    
    pagina = st.session_state.pagina_actual
    
    if pagina == "🏠 Dashboard":
        mostrar_dashboard()
    elif pagina == "📥 Carga Stock":
        mostrar_carga_stock()
    elif pagina == "📤 Importar Excel":
        mostrar_importar_excel()
    elif pagina == "🔢 Conteo Físico":
        mostrar_conteo_fisico()
    elif pagina == "📊 Reportes":
        mostrar_reportes()
    elif pagina == "🏷️ Reporte por Marcas":
        mostrar_reportes_marca()
    elif pagina == "👥 Gestión Usuarios":
        mostrar_gestion_usuarios()
    elif pagina == "⚙️ Configuración":
        mostrar_configuracion()
    
    st.markdown("---")
    st.caption(f"📦 Sistema de Conteo de Inventario con Marcas • {st.session_state.rol.upper()} • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ======================================================
# EJECUCIÓN
# ======================================================
if __name__ == "__main__":
    main()