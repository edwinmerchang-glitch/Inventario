import streamlit as st
import pandas as pd
import os
from datetime import datetime
import time  # Agrega esta importación

from backup_manager import backup_to_github, restore_from_github
from utils import cargar_escaneos, ARCHIVO_ESCANEOS
import database as db

restore_from_github()
db.init_database()

st.set_page_config(
    page_title="Inventarios PRO",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- ESTADO ----------

if "usuario" not in st.session_state:
    st.session_state.usuario = "admin"

if "escaneos" not in st.session_state:
    st.session_state.escaneos = 0

# ---------- UI ----------

st.sidebar.title("📦 Inventarios PRO")

menu = st.sidebar.radio("", [
    "📷 Conteo rápido",
    "📊 Reportes",
    "📥 Importar productos"
])

# ---------- FUNCIONES ----------

def guardar_csv(registro):
    df = pd.DataFrame([registro])

    if os.path.exists(ARCHIVO_ESCANEOS):
        df_old = pd.read_csv(ARCHIVO_ESCANEOS)
        df = pd.concat([df_old, df], ignore_index=True)

    df.to_csv(ARCHIVO_ESCANEOS, index=False)


def conteo_rapido():
    st.title("📷 Conteo rápido")

    with st.form("scan", clear_on_submit=True):
        codigo = st.text_input("Código", autofocus=True)
        cantidad = st.number_input("Cantidad", 1, 1000, 1)

        if st.form_submit_button("Registrar"):
            prod = db.obtener_producto(codigo)

            if not prod:
                st.error("Producto no encontrado")
                return

            db.registrar_conteo(st.session_state.usuario, prod, cantidad)

            guardar_csv({
                "fecha": datetime.now(),
                "usuario": st.session_state.usuario,
                "codigo": codigo,
                "producto": prod["producto"],
                "cantidad": cantidad
            })

            st.session_state.escaneos += 1

            if st.session_state.escaneos % 40 == 0:
                backup_to_github()

            st.success(f"✅ {prod['producto']} +{cantidad}")


def reportes():
    st.title("📊 Reportes")

    df = cargar_escaneos()

    if df.empty:
        st.info("No hay datos")
        return

    st.dataframe(df, use_container_width=True)


def importar():
    st.title("📥 Importar productos")

    archivo = st.file_uploader("Subir Excel", type=["xlsx"])

    if archivo:
        df = pd.read_excel(archivo)
        
        # Validar columnas necesarias
        columnas_requeridas = ["codigo", "producto"]
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        
        if columnas_faltantes:
            st.error(f"El Excel debe contener las columnas: {', '.join(columnas_faltantes)}")
            return
        
        # Mostrar información del archivo
        st.info(f"📊 Archivo con {len(df)} productos")
        
        # Vista previa
        with st.expander("Vista previa de los datos"):
            st.dataframe(df.head(10))
            if len(df) > 10:
                st.caption(f"Mostrando 10 de {len(df)} registros")

        if st.button(f"🚀 Importar {len(df)} productos", type="primary"):
            # Medir tiempo de inicio
            start_time = time.time()
            
            with st.spinner(f"Importando {len(df)} productos..."):
                try:
                    # Usar la función de inserción masiva
                    cantidad = db.guardar_productos_masivo(df)
                    
                    # Calcular tiempo transcurrido
                    elapsed_time = time.time() - start_time
                    
                    # Hacer backup
                    backup_to_github()
                    
                    # Mostrar éxito con tiempo
                    st.success(f"✅ {cantidad} productos importados correctamente en {elapsed_time:.2f} segundos")
                    
                    # Mostrar velocidad de importación
                    velocidad = cantidad / elapsed_time
                    st.info(f"⚡ Velocidad: {velocidad:.0f} productos/segundo")
                    
                except Exception as e:
                    st.error(f"Error durante la importación: {str(e)}")


# ---------- NAVEGACIÓN ----------

if menu == "📷 Conteo rápido":
    conteo_rapido()

elif menu == "📊 Reportes":
    reportes()

elif menu == "📥 Importar productos":
    importar()