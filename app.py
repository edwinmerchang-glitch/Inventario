# app.py
import streamlit as st
import pandas as pd
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
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    if 'marca_seleccionada' not in st.session_state:
        st.session_state.marca_seleccionada = "Todas"

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
# FUNCIONES UTILITARIAS (AHORA USAN SOLO DB)
# ======================================================
def limpiar_codigo(codigo):
    return db.limpiar_codigo(codigo)

def cargar_stock():
    """Cargar stock desde la base de datos"""
    return db.obtener_todos_productos(st.session_state.get('marca_seleccionada', 'Todas'))

def cargar_conteos():
    """Cargar resumen de conteos desde la base de datos"""
    return db.obtener_resumen_conteos_hoy()

def cargar_escaneos_detallados():
    """Cargar historial de escaneos desde la base de datos"""
    return db.obtener_historial_completo()

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
                        autenticado, user, nombre, rol = db.verificar_login(username, password)
                        
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
    st.caption("📦 Sistema de Conteo de Inventario • v3.0 (SQLite)")

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
        
        opciones_disponibles = ["🏠 Dashboard"]
        
        if tiene_permiso("inventario"):
            opciones_disponibles.extend(["📥 Carga Stock", "🔢 Conteo Físico"])
        
        if tiene_permiso("admin"):
            opciones_disponibles.append("📤 Importar Excel")
        
        opciones_disponibles.extend(["📊 Reportes", "🏷️ Reporte por Marcas"])
        
        if tiene_permiso("admin"):
            opciones_disponibles.extend(["👥 Gestión Usuarios", "⚙️ Configuración"])
        
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
            st.metric("🔢 Conteos hoy", len(conteos_df))
        
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
        st.metric("📦 Productos", len(stock_df))
    
    with col2:
        st.metric("🔢 Conteos hoy", len(conteos_df))
    
    with col3:
        st.metric("📱 Escaneos totales", len(escaneos_df))
    
    with col4:
        if not conteos_df.empty:
            exactos = len(conteos_df[conteos_df["diferencia"] == 0])
            porcentaje = (exactos / len(conteos_df)) * 100 if len(conteos_df) > 0 else 0
            st.metric("🎯 Precisión", f"{porcentaje:.1f}%")
        else:
            st.metric("🎯 Precisión", "0%")
    
    st.markdown("---")
    
    col_left, col_center, col_right = st.columns(3)
    
    with col_left:
        st.subheader("📋 Últimos Productos")
        if not stock_df.empty:
            ultimos_productos = stock_df.tail(5)[["codigo", "producto", "marca", "area", "stock_sistema"]]
            st.dataframe(ultimos_productos, use_container_width=True, hide_index=True)
        else:
            st.info("No hay productos registrados")
    
    with col_center:
        st.subheader("📈 Últimos Conteos")
        if not conteos_df.empty:
            ultimos_conteos = conteos_df.head(5)[["usuario", "producto", "diferencia"]].copy()
            st.dataframe(ultimos_conteos, use_container_width=True, hide_index=True)
        else:
            st.info("No hay conteos registrados hoy")
    
    with col_right:
        st.subheader("📱 Últimos Escaneos")
        if not escaneos_df.empty:
            ultimos_escaneos = escaneos_df.head(5)[["timestamp", "usuario", "codigo", "cantidad_escaneada"]].copy()
            ultimos_escaneos["timestamp"] = pd.to_datetime(ultimos_escaneos["timestamp"]).dt.strftime("%H:%M:%S")
            st.dataframe(ultimos_escaneos, use_container_width=True, hide_index=True)
        else:
            st.info("No hay escaneos registrados")
    
    if tiene_permiso("inventario"):
        st.markdown("---")
        st.subheader(f"📊 Mis Estadísticas - {st.session_state.nombre}")
        
        mis_conteos = conteos_df[conteos_df["usuario"] == st.session_state.nombre] if not conteos_df.empty else pd.DataFrame()
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
                st.metric("Mis escaneos", len(mis_escaneos))

