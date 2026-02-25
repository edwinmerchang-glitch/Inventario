#!/bin/bash
echo "==================================="
echo "INICIANDO EN AZURE CON PYTHON 3.10"
echo "==================================="
echo "Fecha: $(date)"
echo "Python version:"
python --version

echo "Instalando dependencias..."
pip install --no-cache-dir -r requirements.txt

echo "Verificando instalación..."
pip list | grep streamlit

echo "Iniciando Streamlit..."
streamlit run app.py \
    --server.port=8000 \
    --server.address=0.0.0.0 \
    --server.enableCORS=true \
    --server.enableXsrfProtection=false \
    --server.maxUploadSize=100