import streamlit as st
import pandas as pd
import os
import database as db

@st.cache_data(ttl=10)
def cargar_escaneos_cached():
    """Versión cacheada de carga de escaneos"""
    return db.obtener_todos_escaneos()

@st.cache_data(ttl=10)
def cargar_productos_cached():
    """Versión cacheada de carga de productos"""
    return db.obtener_todos_productos()