# ======================================================
# 2️⃣ PÁGINA: CARGA DE STOCK
# ======================================================
def mostrar_carga_stock():
    """Mostrar página de carga de stock"""
    if not tiene_permiso("inventario"):
        st.error("⛔ No tienes permisos para acceder a esta sección")
        return
    
    st.title("📥 Carga Manual de Stock")
    st.markdown("---")
    
    marcas = db.obtener_todas_marcas()
    
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
            marca = st.selectbox("Marca *", marcas)
        
        with col2:
            area = st.selectbox("Área *", ["Farmacia", "Cajas", "Pasillos", "Equipos médicos", "Bodega", "Otros"])
            stock = st.number_input("Stock en sistema *", min_value=0, step=1, value=0)
        
        if st.form_submit_button("💾 Guardar Producto", use_container_width=True):
            codigo_limpio = limpiar_codigo(codigo)
            if codigo_limpio and producto:
                db.guardar_producto(codigo_limpio, producto, marca, area, stock)
                st.success(f"✅ Producto guardado correctamente")
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
            areas = ["Todas"] + sorted(stock_df["area"].unique().tolist())
            area_filtro = st.selectbox("Filtrar por área", areas, key="filtro_area_stock")
        
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
# 3️⃣ PÁGINA: IMPORTAR DESDE EXCEL
# ======================================================
def mostrar_importar_excel():
    """Mostrar página de importación desde Excel"""
    if not tiene_permiso("admin"):
        st.error("⛔ No tienes permisos para acceder a esta sección")
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
            df_excel = pd.read_excel(archivo, dtype=str)
            st.success(f"✅ Archivo cargado: {archivo.name}")
            
            with st.expander("👁️ Vista previa", expanded=True):
                st.dataframe(df_excel.head(10), use_container_width=True)
            
            # Normalizar nombres de columnas
            df_excel.columns = df_excel.columns.str.lower().str.strip()
            
            columnas_requeridas = {"codigo", "producto", "area", "stock_sistema"}
            columnas_encontradas = set(df_excel.columns)
            
            if columnas_requeridas.issubset(columnas_encontradas):
                st.success("✅ Columnas verificadas correctamente")
                
                if 'marca' not in df_excel.columns:
                    df_excel['marca'] = 'SIN MARCA'
                    st.info("ℹ️ No se encontró columna 'marca'. Se usará 'SIN MARCA' por defecto.")
                
                total_registros = len(df_excel)
                st.info(f"📊 Total de registros a importar: {total_registros}")
                
                if st.button("🚀 Importar datos", type="primary", use_container_width=True):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    try:
                        status_text.text("Preparando datos...")
                        
                        # Limpiar datos
                        df_excel["codigo"] = df_excel["codigo"].apply(limpiar_codigo)
                        df_excel["stock_sistema"] = pd.to_numeric(df_excel["stock_sistema"], errors='coerce').fillna(0).astype(int)
                        
                        # Preparar batch
                        productos_batch = []
                        marcas_unicas = set()
                        
                        for idx, row in df_excel.iterrows():
                            if pd.notna(row["codigo"]) and pd.notna(row["producto"]):
                                productos_batch.append({
                                    'codigo': row["codigo"],
                                    'producto': row["producto"],
                                    'marca': row["marca"] if pd.notna(row["marca"]) else 'SIN MARCA',
                                    'area': row["area"],
                                    'stock_sistema': row["stock_sistema"]
                                })
                                marcas_unicas.add(row["marca"] if pd.notna(row["marca"]) else 'SIN MARCA')
                            
                            if idx % 100 == 0:
                                progress_bar.progress(min((idx + 1) / total_registros, 1.0))
                                status_text.text(f"Procesando {idx + 1} de {total_registros}...")
                        
                        status_text.text("Guardando en base de datos...")
                        db.guardar_productos_batch(productos_batch)
                        
                        status_text.text("Registrando marcas...")
                        for marca in marcas_unicas:
                            if pd.notna(marca):
                                db.crear_marca(marca)
                        
                        progress_bar.progress(1.0)
                        status_text.text("¡Importación completada!")
                        
                        st.success(f"✅ {len(productos_batch)} productos importados correctamente")
                        st.balloons()
                        
                    except Exception as e:
                        st.error(f"❌ Error durante la importación: {str(e)}")
            else:
                st.error(f"❌ Faltan columnas requeridas. Necesitas: {columnas_requeridas}")
                st.write("Columnas encontradas:", list(columnas_encontradas))
                
        except Exception as e:
            st.error(f"❌ Error al leer el archivo: {str(e)}")

