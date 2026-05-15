#!/bin/bash

# Script para iniciar el servidor de desarrollo de Django

echo "🚀 Iniciando servidor de desarrollo para SitioDistriGigante..."

# Verificar si el entorno virtual existe
if [ ! -d "venv" ]; then
    echo "❌ El entorno virtual no existe. Ejecuta primero ./setup_env.sh"
    exit 1
fi

# Activar entorno virtual
echo "🔧 Activando entorno virtual..."
source venv/bin/activate

# Verificar si las dependencias están instaladas
echo "🔍 Verificando dependencias..."
python -c "import django" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Las dependencias no están instaladas. Ejecuta primero ./setup_env.sh"
    exit 1
fi

# Iniciar el servidor de desarrollo
echo "🌐 Iniciando servidor en http://localhost:8000"
echo "📝 Logs del servidor:"
echo "   - Presiona Ctrl+C para detener el servidor"
echo "   - Panel de admin: http://localhost:8000/admin"
echo "   - Usuario: admin / Contraseña: admin123"
echo ""

python manage.py runserver 0.0.0.0:8000
