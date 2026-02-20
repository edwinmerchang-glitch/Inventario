import streamlit as st
import pandas as pd
import os

ARCHIVO_ESCANEOS = "escaneos.csv"

@st.cache_data(ttl=10)
def cargar_escaneos():
    if os.path.exists(ARCHIVO_ESCANEOS):
        return pd.read_csv(ARCHIVO_ESCANEOS)
    return pd.DataFrame()
