import streamlit as st
import pandas as pd
import os
import hashlib
from datetime import datetime
import time
import io

# ======================================================
# CONFIGURACIÓN GENERAL
# ======================================================
st.set_page_config(
    page_title="Sistema de Conteo de Inventario",
    page_icon="📦",
    layout="centered",
    initial_sidebar_state="expanded"
)

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
    if 'modo_escaneo_continuo' not in st.session_state:
        st.session_state.modo_escaneo_continuo = False
    if 'habilitar_sonidos' not in st.session_state:
        st.session_state.habilitar_sonidos = False
    if 'producto_actual_conteo' not in st.session_state:
        st.session_state.producto_actual_conteo = None
    if 'conteo_actual_session' not in st.session_state:
        st.session_state.conteo_actual_session = 0
    if 'total_escaneos_session' not in st.session_state:
        st.session_state.total_escaneos_session = 0
    if 'historial_escaneos' not in st.session_state:
        st.session_state.historial_escaneos = []
    if 'codigo_input_value' not in st.session_state:  # NUEVO: Para manejar el input
        st.session_state.codigo_input_value = ""

def play_sound(sound_type="success"):
    """Función de sonido dummy"""
    pass

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
    
    nuevo_usuario = pd.DataFrame([[
        username, nombre, hash_password(password), rol, "1"
    ]], columns=usuarios_df.columns)
    
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
    if os.path.exists(ARCHIVO_STOCK):
        df = pd.read_csv(ARCHIVO_STOCK, dtype=str)
        df["codigo"] = df["codigo"].apply(limpiar_codigo)
        df["stock_sistema"] = df["stock_sistema"].astype(int)
        return df
    else:
        return pd.DataFrame(
            columns=["codigo", "producto", "area", "stock_sistema"]
        )

def guardar_stock(df):
    df.to_csv(ARCHIVO_STOCK, index=False)

def cargar_conteos():
    if os.path.exists(ARCHIVO_CONTEOS):
        df = pd.read_csv(ARCHIVO_CONTEOS)
        return df
    else:
        return pd.DataFrame(
            columns=[
                "fecha", "usuario", "codigo",
                "producto", "area",
                "stock_sistema", "conteo_fisico", "diferencia"
            ]
        )

def guardar_conteos(df):
    df.to_csv(ARCHIVO_CONTEOS, index=False)

def cargar_escaneos_detallados():
    if os.path.exists(ARCHIVO_ESCANEOS):
        try:
            df = pd.read_csv(ARCHIVO_ESCANEOS)
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            return df
        except:
            return pd.DataFrame(columns=[
                "timestamp", "usuario", "codigo", "producto", "area",
                "cantidad_escaneada", "total_acumulado", "stock_sistema", "tipo_operacion"
            ])
    else:
        return pd.DataFrame(columns=[
            "timestamp", "usuario", "codigo", "producto", "area",
            "cantidad_escaneada", "total_acumulado", "stock_sistema", "tipo_operacion"
        ])

def guardar_escaneo_detallado(escaneo_data):
    """Guardar UN escaneo individual PERMANENTEMENTE"""
    try:
        escaneos_df = cargar_escaneos_detallados()
        nuevo_escaneo = pd.DataFrame([escaneo_data])
        escaneos_df = pd.concat([escaneos_df, nuevo_escaneo], ignore_index=True)
        escaneos_df.to_csv(ARCHIVO_ESCANEOS, index=False)
        
        if 'historial_escaneos' not in st.session_state:
            st.session_state.historial_escaneos = []
        
        st.session_state.historial_escaneos.append(escaneo_data)
        
        return True, "Escaneo guardado permanentemente"
    except Exception as e:
        return False, f"Error al guardar escaneo: {str(e)}"

def actualizar_resumen_conteo(usuario, codigo, producto, area, stock_sistema, nuevo_total):
    """Actualizar el resumen diario de conteos"""
    try:
        conteos_df = cargar_conteos()
        hoy = datetime.now().strftime("%Y-%m-%d")
        
        mask = (
            (conteos_df["usuario"] == usuario) &
            (conteos_df["codigo"] == codigo) &
            (conteos_df["fecha"].str.startswith(hoy))
        )
        
        if mask.any() and not conteos_df[mask].empty:
            conteos_df.loc[mask, ["conteo_fisico", "diferencia"]] = [
                nuevo_total, nuevo_total - stock_sistema
            ]
        else:
            nuevo = pd.DataFrame([[
                f"{hoy} {datetime.now().strftime('%H:%M:%S')}",
                usuario,
                codigo,
                producto,
                area,
                stock_sistema,
                nuevo_total,
                nuevo_total - stock_sistema
            ]], columns=conteos_df.columns)
            
            conteos_df = pd.concat([conteos_df, nuevo], ignore_index=True)
        
        guardar_conteos(conteos_df)
        return True
    except Exception as e:
        print(f"Error actualizando resumen: {e}")
        return False