# ======================================================
# 4️⃣ PÁGINA: CONTEO FÍSICO
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
    
    marcas = db.obtener_todas_marcas()
    marca_seleccionada = st.selectbox(
        "🏷️ Filtrar por marca",
        ["Todas"] + marcas,
        key="marca_conteo"
    )
    
    if marca_seleccionada != "Todas":
        stock_df = stock_df[stock_df["marca"] == marca_seleccionada]

    # Cargar producto actual de sesión
    if st.session_state.producto_actual_conteo:
        codigo_actual = st.session_state.producto_actual_conteo.get('codigo')
        producto_en_stock = stock_df[stock_df["codigo"].astype(str) == str(codigo_actual)]
        
        if not producto_en_stock.empty:
            prod = producto_en_stock.iloc[0]
            st.session_state.producto_actual_conteo = prod.to_dict()
        else:
            st.session_state.producto_actual_conteo = None

    # Calcular total escaneado
    total_contado = 0
    if st.session_state.producto_actual_conteo:
        total_contado = db.obtener_total_escaneado_hoy(
            usuario_actual, 
            st.session_state.producto_actual_conteo['codigo']
        )
        st.session_state.conteo_actual_session = total_contado

    # Panel de información del producto actual
    if st.session_state.producto_actual_conteo:
        prod = st.session_state.producto_actual_conteo
        st.subheader("📊 Producto actual")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.info(f"**Producto:**\n{prod['producto']}")
        with col2:
            st.info(f"**Código:**\n{prod['codigo']}")
        with col3:
            st.info(f"**Marca:**\n{prod.get('marca', 'SIN MARCA')}")
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
            escaneos_hoy = db.obtener_escaneos_hoy(usuario=usuario_actual)
            st.metric("Mis escaneos hoy", len(escaneos_hoy))

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

    # Procesar escaneo
    if enviar or enviar_1:
        if enviar_1:
            cantidad = 1

        codigo_limpio = limpiar_codigo(codigo)

        if not codigo_limpio:
            st.error("❌ Ingrese un código")
        else:
            exito, resultado = db.registrar_escaneo(usuario_actual, codigo_limpio, cantidad)
            
            if exito:
                prod = resultado['producto']
                st.session_state.producto_actual_conteo = prod
                st.session_state.conteo_actual_session = resultado['nuevo_total']
                
                st.success(f"✅ +{cantidad} = {resultado['nuevo_total']} (Diferencia: {resultado['diferencia']:+d})")
                time.sleep(0.5)
                st.rerun()
            else:
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

    # Botones de acción
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
                historial = db.obtener_escaneos_hoy(
                    usuario=usuario_actual,
                    codigo=st.session_state.producto_actual_conteo['codigo']
                )
                if not historial.empty:
                    st.dataframe(historial[['timestamp', 'cantidad_escaneada', 'total_acumulado', 'diferencia']].head(10))

