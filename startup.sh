#!/bin/bash
echo "=== Iniciando aplicación en Azure ==="

# Mostrar información del entorno
echo "Directorio actual: $(pwd)"
echo "Python version: $(python --version)"

# Crear directorio temporal si no existe
mkdir -p /tmp

# Instalar dependencias
pip install -r requirements.txt

# Verificar variables de entorno
if [ -z "$SUPABASE_URL" ]; then
    echo "⚠️ SUPABASE_URL no está configurada"
else
    echo "✅ SUPABASE_URL configurada"
fi

if [ -z "$SUPABASE_KEY" ]; then
    echo "⚠️ SUPABASE_KEY no está configurada"
else
    echo "✅ SUPABASE_KEY configurada"
fi

# Iniciar la aplicación
echo "🚀 Iniciando Streamlit..."
streamlit run app.py --server.port 8000 --server.address 0.0.0.0 --server.enableCORS true --server.enableXsrfProtection false