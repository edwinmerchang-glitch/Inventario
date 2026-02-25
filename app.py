import streamlit as st
import pandas as pd
import os
import hashlib
from datetime import datetime
import time
import tempfile
import database as db

# ======================================================
# DETECCIÓN DE ENTORNO AZURE
# ======================================================
EN_AZURE = os.environ.get('WEBSITE_SITE_NAME') is not None

if EN_AZURE:
    # En Azure, usar /tmp para archivos temporales
    BASE_PATH = tempfile.gettempdir()
else:
    # Localmente, usar el directorio actual
    BASE_PATH = "."

# ======================================================
# CONFIGURACIÓN GENERAL
# ======================================================
st.set_page_config(
    page_title="Sistema de Conteo de Inventario",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ARCHIVOS (USANDO RUTA CORRECTA SEGÚN ENTORNO)
ARCHIVO_STOCK = os.path.join(BASE_PATH, "stock_sistema.csv")
ARCHIVO_CONTEOS = os.path.join(BASE_PATH, "conteos.csv")
ARCHIVO_USUARIOS = os.path.join(BASE_PATH, "usuarios.csv")
ARCHIVO_ESCANEOS = os.path.join(BASE_PATH, "escaneos_detallados.csv")

# ======================================================
# INICIALIZAR BASE DE DATOS (SUPABASE)
# ======================================================
db.init_supabase()

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
    """Cargar usuarios desde CSV local (backup)"""
    if os.path.exists(ARCHIVO_USUARIOS):
        df = pd.read_csv(ARCHIVO_USUARIOS, dtype=str)
        return df
    else:
        # Crear usuarios por defecto
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
    """Cargar stock desde Supabase"""
    try:
        df = db.obtener_todos_productos(st.session_state.get('marca_seleccionada', 'Todas'))
        
        if 'marca' not in df.columns:
            df['marca'] = 'SIN MARCA'
        
        return df
    except Exception as e:
        st.error(f"Error cargando stock: {e}")
        return pd.DataFrame(columns=["codigo", "producto", "marca", "area", "stock_sistema"])

def cargar_conteos():
    """Cargar conteos desde Supabase"""
    try:
        df = db.obtener_todos_conteos()
        return df
    except Exception as e:
        print(f"Error cargando conteos: {e}")
        # Fallback a CSV
        if os.path.exists(ARCHIVO_CONTEOS):
            return pd.read_csv(ARCHIVO_CONTEOS)
        return pd.DataFrame(columns=["fecha", "usuario", "codigo", "producto", "marca", "area", "stock_sistema", "conteo_fisico", "diferencia"])

def cargar_escaneos_detallados():
    """Cargar escaneos desde Supabase"""
    try:
        df = db.obtener_todos_escaneos()
        return df
    except Exception as e:
        print(f"Error cargando escaneos: {e}")
        # Fallback a CSV
        if os.path.exists(ARCHIVO_ESCANEOS):
            return pd.read_csv(ARCHIVO_ESCANEOS)
        return pd.DataFrame(columns=["timestamp", "usuario", "codigo", "producto", "marca", "area", "cantidad_escaneada", "total_acumulado", "stock_sistema", "tipo_operacion"])

def guardar_escaneo_detallado(escaneo_data):
    """Guardar escaneo en Supabase y CSV local"""
    try:
        # Guardar en Supabase
        exito = db.guardar_escaneo(escaneo_data)
        
        if not exito:
            # Fallback: guardar en CSV
            columnas_ordenadas = ['timestamp', 'usuario', 'codigo', 'producto', 'marca', 'area', 
                                 'cantidad_escaneada', 'total_acumulado', 'stock_sistema', 'tipo_operacion']
            
            nuevo_registro = pd.DataFrame([{col: escaneo_data.get(col, None) for col in columnas_ordenadas}])
            
            if os.path.exists(ARCHIVO_ESCANEOS):
                df_existente = pd.read_csv(ARCHIVO_ESCANEOS)
                df_final = pd.concat([df_existente, nuevo_registro], ignore_index=True)
            else:
                df_final = nuevo_registro
            
            df_final.to_csv(ARCHIVO_ESCANEOS, index=False)
        
        # Actualizar sesión
        if 'historial_escaneos' not in st.session_state:
            st.session_state.historial_escaneos = []
        st.session_state.historial_escaneos.append(escaneo_data)
        
        return True, "Escaneo guardado"
    except Exception as e:
        return False, f"Error: {str(e)}"

def actualizar_resumen_conteo(usuario, codigo, producto, area, stock_sistema, nuevo_total, marca='SIN MARCA'):
    """Actualizar resumen de conteo en Supabase"""
    try:
        exito = db.registrar_conteo(
            usuario, codigo, producto, marca, area, stock_sistema, nuevo_total
        )
        
        if not exito:
            # Fallback a CSV
            conteos_df = cargar_conteos()
            hoy = datetime.now().strftime("%Y-%m-%d")
            
            nuevo = pd.DataFrame([[
                f"{hoy} {datetime.now().strftime('%H:%M:%S')}", 
                usuario, codigo, producto, marca, area, stock_sistema, nuevo_total, nuevo_total - stock_sistema
            ]], columns=["fecha", "usuario", "codigo", "producto", "marca", "area", "stock_sistema", "conteo_fisico", "diferencia"])
            
            conteos_df = pd.concat([conteos_df, nuevo], ignore_index=True)
            conteos_df.to_csv(ARCHIVO_CONTEOS, index=False)
        
        return True
    except Exception as e:
        print(f"Error actualizando resumen: {e}")
        return False

# ======================================================
# PÁGINA DE LOGIN
# ======================================================
def mostrar_login():
    """Mostrar página de login"""
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
    st.markdown("<p style='text-align: center; color: gray;'>📦 Sistema de Conteo de Inventario • v2.0 Azure</p>", unsafe_allow_html=True)

# ======================================================
# BARRA LATERAL
# ======================================================
def mostrar_sidebar():
    """Mostrar barra lateral con navegación"""
    with st.sidebar:
        st.title(f"👤 {st.session_state.nombre}")
        st.write(f"**Rol:** {st.session_state.rol.upper()}")
        st.write(f"**Usuario:** {st.session_state.usuario}")
        
        if EN_AZURE:
            st.info("☁️ Ejecutándose en Azure")
        
        st.markdown("---")
        
        st.subheader("📌 Navegación")
        
        opciones_disponibles = ["🏠 Dashboard"]
        
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
# FUNCIÓN PRINCIPAL DE CONTEO FÍSICO
# ======================================================
def mostrar_conteo_fisico():
    """Mostrar página de conteo físico"""
    if not tiene_permiso("inventario"):
        st.error("⛔ No tienes permisos para acceder a esta sección")
        return

    st.title("🔢 Conteo Físico")
    st.markdown("---")

    stock_df = cargar_stock()
    usuario_actual = st.session_state.nombre
    hoy = datetime.now().strftime("%Y-%m-%d")
    
    marcas = db.obtener_todas_marcas()
    marca_seleccionada = st.selectbox(
        "🏷️ Filtrar por marca",
        ["Todas"] + marcas,
        key="marca_conteo"
    )
    
    if marca_seleccionada != "Todas":
        stock_df = stock_df[stock_df["marca"] == marca_seleccionada]

    def total_escaneado_hoy(usuario, codigo):
        """Calcula el total escaneado hoy"""
        try:
            return db.obtener_total_escaneado_hoy(usuario, codigo)
        except:
            return 0

    # Determinar producto actual
    if st.session_state.producto_actual_conteo:
        codigo_actual = st.session_state.producto_actual_conteo.get('codigo')
        producto_en_stock = stock_df[stock_df["codigo"].astype(str) == str(codigo_actual)]
        
        if not producto_en_stock.empty:
            prod = producto_en_stock.iloc[0]
            st.session_state.producto_actual_conteo = {
                'codigo': prod["codigo"],
                'nombre': prod["producto"],
                'marca': prod.get("marca", "SIN MARCA"),
                'area': prod["area"],
                'stock_sistema': int(prod["stock_sistema"])
            }

    # Calcular total
    total_contado = 0
    if st.session_state.producto_actual_conteo:
        total_contado = total_escaneado_hoy(usuario_actual, st.session_state.producto_actual_conteo['codigo'])
        st.session_state.conteo_actual_session = total_contado

    # Panel de información
    if st.session_state.producto_actual_conteo:
        prod = st.session_state.producto_actual_conteo
        
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
            st.metric("Diferencia", f"{diferencia:+d}")
        with colm4:
            total_hoy = db.obtener_total_escaneos_usuario_hoy(usuario_actual)
            st.metric("Mis escaneos hoy", total_hoy)

    # Formulario de escaneo
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
                prod = producto_encontrado.iloc[0]
                total_anterior = total_escaneado_hoy(usuario_actual, codigo_limpio)
                nuevo_total = total_anterior + cantidad

                # Guardar escaneo
                timestamp_actual = datetime.now()
                
                escaneo_data = {
                    "timestamp": timestamp_actual.isoformat(),
                    "usuario": usuario_actual,
                    "codigo": codigo_limpio,
                    "producto": prod["producto"],
                    "marca": prod.get("marca", "SIN MARCA"),
                    "area": prod["area"],
                    "cantidad_escaneada": int(cantidad),
                    "total_acumulado": int(nuevo_total),
                    "stock_sistema": int(prod["stock_sistema"]),
                    "tipo_operacion": "ESCANEO"
                }

                guardar_escaneo_detallado(escaneo_data)

                # Actualizar sesión
                st.session_state.producto_actual_conteo = {
                    'codigo': codigo_limpio,
                    'nombre': prod["producto"],
                    'marca': prod.get("marca", "SIN MARCA"),
                    'area': prod["area"],
                    'stock_sistema': int(prod["stock_sistema"])
                }
                st.session_state.conteo_actual_session = nuevo_total

                st.success(f"✅ +{cantidad} = {nuevo_total}")
                time.sleep(0.5)
                st.rerun()

# ======================================================
# FUNCIONES SIMPLIFICADAS DE LAS DEMÁS PÁGINAS
# ======================================================
def mostrar_dashboard():
    """Dashboard simplificado"""
    st.title(f"🏠 Dashboard - Bienvenido {st.session_state.nombre}")
    st.markdown("---")
    
    stock_df = cargar_stock()
    conteos_df = cargar_conteos()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📦 Productos", len(stock_df))
    with col2:
        st.metric("🔢 Conteos", len(conteos_df))
    with col3:
        st.metric("📱 Escaneos", len(cargar_escaneos_detallados()))
    with col4:
        if not conteos_df.empty and 'diferencia' in conteos_df.columns:
            exactos = len(conteos_df[conteos_df['diferencia'] == 0])
            precision = (exactos / len(conteos_df)) * 100 if len(conteos_df) > 0 else 0
            st.metric("🎯 Precisión", f"{precision:.1f}%")
        else:
            st.metric("🎯 Precisión", "0%")
    
    st.markdown("---")
    st.info("☁️ Sistema funcionando en Azure con Supabase")

def mostrar_carga_stock():
    """Carga de stock simplificada"""
    if not tiene_permiso("inventario"):
        st.error("⛔ No tienes permisos")
        return
    
    st.title("📥 Carga Manual de Stock")
    
    with st.form("form_stock"):
        codigo = st.text_input("Código")
        producto = st.text_input("Nombre")
        marca = st.text_input("Marca")
        area = st.selectbox("Área", ["Farmacia", "Cajas", "Pasillos", "Equipos médicos", "Bodega"])
        stock = st.number_input("Stock", min_value=0, value=0)
        
        if st.form_submit_button("💾 Guardar"):
            db.guardar_producto(codigo, producto, marca, area, stock)
            st.success("✅ Producto guardado")
            st.rerun()

def mostrar_importar_excel():
    """Importar Excel simplificado"""
    if not tiene_permiso("admin"):
        st.error("⛔ No tienes permisos")
        return
    
    st.title("📤 Importar desde Excel")
    
    archivo = st.file_uploader("Seleccionar Excel", type=["xlsx", "xls"])
    
    if archivo:
        df = pd.read_excel(archivo)
        st.dataframe(df.head())
        
        if st.button("Importar"):
            for _, row in df.iterrows():
                db.guardar_producto(
                    str(row['codigo']),
                    row['producto'],
                    row.get('marca', 'SIN MARCA'),
                    row['area'],
                    int(row['stock_sistema'])
                )
            st.success("✅ Importación completada")

def mostrar_reportes():
    """Reportes simplificados"""
    st.title("📊 Reportes")
    
    tab1, tab2 = st.tabs(["Conteos", "Productos"])
    
    with tab1:
        df = cargar_conteos()
        if not df.empty:
            st.dataframe(df)
        else:
            st.info("No hay datos")
    
    with tab2:
        df = cargar_stock()
        if not df.empty:
            st.dataframe(df)
        else:
            st.info("No hay productos")

def mostrar_reportes_marca():
    """Reportes por marca"""
    st.title("🏷️ Reporte por Marcas")
    
    df = cargar_stock()
    if df.empty:
        st.info("No hay productos")
        return
    
    marcas = df['marca'].unique()
    marca_sel = st.selectbox("Seleccionar marca", marcas)
    
    df_filtrado = df[df['marca'] == marca_sel]
    st.dataframe(df_filtrado)

def mostrar_gestion_usuarios():
    """Gestión de usuarios"""
    if not tiene_permiso("admin"):
        st.error("⛔ No tienes permisos")
        return
    
    st.title("👥 Gestión de Usuarios")
    
    usuarios_df = cargar_usuarios()
    st.dataframe(usuarios_df[['username', 'nombre', 'rol', 'activo']])

def mostrar_configuracion():
    """Configuración"""
    if not tiene_permiso("admin"):
        st.error("⛔ No tienes permisos")
        return
    
    st.title("⚙️ Configuración")
    
    st.subheader("Estado del sistema")
    st.write(f"**Entorno:** {'Azure' if EN_AZURE else 'Local'}")
    st.write(f"**Base de datos:** Supabase")
    st.write(f"**Directorio temporal:** {BASE_PATH}")

# ======================================================
# APLICACIÓN PRINCIPAL
# ======================================================
def main():
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
    st.caption(f"📦 Sistema en {'Azure' if EN_AZURE else 'Local'} • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()