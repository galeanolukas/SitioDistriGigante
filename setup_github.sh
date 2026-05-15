#!/bin/bash

# Script para configurar el repositorio GitHub y subir los archivos

echo "🚀 Configurando repositorio GitHub para SitioDistriGigante..."

# Verificar si estamos en un repositorio git
if [ ! -d ".git" ]; then
    echo "❌ No hay un repositorio git inicializado"
    exit 1
fi

# Mostrar estado actual
echo "📋 Estado actual del repositorio:"
git status

# Agregar archivos nuevos
echo "📝 Agregando archivos nuevos al commit..."
git add README_DEVELOPMENT.md run_server.sh setup_env.sh

# Agregar cambios en requirements.txt
echo "📦 Agregando cambios en requirements.txt..."
git add requirements.txt

# Crear commit
echo "💾 Creando commit con los cambios de desarrollo..."
git commit -m "feat: agregar scripts de configuración y actualizar dependencias

- Agregar setup_env.sh para configurar entorno automático
- Agregar run_server.sh para iniciar servidor fácilmente  
- Actualizar requirements.txt con todas las dependencias necesarias
- Agregar README_DEVELOPMENT.md con guía completa
- Incluir librerías faltantes: django-ckeditor-5, weasyprint, mercadopago, etc."

echo ""
echo "✅ Commit creado exitosamente!"
echo ""
echo "📝 Pasos para subir a GitHub:"
echo "1. Crea el repositorio 'SitioDistriGigante' en github.com"
echo "2. Ejecuta los siguientes comandos:"
echo ""
echo "   # Cambiar el remote al nuevo repositorio:"
echo "   git remote set-url origin https://github.com/galeanolukas/SitioDistriGigante.git"
echo ""
echo "   # Subir al nuevo repositorio:"
echo "   git push -u origin main"
echo ""
echo "   # Si tu rama principal es 'master' en lugar de 'main':"
echo "   git push -u origin master"
echo ""

# Verificar en qué rama estamos
CURRENT_BRANCH=$(git branch --show-current)
echo "🌿 Rama actual: $CURRENT_BRANCH"

# Mostrar los commits pendientes de subir
echo ""
echo "📊 Commits por subir:"
git log --oneline origin/$CURRENT_BRANCH..$CURRENT_BRANCH 2>/dev/null || git log --oneline -3
