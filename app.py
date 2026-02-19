import streamlit as st
import pandas as pd
import os
import hashlib
from datetime import datetime
import time

# ======================================================
# CONFIGURACIÓN GENERAL
# ======================================================
st.set_page_config(
    page_title="Sistema de Conteo de Inventario",
    page_icon="📦",
    layout="centered",
    initial_sidebar_state="expanded"
)

# USAR LA MISMA RUTA EN TODO EL PROGRAMA
ARCHIVO_STOCK = "stock_sistema.csv"
ARCHIVO_CONTEOS = "conteos.csv"
ARCHIVO_USUARIOS = "usuarios.csv"
ARCHIVO_ESCANEOS = "escaneos_detallados.csv"

# ======================================================
# DIAGNÓSTICO - Ver dónde se están guardando los archivos
# ======================================================
st.sidebar.markdown("---")
st.sidebar.subheader("🔧 DIAGNÓSTICO")
st.sidebar.write(f"Directorio actual: {os.getcwd()}")
st.sidebar.write(f"Existe escaneos.csv: {os.path.exists(ARCHIVO_ESCANEOS)}")

if os.path.exists(ARCHIVO_ESCANEOS):
    try:
        tamaño = os.path.getsize(ARCHIVO_ESCANEOS)
        st.sidebar.write(f"Tamaño del archivo: {tamaño} bytes")
    except:
        st.sidebar.write("Error al leer tamaño")

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
    """Cargar escaneos - AHORA LEE SIEMPRE DEL MISMO ARCHIVO"""
    if os.path.exists(ARCHIVO_ESCANEOS):
        try:
            df = pd.read_csv(ARCHIVO_ESCANEOS)
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            # Asegurar que las columnas numéricas lo sean
            if 'cantidad_escaneada' in df.columns:
                df['cantidad_escaneada'] = pd.to_numeric(df['cantidad_escaneada'], errors='coerce').fillna(0).astype(int)
            if 'total_acumulado' in df.columns:
                df['total_acumulado'] = pd.to_numeric(df['total_acumulado'], errors='coerce').fillna(0).astype(int)
            if 'stock_sistema' in df.columns:
                df['stock_sistema'] = pd.to_numeric(df['stock_sistema'], errors='coerce').fillna(0).astype(int)
            return df
        except Exception as e:
            print(f"Error cargando escaneos: {e}")
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
    """Guardar UN escaneo individual PERMANENTEMENTE - VERSIÓN CORREGIDA"""
    try:
        # Asegurar que los números sean enteros
        escaneo_data['cantidad_escaneada'] = int(escaneo_data['cantidad_escaneada'])
        escaneo_data['total_acumulado'] = int(escaneo_data['total_acumulado'])
        escaneo_data['stock_sistema'] = int(escaneo_data['stock_sistema'])
        
        # Crear DataFrame con el nuevo registro
        nuevo_registro = pd.DataFrame([escaneo_data])
        
        # Leer o crear el archivo
        if os.path.exists(ARCHIVO_ESCANEOS):
            df_existente = pd.read_csv(ARCHIVO_ESCANEOS)
            # Asegurar que todas las columnas existen
            for col in nuevo_registro.columns:
                if col not in df_existente.columns:
                    df_existente[col] = None
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
            nuevo = pd.DataFrame([[f"{hoy} {datetime.now().strftime('%H:%M:%S')}", usuario, codigo, producto, area, stock_sistema, nuevo_total, nuevo_total - stock_sistema]], 
                                columns=conteos_df.columns)
            conteos_df = pd.concat([conteos_df, nuevo], ignore_index=True)
        
        guardar_conteos(conteos_df)
        return True
    except Exception as e:
        print(f"Error actualizando resumen: {e}")
        return False

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
                key="filtro_area_stock"
            )
        
        with col_filt2:
            buscar = st.text_input("Buscar por código o nombre", key="buscar_stock_input")
        
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
# 4️⃣ PÁGINA: CONTEO FÍSICO - VERSIÓN CORREGIDA
# ======================================================
def mostrar_conteo_fisico():
    """Mostrar página de conteo físico - VERSIÓN CORREGIDA"""
    if not tiene_permiso("inventario"):
        st.error("⛔ No tienes permisos para acceder a esta sección")
        st.info("Solo usuarios con rol 'inventario' o 'admin' pueden realizar conteos")
        return

    st.title("🔢 Conteo Físico")
    st.markdown("---")

    # Cargar datos
    stock_df = cargar_stock()
    conteos_df = cargar_conteos()
    usuario_actual = st.session_state.nombre
    hoy = datetime.now().strftime("%Y-%m-%d")

    # --- FUNCIÓN PARA VER EL CSV ---
    def mostrar_contenido_csv():
        if os.path.exists(ARCHIVO_ESCANEOS):
            try:
                df = pd.read_csv(ARCHIVO_ESCANEOS)
                st.write(f"**Total de registros en CSV:** {len(df)}")
                st.write(f"**Columnas:** {list(df.columns)}")
                st.dataframe(df)
                return df
            except Exception as e:
                st.error(f"Error leyendo CSV: {e}")
        else:
            st.warning("⚠️ El archivo CSV NO EXISTE")
        return None

    # --- FUNCIÓN PARA CALCULAR TOTAL (CORREGIDA) ---
    def total_escaneado_hoy(usuario, codigo):
        """Calcula el total escaneado hoy por un usuario para un código específico"""
        if not os.path.exists(ARCHIVO_ESCANEOS):
            return 0

        try:
            df = pd.read_csv(ARCHIVO_ESCANEOS)

            if df.empty:
                return 0

            # Verificar que existe la columna cantidad_escaneada
            if 'cantidad_escaneada' not in df.columns:
                st.error("⚠️ El CSV no tiene columna 'cantidad_escaneada'")
                return 0

            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df['fecha'] = df['timestamp'].dt.strftime('%Y-%m-%d')

            hoy = datetime.now().strftime('%Y-%m-%d')

            # Filtrar
            mask = (df['fecha'] == hoy) & (df['usuario'] == usuario) & (df['codigo'].astype(str) == str(codigo))
            df_filtrado = df[mask]

            if df_filtrado.empty:
                return 0

            # Asegurar que sea número y sumar
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

        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"**Producto:**\n{prod['nombre']}")
        with col2:
            st.info(f"**Código:**\n{prod['codigo']}")
        with col3:
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

        # --- EXPANDER DE DIAGNÓSTICO ---
        with st.expander("🔍 DIAGNÓSTICO - Ver contenido del CSV", expanded=True):
            mostrar_contenido_csv()

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
                        nuevo_area = st.selectbox("Área", ["Farmacia", "Cajas", "Pasillos", "Equipos médicos", "Bodega", "Otros"])
                        nuevo_stock = st.number_input("Stock inicial", min_value=0, value=0, step=1)

                        if st.form_submit_button("💾 Guardar"):
                            if nuevo_nombre:
                                nuevo = pd.DataFrame([[codigo_limpio, nuevo_nombre, nuevo_area, nuevo_stock]],
                                                    columns=["codigo", "producto", "area", "stock_sistema"])
                                stock_df = pd.concat([stock_df, nuevo], ignore_index=True)
                                guardar_stock(stock_df)
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
                    "area": prod["area"],
                    "cantidad_escaneada": int(cantidad),
                    "total_acumulado": int(nuevo_total),
                    "stock_sistema": int(prod["stock_sistema"]),
                    "tipo_operacion": "ESCANEO"
                }])

                # Guardar en CSV
                if os.path.exists(ARCHIVO_ESCANEOS):
                    # Si existe, leer y concatenar
                    df_existente = pd.read_csv(ARCHIVO_ESCANEOS)
                    df_final = pd.concat([df_existente, nuevo_registro], ignore_index=True)
                else:
                    # Si no existe, crear nuevo
                    df_final = nuevo_registro

                # Guardar
                df_final.to_csv(ARCHIVO_ESCANEOS, index=False)

                # Actualizar resumen de conteos
                actualizar_resumen_conteo(
                    usuario_actual, codigo_limpio, prod["producto"],
                    prod["area"], int(prod["stock_sistema"]), nuevo_total
                )

                # Actualizar sesión
                st.session_state.producto_actual_conteo = {
                    'codigo': codigo_limpio,
                    'nombre': prod["producto"],
                    'area': prod["area"],
                    'stock_sistema': int(prod["stock_sistema"])
                }
                st.session_state.conteo_actual_session = nuevo_total
                st.session_state.total_escaneos_session += 1

                st.success(f"✅ +{cantidad} = {nuevo_total}")
                time.sleep(0.5)
                st.rerun()

    # --- Botones de acción ---
    if st.session_state.producto_actual_conteo:
        st.markdown("---")
        col_acc1, col_acc2 = st.columns(2)
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