# ======================================================
# 5️⃣ PÁGINA: REPORTE POR MARCAS
# ======================================================
def mostrar_reportes_marca():
    """Mostrar reportes detallados por marca"""
    st.title("🏷️ Reporte por Marcas")
    st.markdown("---")
    
    try:
        resumen_marcas = db.obtener_resumen_por_marca()
        
        if resumen_marcas.empty:
            st.warning("No hay datos de marcas disponibles")
            return
        
        st.subheader("📊 Resumen General por Marcas")
        
        st.dataframe(
            resumen_marcas,
            use_container_width=True,
            hide_index=True,
            column_config={
                'marca': 'Marca',
                'total_productos': 'Total Prod.',
                'productos_contados': 'Contados',
                'productos_no_escaneados': 'No Escaneados',
                'porcentaje_avance': st.column_config.NumberColumn('Avance', format="%.1f%%"),
                'stock_total_sistema': 'Stock Sistema',
                'total_contado': 'Total Contado',
                'diferencia_neta': st.column_config.NumberColumn('Dif. Neta', format="%+d")
            }
        )
        
        st.markdown("---")
        
        marcas = resumen_marcas['marca'].tolist()
        if marcas:
            marca_seleccionada = st.selectbox("🔍 Seleccionar marca para ver detalle", marcas)
            
            if marca_seleccionada:
                st.subheader(f"📋 Detalle de productos - {marca_seleccionada}")
                
                solo_no_escaneados = st.checkbox("Mostrar solo productos NO escaneados")
                
                detalle = db.obtener_detalle_productos_por_marca(
                    marca_seleccionada, 
                    solo_no_escaneados=solo_no_escaneados
                )
                
                if not detalle.empty:
                    stats = db.obtener_estadisticas_marca(marca_seleccionada)
                    
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        st.metric("Total Productos", stats.get('total_productos', 0))
                    with col2:
                        st.metric("Productos Contados", stats.get('productos_contados', 0))
                    with col3:
                        st.metric("No Escaneados", stats.get('productos_no_contados', 0))
                    with col4:
                        st.metric("Stock Total", stats.get('stock_total', 0))
                    with col5:
                        st.metric("Diferencia Neta", f"{stats.get('diferencia_neta', 0):+,d}")
                    
                    st.subheader("📊 Distribución por Estado")
                    col_graf1, col_graf2, col_graf3 = st.columns(3)
                    
                    with col_graf1:
                        st.metric("✅ Exactos", stats.get('exactos', 0))
                    with col_graf2:
                        leves = stats.get('sobrantes_leves', 0) + stats.get('faltantes_leves', 0)
                        st.metric("⚠️ Diferencias Leves", leves)
                    with col_graf3:
                        st.metric("🔴 Diferencias Críticas", stats.get('diferencias_criticas', 0))
                    
                    st.subheader("📋 Listado de Productos")
                    
                    # Función para colorear
                    def color_estado(val):
                        if val == 'NO_ESCANEADO':
                            return 'background-color: #fff3cd'
                        elif val == 'OK':
                            return 'background-color: #d4edda'
                        elif val in ['LEVE', 'CRITICA']:
                            return 'background-color: #f8d7da'
                        return ''
                    
                    detalle_display = detalle.copy()
                    if 'diferencia' in detalle_display.columns:
                        detalle_display['diferencia'] = detalle_display['diferencia'].apply(lambda x: f"{x:+,d}")
                    
                    styled_df = detalle_display.style.applymap(color_estado, subset=['estado'])
                    st.dataframe(styled_df, use_container_width=True, hide_index=True)
                    
                    if st.button("📥 Exportar detalle a CSV"):
                        csv = detalle.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "⬇️ Descargar CSV",
                            data=csv,
                            file_name=f"detalle_{marca_seleccionada}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            mime="text/csv"
                        )
                else:
                    st.info(f"No hay productos para la marca {marca_seleccionada}")
    except Exception as e:
        st.error(f"Error al cargar reportes: {str(e)}")

# ======================================================
# 6️⃣ PÁGINA: REPORTES GENERALES
# ======================================================
def mostrar_reportes():
    """Mostrar página de reportes generales"""
    st.title("📊 Reportes de Conteo")
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["📈 Resumen General", "🏷️ Por Marcas", "📋 Historial Completo"])
    
    with tab1:
        mostrar_resumen_general()
    
    with tab2:
        mostrar_reportes_marca()
    
    with tab3:
        mostrar_historial_completo()