def eliminar_registro_conteo(index):
    """Eliminar un registro específico del archivo de conteos"""
    try:
        conteos_df = cargar_conteos()
        if not conteos_df.empty and 0 <= index < len(conteos_df):
            conteos_df = conteos_df.drop(index).reset_index(drop=True)
            guardar_conteos(conteos_df)
            return True, f"Registro {index + 1} eliminado correctamente"
        else:
            return False, "Índice no válido"
    except Exception as e:
        return False, f"Error al eliminar: {str(e)}"

def eliminar_todos_conteos():
    """Eliminar todos los registros de conteos"""
    try:
        df_vacio = pd.DataFrame(
            columns=[
                "fecha", "usuario", "codigo",
                "producto", "area",
                "stock_sistema", "conteo_fisico", "diferencia"
            ]
        )
        guardar_conteos(df_vacio)
        return True, "Todos los registros han sido eliminados"
    except Exception as e:
        return False, f"Error al eliminar todos: {str(e)}"

# ======================================================
# PÁGINA DE LOGIN
# ======================================================
def mostrar_login():
    """Mostrar página de login"""
    st.title("🔐 Sistema de Conteo de Inventario")
    st.markdown("---")
    
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            with st.form("login_form"):
                st.subheader("Inicio de Sesión")
                
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
            
            with st.expander("🧪 Credenciales de prueba", expanded=False):
                st.write("**Administrador:**")
                st.code("Usuario: admin / Contraseña: admin123")
                st.write("**Operador Inventario:**")
                st.code("Usuario: inventario / Contraseña: inventario123")
                st.write("**Usuario Consulta:**")
                st.code("Usuario: consulta / Contraseña: consulta123")
    
    st.markdown("---")
    st.caption("📦 Sistema de Conteo de Inventario • v1.0")

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
            st.metric("📦", len(stock_df))
        with col_info2:
            st.metric("🔢", len(conteos_df))
        
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
    
    col_left, col_center, col_right = st.columns(3)
    
    with col_left:
        st.subheader("📋 Últimos Productos")
        if not stock_df.empty:
            ultimos_productos = stock_df.tail(5)[["codigo", "producto", "area", "stock_sistema"]]
            st.dataframe(ultimos_productos, use_container_width=True, hide_index=True)
        else:
            st.info("No hay productos registrados")
    
    with col_center:
        st.subheader("📈 Últimos Conteos")
        if not conteos_df.empty:
            ultimos_conteos = conteos_df.tail(5)[["fecha", "producto", "diferencia"]].copy()
            ultimos_conteos["fecha"] = pd.to_datetime(ultimos_conteos["fecha"], errors='coerce').dt.strftime("%H:%M")
            st.dataframe(ultimos_conteos, use_container_width=True, hide_index=True)
        else:
            st.info("No hay conteos registrados")
    
    with col_right:
        st.subheader("📱 Últimos Escaneos")
        if not escaneos_df.empty:
            ultimos_escaneos = escaneos_df.tail(5)[["timestamp", "codigo", "cantidad_escaneada"]].copy()
            ultimos_escaneos["timestamp"] = pd.to_datetime(ultimos_escaneos["timestamp"], errors='coerce').dt.strftime("%H:%M:%S")
            st.dataframe(ultimos_escaneos, use_container_width=True, hide_index=True)
        else:
            st.info("No hay escaneos registrados")
    
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
# 2️⃣ PÁGINA: CARGA DE STOCK
# ======================================================
def mostrar_carga_stock():
    """Mostrar página de carga de stock"""
    if not tiene_permiso("inventario"):
        st.error("⛔ No tienes permisos para acceder a esta sección")
        st.info("Solo usuarios con rol 'inventario' o 'admin' pueden acceder")
        return
    
    st.title("📥 Carga Manual de Stock")
    st.markdown("---")
    
    stock_df = cargar_stock()
    
    st.subheader("➕ Agregar/Editar Producto")
    
    with st.form("form_stock", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            codigo = st.text_input("Código del producto *", help="Escanea el código de barras o ingrésalo manualmente")
            producto = st.text_input("Nombre del producto *")
        
        with col2:
            area = st.selectbox(
                "Área *",
                ["Farmacia", "Cajas", "Pasillos", "Equipos médicos", "Bodega", "Otros"]
            )
            stock = st.number_input("Stock en sistema *", min_value=0, step=1, value=0)
        
        guardar = st.form_submit_button("💾 Guardar Producto", use_container_width=True)
        
        if guardar:
            codigo_limpio = limpiar_codigo(codigo)
            if codigo_limpio and producto:
                existe = not stock_df.empty and codigo_limpio in stock_df["codigo"].values
                
                if existe:
                    stock_df.loc[stock_df["codigo"] == codigo_limpio, ["producto", "area", "stock_sistema"]] = [
                        producto, area, stock
                    ]
                    mensaje = "actualizado"
                else:
                    nuevo = pd.DataFrame(
                        [[codigo_limpio, producto, area, stock]],
                        columns=stock_df.columns
                    )
                    stock_df = pd.concat([stock_df, nuevo], ignore_index=True)
                    mensaje = "guardado"
                
                guardar_stock(stock_df)
                st.success(f"✅ Producto {mensaje} correctamente por {st.session_state.nombre}")
                st.rerun()
            else:
                st.error("❌ Código y nombre son obligatorios")
    
    st.markdown("---")
    
    st.subheader("📋 Stock Actual")
    
    if not stock_df.empty:
        col_filt1, col_filt2 = st.columns(2)
        
        with col_filt1:
            area_filtro = st.selectbox(
                "Filtrar por área",
                ["Todas"] + sorted(stock_df["area"].unique().tolist()),
                key="filtro_area"
            )
        
        with col_filt2:
            buscar = st.text_input("Buscar por código o nombre", key="buscar_stock")
        
        df_filtrado = stock_df.copy()
        
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
# 3️⃣ PÁGINA: IMPORTAR DESDE EXCEL
# ======================================================
def mostrar_importar_excel():
    """Mostrar página de importación desde Excel"""
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
        3. **area** - Área de ubicación
        4. **stock_sistema** - Cantidad en sistema
        """)
        
        ejemplo = pd.DataFrame({
            "codigo": ["PROD001", "PROD002", "PROD003"],
            "producto": ["Paracetamol 500mg", "Jabón líquido", "Guantes latex"],
            "area": ["Farmacia", "Pasillos", "Equipos médicos"],
            "stock_sistema": [100, 50, 200]
        })
        
        st.dataframe(ejemplo, use_container_width=True)
    
    st.markdown("---")
    
    st.subheader("📁 Subir archivo Excel")
    
    archivo = st.file_uploader(
        "Selecciona tu archivo Excel (.xlsx, .xls)",
        type=["xlsx", "xls"]
    )
    
    if archivo is not None:
        try:
            df_excel = pd.read_excel(archivo, dtype=str)
            
            st.success(f"✅ Archivo cargado: {archivo.name}")
            
            with st.expander("👁️ Vista previa", expanded=True):
                st.dataframe(df_excel.head(10), use_container_width=True)
            
            columnas_requeridas = {"codigo", "producto", "area", "stock_sistema"}
            columnas_encontradas = set(df_excel.columns)
            
            if columnas_requeridas.issubset(columnas_encontradas):
                st.success("✅ Columnas verificadas correctamente")
                
                if st.button("🚀 Importar datos", type="primary", use_container_width=True):
                    with st.spinner("Importando..."):
                        df_excel["codigo"] = df_excel["codigo"].apply(limpiar_codigo)
                        df_excel["stock_sistema"] = pd.to_numeric(
                            df_excel["stock_sistema"], errors='coerce'
                        ).fillna(0).astype(int)
                        
                        guardar_stock(df_excel)
                        
                        st.success(f"✅ {len(df_excel)} productos importados correctamente")
                        st.balloons()
            else:
                st.error("❌ Faltan columnas requeridas")
                
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# ======================================================
# 4️⃣ PÁGINA: CONTEO FÍSICO MEJORADO - GUARDA PERMANENTE
# ======================================================
def mostrar_conteo_fisico():
    """Mostrar página de conteo físico con guardado permanente"""
    if not tiene_permiso("inventario"):
        st.error("⛔ No tienes permisos para acceder a esta sección")
        st.info("Solo usuarios con rol 'inventario' o 'admin' pueden realizar conteos")
        return
    
    st.title("🔢 Conteo Físico Avanzado")
    st.markdown("---")
    
    # Cargar datos
    stock_df = cargar_stock()
    conteos_df = cargar_conteos()
    escaneos_df = cargar_escaneos_detallados()
    
    # Configuración del modo
    st.subheader("⚙️ Configuración de escaneo")
    
    col_config1, col_config2 = st.columns(2)
    
    with col_config1:
        modo_continuo = st.checkbox(
            "🔄 Modo escaneo continuo",
            value=st.session_state.modo_escaneo_continuo,
            help="Guarda automáticamente después de cada escaneo"
        )
        st.session_state.modo_escaneo_continuo = modo_continuo
    
    with col_config2:
        # Habilitar sonidos deshabilitado
        st.checkbox(
            "🔊 Sonidos de confirmación (requiere pygame)",
            value=False,
            disabled=True,
            help="Sonidos deshabilitados"
        )
    
    st.markdown("---")
    
    # Panel de control en tiempo real
    if st.session_state.producto_actual_conteo:
        producto_info = st.session_state.producto_actual_conteo
        
        st.subheader("📊 Conteo en tiempo real")
        
        col_rt1, col_rt2, col_rt3, col_rt4 = st.columns(4)
        
        with col_rt1:
            st.metric(
                "Producto actual",
                producto_info.get('nombre', 'N/A')[:20] + "..."
            )
        
        with col_rt2:
            st.metric("Stock sistema", producto_info.get('stock_sistema', 0))
        
        with col_rt3:
            st.metric("Contado en sesión", st.session_state.conteo_actual_session)
        
        with col_rt4:
            hoy = datetime.now().strftime("%Y-%m-%d")
            escaneos_hoy = escaneos_df[
                (escaneos_df["codigo"] == producto_info.get('codigo')) &
                (escaneos_df["usuario"] == st.session_state.nombre)
            ]
            if not escaneos_hoy.empty:
                escaneos_hoy['timestamp'] = pd.to_datetime(escaneos_hoy['timestamp'])
                escaneos_hoy = escaneos_hoy[escaneos_hoy['timestamp'].dt.strftime('%Y-%m-%d') == hoy]
                total_hoy = escaneos_hoy["cantidad_escaneada"].sum() if not escaneos_hoy.empty else 0
            else:
                total_hoy = 0
            st.metric("Total hoy", total_hoy)
        
        st.info(f"**Código:** {producto_info.get('codigo', 'N/A')} | **Área:** {producto_info.get('area', 'N/A')}")
    
    # Sección principal de escaneo
    st.subheader("📷 Escanear producto")
    
    # Input para código usando una variable de sesión separada
    codigo_input = st.text_input(
        "Código del producto",
        placeholder="Pase el código por el escáner o ingréselo manualmente",
        value=st.session_state.get('codigo_input_value', ''),
        help="Escanea el código de barras",
        key="codigo_input_widget"  # Key fijo para el widget
    )
    
    # Actualizar la variable de sesión cuando cambia el input
    if codigo_input != st.session_state.get('codigo_input_value', ''):
        st.session_state.codigo_input_value = codigo_input
    
    # Procesar código ingresado
    codigo = limpiar_codigo(codigo_input)
    
    # Función para procesar un escaneo PERMANENTE
    def procesar_escaneo_permanente(codigo_escaneado, cantidad=1):
        """Procesar y guardar PERMANENTEMENTE un escaneo individual"""
        codigo_limpio = limpiar_codigo(codigo_escaneado)
        if not codigo_limpio:
            return False, "Código vacío"
        
        # Buscar producto
        fila = stock_df[stock_df["codigo"].astype(str) == str(codigo_limpio)]
        
        if fila.empty:
            return False, "Producto no encontrado"
        
        producto = fila.iloc[0]["producto"]
        area = fila.iloc[0]["area"]
        stock_sistema = int(fila.iloc[0]["stock_sistema"])
        
        # Calcular total acumulado hasta ahora (hoy)
        hoy = datetime.now().strftime("%Y-%m-%d")
        escaneos_hoy = escaneos_df[
            (escaneos_df["codigo"] == codigo_limpio) &
            (escaneos_df["usuario"] == st.session_state.nombre)
        ]
        if not escaneos_hoy.empty:
            escaneos_hoy['timestamp'] = pd.to_datetime(escaneos_hoy['timestamp'])
            escaneos_hoy = escaneos_hoy[escaneos_hoy['timestamp'].dt.strftime('%Y-%m-%d') == hoy]
        
        # Calcular nuevo total acumulado
        total_anterior = escaneos_hoy["cantidad_escaneada"].sum() if not escaneos_hoy.empty else 0
        nuevo_total_acumulado = total_anterior + cantidad
        
        # Crear datos del escaneo para guardar PERMANENTEMENTE
        timestamp_actual = datetime.now()
        
        escaneo_data = {
            "timestamp": timestamp_actual,
            "usuario": st.session_state.nombre,
            "codigo": codigo_limpio,
            "producto": producto,
            "area": area,
            "cantidad_escaneada": cantidad,
            "total_acumulado": nuevo_total_acumulado,
            "stock_sistema": stock_sistema,
            "tipo_operacion": "ESCANEO"
        }
        
        # GUARDAR PERMANENTEMENTE el escaneo individual
        exito_guardado, mensaje_guardado = guardar_escaneo_detallado(escaneo_data)
        
        if not exito_guardado:
            return False, f"Error al guardar: {mensaje_guardado}"
        
        # Actualizar el resumen diario de conteos
        actualizar_resumen_conteo(
            st.session_state.nombre, 
            codigo_limpio, 
            producto, 
            area, 
            stock_sistema, 
            nuevo_total_acumulado
        )
        
        # Actualizar variables de sesión
        st.session_state.producto_actual_conteo = {
            'codigo': codigo_limpio,
            'nombre': producto,
            'area': area,
            'stock_sistema': stock_sistema
        }
        st.session_state.conteo_actual_session = nuevo_total_acumulado
        st.session_state.total_escaneos_session += 1
        
        # Limpiar el campo de entrada
        st.session_state.codigo_input_value = ""
        
        return True, f"✅ {producto[:20]}... +{cantidad} = {nuevo_total_acumulado}"
    
    # Procesar código si se ingresó (en modo continuo o al presionar Enter)
    if codigo and st.session_state.modo_escaneo_continuo:
        exito, mensaje = procesar_escaneo_permanente(codigo, cantidad=1)
        
        if exito:
            st.success(mensaje)
            # Usar un pequeño delay antes del rerun
            time.sleep(0.5)
            st.rerun()
        else:
            st.error(mensaje)
    
    # Controles para el producto actual
    if st.session_state.producto_actual_conteo:
        producto_info = st.session_state.producto_actual_conteo
        
        st.markdown("---")
        st.subheader("🎯 Controles rápidos")
        
        col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
        
        with col_btn1:
            if st.button("➕ Sumar 1", use_container_width=True, type="primary"):
                exito, mensaje = procesar_escaneo_permanente(producto_info['codigo'], cantidad=1)
                if exito:
                    st.success(mensaje)
                    st.rerun()
        
        with col_btn2:
            if st.button("➕ Sumar 5", use_container_width=True):
                exito, mensaje = procesar_escaneo_permanente(producto_info['codigo'], cantidad=5)
                if exito:
                    st.success(mensaje)
                    st.rerun()
        
        with col_btn3:
            if st.button("➕ Sumar 10", use_container_width=True):
                exito, mensaje = procesar_escaneo_permanente(producto_info['codigo'], cantidad=10)
                if exito:
                    st.success(mensaje)
                    st.rerun()
        
        with col_btn4:
            cantidad_personalizada = st.number_input(
                "Cantidad personalizada",
                min_value=1,
                value=1,
                step=1,
                key="cantidad_personalizada"
            )
            if st.button(f"➕ Sumar {cantidad_personalizada}", use_container_width=True):
                exito, mensaje = procesar_escaneo_permanente(producto_info['codigo'], cantidad=cantidad_personalizada)
                if exito:
                    st.success(mensaje)
                    st.rerun()
        
        # Botón para cambiar de producto
        st.markdown("---")
        if st.button("🔄 Cambiar producto", use_container_width=True):
            st.session_state.producto_actual_conteo = None
            st.session_state.conteo_actual_session = 0
            st.session_state.codigo_input_value = ""
            st.rerun()
    
    # Sección para búsqueda manual si no se encuentra producto
    elif codigo and codigo.strip() and not st.session_state.producto_actual_conteo:
        # Buscar producto
        fila = stock_df[stock_df["codigo"].astype(str) == str(codigo)]
        
        if fila.empty:
            st.error("❌ Producto no encontrado en el sistema")
            
            with st.expander("➕ Registrar como nuevo producto", expanded=True):
                with st.form("form_nuevo_producto_conteo"):
                    nuevo_producto = st.text_input("Nombre del producto *", key="nuevo_nombre")
                    nuevo_area = st.selectbox(
                        "Área *",
                        ["Farmacia", "Cajas", "Pasillos", "Equipos médicos", "Bodega", "Otros"],
                        key="nuevo_area"
                    )
                    nuevo_stock = st.number_input("Stock inicial *", min_value=0, value=0, step=1, key="nuevo_stock")
                    
                    if st.form_submit_button("📝 Registrar y comenzar conteo"):
                        nuevo = pd.DataFrame([[
                            codigo,
                            nuevo_producto,
                            nuevo_area,
                            nuevo_stock
                        ]], columns=["codigo", "producto", "area", "stock_sistema"])
                        
                        stock_df_actualizado = pd.concat([stock_df, nuevo], ignore_index=True)
                        guardar_stock(stock_df_actualizado)
                        
                        st.session_state.producto_actual_conteo = {
                            'codigo': codigo,
                            'nombre': nuevo_producto,
                            'area': nuevo_area,
                            'stock_sistema': nuevo_stock
                        }
                        st.session_state.conteo_actual_session = 0
                        st.session_state.codigo_input_value = ""
                        
                        st.success(f"✅ Producto '{nuevo_producto}' registrado")
                        st.rerun()
        else:
            producto = fila.iloc[0]["producto"]
            area = fila.iloc[0]["area"]
            stock_sistema = int(fila.iloc[0]["stock_sistema"])
            
            st.success(f"✅ Producto encontrado: **{producto}**")
            
            col_select1, col_select2 = st.columns(2)
            
            with col_select1:
                if st.button(f"🎯 Seleccionar para conteo", type="primary", use_container_width=True):
                    st.session_state.producto_actual_conteo = {
                        'codigo': codigo,
                        'nombre': producto,
                        'area': area,
                        'stock_sistema': stock_sistema
                    }
                    st.session_state.conteo_actual_session = 0
                    st.session_state.codigo_input_value = ""
                    st.rerun()
            
            with col_select2:
                if st.button("📋 Ver historial detallado", use_container_width=True):
                    historial = escaneos_df[
                        (escaneos_df["codigo"] == codigo) &
                        (escaneos_df["usuario"] == st.session_state.nombre)
                    ].tail(10)
                    
                    if not historial.empty:
                        historial_display = historial.copy()
                        historial_display["timestamp"] = pd.to_datetime(historial_display["timestamp"]).dt.strftime("%H:%M:%S")
                        st.dataframe(
                            historial_display[["timestamp", "cantidad_escaneada", "total_acumulado"]],
                            use_container_width=True,
                            hide_index=True
                        )
                        st.metric("Total escaneos producto", len(historial))
                    else:
                        st.info("No hay historial de escaneos para este producto")
    
    # Historial de escaneos en tiempo real
    st.markdown("---")
    st.subheader("📱 Escaneos en tiempo real")
    
    if hasattr(st.session_state, 'historial_escaneos') and st.session_state.historial_escaneos:
        ultimos_escaneos = st.session_state.historial_escaneos[-10:]
        if ultimos_escaneos:
            df_ultimos = pd.DataFrame(ultimos_escaneos)
            df_ultimos["timestamp"] = pd.to_datetime(df_ultimos["timestamp"]).dt.strftime("%H:%M:%S")
            
            col_esc1, col_esc2 = st.columns([3, 1])
            
            with col_esc1:
                st.dataframe(
                    df_ultimos[["timestamp", "codigo", "producto", "cantidad_escaneada", "total_acumulado"]],
                    use_container_width=True,
                    hide_index=True,
                    height=300
                )
            
            with col_esc2:
                st.metric("Escaneos sesión", len(st.session_state.historial_escaneos))
                total_cantidad = sum(e.get("cantidad_escaneada", 0) for e in st.session_state.historial_escaneos)
                st.metric("Total unidades", total_cantidad)
    
    # Estadísticas de esta sesión
    st.markdown("---")
    st.subheader("📊 Estadísticas de esta sesión")
    
    col_ses1, col_ses2, col_ses3, col_ses4 = st.columns(4)
    
    with col_ses1:
        st.metric("Escaneos hoy", st.session_state.total_escaneos_session)
    
    with col_ses2:
        hoy = datetime.now().strftime("%Y-%m-%d")
        mis_escaneos_hoy = escaneos_df[
            (escaneos_df["usuario"] == st.session_state.nombre)
        ]
        if not mis_escaneos_hoy.empty:
            mis_escaneos_hoy['timestamp'] = pd.to_datetime(mis_escaneos_hoy['timestamp'])
            mis_escaneos_hoy = mis_escaneos_hoy[mis_escaneos_hoy['timestamp'].dt.strftime('%Y-%m-%d') == hoy]
            st.metric("Productos hoy", mis_escaneos_hoy["codigo"].nunique() if not mis_escaneos_hoy.empty else 0)
        else:
            st.metric("Productos hoy", 0)
    
    with col_ses3:
        if not mis_escaneos_hoy.empty:
            total_unidades = mis_escaneos_hoy["cantidad_escaneada"].sum()
            st.metric("Unidades hoy", total_unidades)
        else:
            st.metric("Unidades hoy", 0)
    
    with col_ses4:
        mis_conteos_hoy = conteos_df[
            (conteos_df["usuario"] == st.session_state.nombre) &
            (conteos_df["fecha"].str.startswith(hoy))
        ]
        if mis_conteos_hoy.shape[0] > 0:
            exactos = len(mis_conteos_hoy[mis_conteos_hoy["diferencia"] == 0])
            st.metric("Precisión hoy", f"{(exactos/len(mis_conteos_hoy)*100):.1f}%" if len(mis_conteos_hoy) > 0 else "0%")
        else:
            st.metric("Precisión hoy", "0%")
    
    # Botón para exportar historial completo
    st.markdown("---")
    if st.button("💾 Exportar historial completo de hoy", use_container_width=True):
        hoy = datetime.now().strftime("%Y-%m-%d")
        mis_escaneos_hoy = escaneos_df[
            (escaneos_df["usuario"] == st.session_state.nombre)
        ]
        if not mis_escaneos_hoy.empty:
            mis_escaneos_hoy['timestamp'] = pd.to_datetime(mis_escaneos_hoy['timestamp'])
            mis_escaneos_hoy = mis_escaneos_hoy[mis_escaneos_hoy['timestamp'].dt.strftime('%Y-%m-%d') == hoy]
        
        if not mis_escaneos_hoy.empty:
            csv = mis_escaneos_hoy.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Descargar CSV completo",
                data=csv,
                file_name=f"historial_completo_{hoy}_{st.session_state.usuario}.csv",
                mime="text/csv"
            )
        else:
            st.warning("No hay escaneos para exportar hoy")
    
    # JavaScript para modo continuo
    if st.session_state.modo_escaneo_continuo:
        st.markdown("""
        <script>
        // Enfocar automáticamente el campo de entrada en modo continuo
        setTimeout(function() {
            const inputs = document.querySelectorAll('input[data-testid="stTextInput"]');
            if (inputs.length > 0) {
                inputs[0].focus();
            }
        }, 100);
        </script>
        """, unsafe_allow_html=True)

# ======================================================
# 5️⃣ PÁGINA: REPORTES MEJORADOS
# ======================================================
def mostrar_reportes():
    """Mostrar página de reportes con historial completo"""
    st.title("📊 Reportes de Conteo")
    st.markdown("---")
    
    conteos_df = cargar_conteos()
    escaneos_df = cargar_escaneos_detallados()
    
    tipo_reporte = st.radio(
        "Seleccionar tipo de reporte:",
        ["📈 Resumen de conteos", "📱 Historial detallado", "👤 Reporte por usuario"],
        horizontal=True
    )
    
    if tipo_reporte == "📈 Resumen de conteos":
        if conteos_df.empty:
            st.info("📭 No hay conteos registrados")
        else:
            st.subheader("📈 Estadísticas del reporte")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total registros", len(conteos_df))
            
            with col2:
                diferencias_criticas = len(conteos_df[abs(conteos_df["diferencia"]) > 2])
                st.metric("Diferencias críticas", diferencias_criticas)
            
            with col3:
                diferencias_leves = len(conteos_df[(abs(conteos_df["diferencia"]) <= 2) & 
                                                  (conteos_df["diferencia"] != 0)])
                st.metric("Diferencias leves", diferencias_leves)
            
            with col4:
                conteos_exactos = len(conteos_df[conteos_df["diferencia"] == 0])
                st.metric("Conteos exactos", conteos_exactos)
            
            st.markdown("---")
            
            st.subheader("📋 Detalle de conteos")
            
            conteos_df_display = conteos_df.copy()
            conteos_df_display.insert(0, '#', range(1, len(conteos_df_display) + 1))
            
            st.dataframe(conteos_df_display, use_container_width=True)
    
    elif tipo_reporte == "📱 Historial detallado":
        if escaneos_df.empty:
            st.info("📭 No hay escaneos registrados")
        else:
            st.subheader("📱 Historial completo de escaneos")
            
            col_filt1, col_filt2, col_filt3 = st.columns(3)
            
            with col_filt1:
                fecha_inicio = st.date_input("Fecha inicio", value=pd.to_datetime('today') - pd.Timedelta(days=7))
            
            with col_filt2:
                fecha_fin = st.date_input("Fecha fin", value=pd.to_datetime('today'))
            
            with col_filt3:
                usuario_filtro = st.selectbox(
                    "Usuario",
                    ["Todos"] + sorted(escaneos_df["usuario"].unique().tolist())
                )
            
            escaneos_filtrados = escaneos_df.copy()
            escaneos_filtrados['timestamp'] = pd.to_datetime(escaneos_filtrados['timestamp'])
            
            escaneos_filtrados = escaneos_filtrados[
                (escaneos_filtrados['timestamp'].dt.date >= fecha_inicio) &
                (escaneos_filtrados['timestamp'].dt.date <= fecha_fin)
            ]
            
            if usuario_filtro != "Todos":
                escaneos_filtrados = escaneos_filtrados[escaneos_filtrados["usuario"] == usuario_filtro]
            
            if escaneos_filtrados.empty:
                st.info("No hay escaneos en el período seleccionado")
            else:
                total_escaneos = len(escaneos_filtrados)
                total_unidades = escaneos_filtrados["cantidad_escaneada"].sum()
                productos_unicos = escaneos_filtrados["codigo"].nunique()
                
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                with col_stat1:
                    st.metric("Total escaneos", total_escaneos)
                with col_stat2:
                    st.metric("Total unidades", total_unidades)
                with col_stat3:
                    st.metric("Productos únicos", productos_unicos)
                
                escaneos_display = escaneos_filtrados.copy()
                escaneos_display["timestamp"] = escaneos_display["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
                
                st.dataframe(
                    escaneos_display[["timestamp", "usuario", "codigo", "producto", "cantidad_escaneada", "total_acumulado"]],
                    use_container_width=True,
                    height=400
                )
    
    elif tipo_reporte == "👤 Reporte por usuario":
        if escaneos_df.empty:
            st.info("📭 No hay escaneos registrados")
        else:
            st.subheader("👤 Estadísticas por usuario")
            
            stats_por_usuario = escaneos_df.groupby("usuario").agg(
                total_escaneos=('cantidad_escaneada', 'count'),
                total_unidades=('cantidad_escaneada', 'sum'),
                productos_unicos=('codigo', 'nunique'),
                primera_fecha=('timestamp', 'min'),
                ultima_fecha=('timestamp', 'max')
            ).reset_index()
            
            stats_por_usuario["primera_fecha"] = pd.to_datetime(stats_por_usuario["primera_fecha"]).dt.strftime("%Y-%m-%d")
            stats_por_usuario["ultima_fecha"] = pd.to_datetime(stats_por_usuario["ultima_fecha"]).dt.strftime("%Y-%m-%d")
            
            st.dataframe(stats_por_usuario, use_container_width=True)
    
    st.markdown("---")
    st.subheader("💾 Exportar datos")
    
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        if not conteos_df.empty:
            st.download_button(
                "⬇️ Descargar resumen CSV",
                data=conteos_df.to_csv(index=False).encode("utf-8"),
                file_name=f"resumen_conteos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
    
    with col_exp2:
        if not escaneos_df.empty:
            st.download_button(
                "⬇️ Descargar historial completo CSV",
                data=escaneos_df.to_csv(index=False).encode("utf-8"),
                file_name=f"historial_completo_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
    
    if tiene_permiso("inventario"):
        st.markdown("---")
        st.subheader("⚙️ Administración")
        
        with st.expander("🗑️ Eliminar registro de conteo", expanded=False):
            if not conteos_df.empty:
                registro_a_eliminar = st.number_input(
                    "Número de registro a eliminar",
                    min_value=1,
                    max_value=len(conteos_df),
                    step=1
                )
                
                if st.button("❌ Eliminar registro", type="secondary"):
                    registro_idx = registro_a_eliminar - 1
                    exito, mensaje = eliminar_registro_conteo(registro_idx)
                    if exito:
                        st.success(mensaje)
                        st.rerun()
                    else:
                        st.error(mensaje)
            else:
                st.info("No hay registros para eliminar")

# ======================================================
# 6️⃣ PÁGINA: GESTIÓN DE USUARIOS (SOLO ADMIN)
# ======================================================
def mostrar_gestion_usuarios():
    """Mostrar página de gestión de usuarios"""
    if not tiene_permiso("admin"):
        st.error("⛔ No tienes permisos para acceder a esta sección")
        st.info("Solo administradores pueden gestionar usuarios")
        return
    
    st.title("👥 Gestión de Usuarios")
    st.markdown("---")
    
    usuarios_df = cargar_usuarios()
    
    st.subheader("➕ Crear nuevo usuario")
    
    with st.form("form_nuevo_usuario", clear_on_submit=True):
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
    
    st.subheader("📋 Usuarios del sistema")
    
    if not usuarios_df.empty:
        usuarios_display = usuarios_df.copy()
        usuarios_display["password"] = "••••••••"
        
        st.dataframe(usuarios_display, use_container_width=True)
        
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
    else:
        st.info("No hay usuarios registrados")

# ======================================================
# 7️⃣ PÁGINA: CONFIGURACIÓN (SOLO ADMIN)
# ======================================================
def mostrar_configuracion():
    """Mostrar página de configuración"""
    if not tiene_permiso("admin"):
        st.error("⛔ No tienes permisos para acceder a esta sección")
        st.info("Solo administradores pueden acceder a la configuración")
        return
    
    st.title("⚙️ Configuración del Sistema")
    st.markdown("---")
    
    stock_df = cargar_stock()
    conteos_df = cargar_conteos()
    usuarios_df = cargar_usuarios()
    escaneos_df = cargar_escaneos_detallados()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Productos", len(stock_df))
        if not stock_df.empty:
            st.caption(f"Último: {stock_df.iloc[-1]['producto'][:20]}...")
    
    with col2:
        st.metric("Conteos", len(conteos_df))
        if not conteos_df.empty:
            fecha_ultimo = conteos_df.iloc[-1]['fecha'][:10]
            st.caption(f"Último: {fecha_ultimo}")
    
    with col3:
        st.metric("Usuarios", len(usuarios_df))
        activos = len(usuarios_df[usuarios_df["activo"] == "1"])
        st.caption(f"Activos: {activos}")
    
    with col4:
        st.metric("Escaneos totales", len(escaneos_df) if not escaneos_df.empty else 0)
        if not escaneos_df.empty:
            fecha_ultimo = pd.to_datetime(escaneos_df.iloc[-1]['timestamp']).strftime("%Y-%m-%d")
            st.caption(f"Último: {fecha_ultimo}")
    
    st.markdown("---")
    
    st.subheader("🛠️ Mantenimiento")
    
    col_mant1, col_mant2 = st.columns(2)
    
    with col_mant1:
        if st.button("🔄 Recalcular estadísticas", use_container_width=True):
            st.info("Función en desarrollo")
    
    with col_mant2:
        if st.button("🧹 Limpiar caché", use_container_width=True):
            st.info("Función en desarrollo")
    
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
    elif pagina == "👥 Gestión Usuarios":
        mostrar_gestion_usuarios()
    elif pagina == "⚙️ Configuración":
        mostrar_configuracion()
    
    st.markdown("---")
    st.caption(f"📦 Sistema de Conteo de Inventario • {st.session_state.rol.upper()} • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ======================================================
# EJECUCIÓN
# ======================================================
if __name__ == "__main__":
    main()