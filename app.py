import streamlit as st
import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

# ======================================================
# HEALTH CHECK PARA AZURE - ESTO ES CRÍTICO
# ======================================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
    
    def log_message(self, format, *args):
        # Silenciar logs del health check
        pass

def run_health_server():
    """Ejecuta un servidor HTTP simple para health checks"""
    try:
        server = HTTPServer(('0.0.0.0', 8080), HealthCheckHandler)
        print("✅ Health check server running on port 8080")
        server.serve_forever()
    except Exception as e:
        print(f"❌ Health check server error: {e}")

# Iniciar health check en segundo plano
threading.Thread(target=run_health_server, daemon=True).start()
time.sleep(1)  # Dar tiempo para que inicie

# ======================================================
# APLICACIÓN STREAMLIT
# ======================================================
st.set_page_config(
    page_title="Sistema de Conteo",
    page_icon="📦",
    layout="wide"
)

st.title("📦 Sistema de Conteo de Inventario")
st.markdown("---")

# Mostrar información de debug
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Estado", "✅ Activo")
with col2:
    st.metric("Python", "3.10")
with col3:
    st.metric("Health Check", "✅ OK")

st.markdown("---")
st.success("✅ Aplicación funcionando correctamente en Azure")

# Verificar variables de entorno
st.subheader("🔧 Configuración:")
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

if supabase_url and supabase_key:
    st.success("✅ Variables de Supabase configuradas")
    st.code(f"URL: {supabase_url[:20]}...")
else:
    st.error("❌ Variables de Supabase NO configuradas")