def mostrar_resumen_general():
    """Mostrar resumen general de conteos"""
    conteos_df = cargar_conteos()
    escaneos_df = cargar_escaneos_detallados()
    
    st.subheader("📈 Métricas Principales")
    
    if escaneos_df.empty:
        st.info("📭 No hay escaneos registrados")
    else:
        total_escaneos = len(escaneos_df)
        productos_contados = escaneos_df['codigo'].nunique() if 'codigo' in escaneos_df.columns else 0
        total_unidades = escaneos_df['cantidad_escaneada'].sum() if 'cantidad_escaneada' in escaneos_df.columns else 0
        usuarios_activos = escaneos_df['usuario'].nunique() if 'usuario' in escaneos_df.columns else 0
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        
        with col_m1:
            st.metric("📦 Productos contados", productos_contados)
        with col_m2:
            st.metric("🔢 Total escaneos", total_escaneos)
        with col_m3:
            st.metric("📦 Unidades contadas", total_unidades)
        with col_m4:
            st.metric("👥 Usuarios activos", usuarios_activos)
    
    st.markdown("---")
    st.subheader("🎯 Análisis de Precisión")
    
    if not conteos_df.empty:
        total_productos = len(conteos_df)
        exactos = len(conteos_df[conteos_df["diferencia"] == 0])
        sobrantes = len(conteos_df[conteos_df["diferencia"] > 0])
        faltantes = len(conteos_df[conteos_df["diferencia"] < 0])
        
        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        
        with col_p1:
            st.metric("✅ Conteos exactos", f"{exactos} de {total_productos}", 
                     f"{(exactos/total_productos*100):.1f}%" if total_productos > 0 else "0%")
        with col_p2:
            st.metric("⚠️ Sobrantes", sobrantes)
        with col_p3:
            st.metric("🔻 Faltantes", faltantes)
        with col_p4:
            diferencia_neta = conteos_df['diferencia'].sum()
            st.metric("📊 Diferencia neta", f"{diferencia_neta:+,d}")
        
        st.markdown("---")
        st.subheader("📋 Productos con diferencias")
        
        productos_con_diferencia = conteos_df[conteos_df["diferencia"] != 0].copy()
        
        if not productos_con_diferencia.empty:
            productos_con_diferencia = productos_con_diferencia.sort_values('diferencia', ascending=False)
            st.dataframe(
                productos_con_diferencia[['producto', 'stock_sistema', 'conteo_fisico', 'diferencia']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No hay productos con diferencias")
    else:
        st.info("📭 No hay suficientes datos para análisis de precisión")

def mostrar_historial_completo():
    """Mostrar historial completo de escaneos"""
    escaneos_df = cargar_escaneos_detallados()
    
    if not escaneos_df.empty:
        st.subheader("📋 Historial de Escaneos")
        
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            if 'timestamp' in escaneos_df.columns:
                escaneos_df['fecha'] = pd.to_datetime(escaneos_df['timestamp']).dt.date
                fechas = sorted(escaneos_df['fecha'].unique(), reverse=True)
                fecha_inicio = st.selectbox("Fecha inicio", fechas, index=0)
            else:
                fecha_inicio = datetime.now().date()
        
        with col_f2:
            if 'usuario' in escaneos_df.columns:
                usuarios = ["Todos"] + escaneos_df['usuario'].unique().tolist()
                usuario_filtro = st.selectbox("Usuario", usuarios)
        
        with col_f3:
            registros_mostrar = st.selectbox("Registros a mostrar", [50, 100, 200, 500, 1000], index=0)
        
        df_filtrado = escaneos_df.copy()
        
        if 'fecha' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['fecha'] == fecha_inicio]
        
        if 'usuario_filtro' in locals() and usuario_filtro != "Todos":
            df_filtrado = df_filtrado[df_filtrado['usuario'] == usuario_filtro]
        
        df_filtrado = df_filtrado.head(registros_mostrar)
        
        st.dataframe(
            df_filtrado,
            use_container_width=True,
            hide_index=True
        )
        
        st.metric("Registros mostrados", len(df_filtrado))
        
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
# 7️⃣ PÁGINA: GESTIÓN DE USUARIOS
# ======================================================
def mostrar_gestion_usuarios():
    """Mostrar página de gestión de usuarios"""
    if not tiene_permiso("admin"):
        st.error("⛔ No tienes permisos para acceder a esta sección")
        return
    
    st.title("👥 Gestión de Usuarios")
    st.markdown("---")
    
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
                exito, mensaje = db.crear_usuario(nuevo_username, nuevo_nombre, nuevo_password, nuevo_rol)
                if exito:
                    st.success(mensaje)
                    st.rerun()
                else:
                    st.error(mensaje)
            else:
                st.error("❌ Todos los campos son obligatorios")
    
    st.markdown("---")
    st.subheader("📋 Usuarios del sistema")
    
    usuarios_df = db.obtener_todos_usuarios()
    
    if not usuarios_df.empty:
        st.dataframe(usuarios_df, use_container_width=True)
        
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        
        with col_stat1:
            st.metric("Total usuarios", len(usuarios_df))
        with col_stat2:
            activos = len(usuarios_df[usuarios_df["activo"] == 1]) if "activo" in usuarios_df.columns else 0
            st.metric("Usuarios activos", activos)
        with col_stat3:
            admins = len(usuarios_df[usuarios_df["rol"] == "admin"])
            st.metric("Administradores", admins)
    else:
        st.info("No hay usuarios registrados")

# ======================================================
# 8️⃣ PÁGINA: CONFIGURACIÓN
# ======================================================
def mostrar_configuracion():
    """Mostrar página de configuración"""
    if not tiene_permiso("admin"):
        st.error("⛔ No tienes permisos para acceder a esta sección")
        return
    
    st.title("⚙️ Configuración del Sistema")
    st.markdown("---")
    
    st.subheader("🏷️ Gestión de Marcas")
    
    marcas = db.obtener_todas_marcas()
    st.write("**Marcas disponibles:**")
    st.write(", ".join(marcas))
    
    with st.form("nueva_marca_config"):
        nueva_marca = st.text_input("Agregar nueva marca")
        if st.form_submit_button("➕ Agregar"):
            if nueva_marca:
                if db.crear_marca(nueva_marca):
                    st.success(f"Marca '{nueva_marca}' agregada")
                    st.rerun()
                else:
                    st.error("La marca ya existe")
    
    st.markdown("---")
    st.subheader("📊 Estadísticas del Sistema")
    
    stock_df = cargar_stock()
    conteos_df = cargar_conteos()
    escaneos_df = cargar_escaneos_detallados()
    usuarios_df = db.obtener_todos_usuarios()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Productos", len(stock_df))
    with col2:
        st.metric("Conteos hoy", len(conteos_df))
    with col3:
        st.metric("Usuarios", len(usuarios_df))
    with col4:
        st.metric("Escaneos totales", len(escaneos_df))
    
    st.markdown("---")
    st.subheader("🔄 Mantenimiento")
    
    st.info("""
    **Nota sobre actualizaciones:**
    - Los datos se guardan en SQLite (`inventario.db`)
    - Puedes actualizar el código en GitHub y hacer reboot sin perder datos
    - La base de datos persiste entre reinicios
    """)
    
    if st.button("🧹 Limpiar caché de la aplicación", use_container_width=True):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success("✅ Caché limpiado. La aplicación se recargará con el nuevo código.")
        time.sleep(2)
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
    st.caption(f"📦 Sistema de Conteo de Inventario v3.0 (SQLite) • {st.session_state.rol.upper()} • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()