# ======================================================
# 5️⃣ PÁGINA: REPORTES - VERSIÓN SIN RESUMEN POR ÁREA
# ======================================================
def mostrar_reportes():
    """Mostrar página de reportes con resumen claro y útil"""
    st.title("📊 Reportes de Conteo")
    st.markdown("---")
    
    conteos_df = cargar_conteos()
    escaneos_df = cargar_escaneos_detallados()
    
    # ==============================================
    # SECCIÓN 1: MÉTRICAS PRINCIPALES
    # ==============================================
    st.subheader("📈 Métricas Principales")
    
    if escaneos_df.empty:
        st.info("📭 No hay escaneos registrados")
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
                     help="Número total de veces que se ha escaneado (incluye múltiples escaneos del mismo producto)")
        
        with col_m3:
            st.metric("📦 Unidades contadas", total_unidades,
                     help="Suma total de todas las cantidades escaneadas")
        
        with col_m4:
            st.metric("👥 Usuarios activos", usuarios_activos,
                     help="Número de usuarios que han realizado escaneos")
    
    st.markdown("---")
    
    # ==============================================
    # SECCIÓN 2: ANÁLISIS DE PRECISIÓN
    # ==============================================
    st.subheader("🎯 Análisis de Precisión")
    
    if not conteos_df.empty and not escaneos_df.empty:
        # Crear resumen por producto para análisis de precisión
        resumen_precision = escaneos_df.groupby(['codigo', 'producto', 'area', 'stock_sistema']).agg({
            'cantidad_escaneada': 'sum'
        }).reset_index()
        
        resumen_precision.columns = ['codigo', 'producto', 'area', 'stock_sistema', 'conteo_fisico']
        resumen_precision['diferencia'] = resumen_precision['conteo_fisico'] - resumen_precision['stock_sistema']
        resumen_precision['estado'] = resumen_precision['diferencia'].apply(
            lambda x: '✅ Exacto' if x == 0 else ('⚠️ Sobrante' if x > 0 else '🔻 Faltante')
        )
        
        # Calcular estadísticas de precisión
        total_productos = len(resumen_precision)
        exactos = len(resumen_precision[resumen_precision['diferencia'] == 0])
        sobrantes = len(resumen_precision[resumen_precision['diferencia'] > 0])
        faltantes = len(resumen_precision[resumen_precision['diferencia'] < 0])
        
        # Mostrar en 4 columnas con colores
        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        
        with col_p1:
            st.metric("✅ Conteos exactos", f"{exactos} de {total_productos}", 
                     f"{(exactos/total_productos*100):.1f}%",
                     help="Productos donde el conteo físico coincide con el stock del sistema")
        
        with col_p2:
            st.metric("⚠️ Sobrantes", sobrantes,
                     help="Productos donde se contó MÁS de lo que indica el sistema")
        
        with col_p3:
            st.metric("🔻 Faltantes", faltantes,
                     help="Productos donde se contó MENOS de lo que indica el sistema")
        
        with col_p4:
            # Diferencia neta total
            diferencia_neta = resumen_precision['diferencia'].sum()
            st.metric("📊 Diferencia neta", f"{diferencia_neta:+,d}",
                     delta_color="off" if diferencia_neta == 0 else ("normal" if diferencia_neta > 0 else "inverse"),
                     help="Suma total de todas las diferencias (positivo = sobrante general, negativo = faltante general)")
        
        # Mostrar productos con mayores diferencias
        st.markdown("---")
        st.subheader("🔍 Productos con mayores diferencias")
        
        col_tab1, col_tab2 = st.columns(2)
        
        with col_tab1:
            st.write("**Top 5 sobrantes**")
            sobrantes_top = resumen_precision[resumen_precision['diferencia'] > 0].nlargest(5, 'diferencia')
            if not sobrantes_top.empty:
                sobrantes_top = sobrantes_top[['codigo', 'producto', 'stock_sistema', 'conteo_fisico', 'diferencia']].copy()
                sobrantes_top.columns = ['Código', 'Producto', 'Stock', 'Contado', 'Sobrante']
                st.dataframe(sobrantes_top, use_container_width=True, hide_index=True)
            else:
                st.info("No hay productos con sobrantes")
        
        with col_tab2:
            st.write("**Top 5 faltantes**")
            faltantes_top = resumen_precision[resumen_precision['diferencia'] < 0].nsmallest(5, 'diferencia')
            if not faltantes_top.empty:
                faltantes_top = faltantes_top[['codigo', 'producto', 'stock_sistema', 'conteo_fisico', 'diferencia']].copy()
                faltantes_top.columns = ['Código', 'Producto', 'Stock', 'Contado', 'Faltante']
                st.dataframe(faltantes_top, use_container_width=True, hide_index=True)
            else:
                st.info("No hay productos con faltantes")
    
    else:
        st.info("📭 No hay suficientes datos para análisis de precisión")
    
    st.markdown("---")
    
    # ==============================================
    # SECCIÓN 3: DETALLE POR PRODUCTO
    # ==============================================
    st.subheader("📋 Detalle por Producto")
    
    if not escaneos_df.empty:
        # Crear resumen agrupado por producto
        resumen_productos = escaneos_df.groupby(['codigo', 'producto', 'area']).agg({
            'cantidad_escaneada': 'sum',
            'stock_sistema': 'first',
            'usuario': lambda x: ', '.join(x.unique()),  # Lista de usuarios que escanearon
            'timestamp': ['max', 'count']  # Último escaneo y total de escaneos
        }).reset_index()
        
        # Aplanar columnas multiíndice
        resumen_productos.columns = ['codigo', 'producto', 'area', 'total_contado', 
                                    'stock_sistema', 'usuarios', 'ultimo_escaneo', 'veces_escaneado']
        
        # Calcular diferencia
        resumen_productos['diferencia'] = resumen_productos['total_contado'] - resumen_productos['stock_sistema']
        
        # Formatear fecha
        resumen_productos['ultimo_escaneo'] = pd.to_datetime(resumen_productos['ultimo_escaneo']).dt.strftime('%Y-%m-%d %H:%M')
        
        # Agregar columna de estado visual
        resumen_productos['estado'] = resumen_productos['diferencia'].apply(
            lambda x: '✅' if x == 0 else ('⚠️' if x > 0 else '🔻')
        )
        
        # Agregar columna de índice
        resumen_productos.insert(0, '#', range(1, len(resumen_productos) + 1))
        
        # Filtros
        col_filt1, col_filt2, col_filt3 = st.columns(3)
        
        with col_filt1:
            estado_filtro = st.selectbox(
                "Filtrar por estado",
                ["Todos", "✅ Exactos", "⚠️ Sobrantes", "🔻 Faltantes"]
            )
        
        with col_filt2:
            area_filtro = st.selectbox(
                "Filtrar por área",
                ["Todas"] + sorted(resumen_productos['area'].unique().tolist())
            )
        
        with col_filt3:
            buscar = st.text_input("🔍 Buscar producto", placeholder="Código o nombre")
        
        # Aplicar filtros
        df_filtrado = resumen_productos.copy()
        
        if estado_filtro != "Todos":
            if estado_filtro == "✅ Exactos":
                df_filtrado = df_filtrado[df_filtrado['diferencia'] == 0]
            elif estado_filtro == "⚠️ Sobrantes":
                df_filtrado = df_filtrado[df_filtrado['diferencia'] > 0]
            elif estado_filtro == "🔻 Faltantes":
                df_filtrado = df_filtrado[df_filtrado['diferencia'] < 0]
        
        if area_filtro != "Todas":
            df_filtrado = df_filtrado[df_filtrado['area'] == area_filtro]
        
        if buscar:
            mask = df_filtrado['codigo'].astype(str).str.contains(buscar, case=False, na=False) | \
                   df_filtrado['producto'].astype(str).str.contains(buscar, case=False, na=False)
            df_filtrado = df_filtrado[mask]
        
        # Mostrar tabla
        st.dataframe(
            df_filtrado[['#', 'estado', 'codigo', 'producto', 'area', 'stock_sistema', 
                        'total_contado', 'diferencia', 'veces_escaneado', 'usuarios', 'ultimo_escaneo']],
            use_container_width=True,
            hide_index=True,
            column_config={
                'estado': '📊',
                'diferencia': st.column_config.NumberColumn(format="%+d")
            }
        )
        
        st.caption(f"Mostrando {len(df_filtrado)} de {len(resumen_productos)} productos")
    
    else:
        st.info("📭 No hay escaneos registrados para mostrar detalle")
    
    st.markdown("---")
    
    # ==============================================
    # SECCIÓN 4: EXPORTAR DATOS
    # ==============================================
    st.subheader("💾 Exportar datos")
    
    col_exp1, col_exp2, col_exp3 = st.columns(3)
    
    with col_exp1:
        if not escaneos_df.empty:
            # Crear resumen para exportar
            resumen_export = escaneos_df.groupby(['codigo', 'producto', 'area', 'stock_sistema']).agg({
                'cantidad_escaneada': 'sum',
                'usuario': lambda x: ', '.join(x.unique()),
                'timestamp': 'max'
            }).reset_index()
            resumen_export.columns = ['codigo', 'producto', 'area', 'stock_sistema', 
                                     'total_contado', 'usuarios', 'ultimo_escaneo']
            resumen_export['diferencia'] = resumen_export['total_contado'] - resumen_export['stock_sistema']
            
            st.download_button(
                "📥 Exportar resumen por producto (CSV)",
                data=resumen_export.to_csv(index=False).encode("utf-8"),
                file_name=f"resumen_productos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    with col_exp2:
        if not escaneos_df.empty:
            st.download_button(
                "📥 Exportar historial completo (CSV)",
                data=escaneos_df.to_csv(index=False).encode("utf-8"),
                file_name=f"historial_completo_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    with col_exp3:
        if not conteos_df.empty:
            st.download_button(
                "📥 Exportar resumen original (CSV)",
                data=conteos_df.to_csv(index=False).encode("utf-8"),
                file_name=f"resumen_conteos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )

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