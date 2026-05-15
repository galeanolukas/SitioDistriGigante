# SitioDistriGigante - Guía de Desarrollo

## 🚀 Configuración Rápida

### 1. Configurar el entorno
```bash
./setup_env.sh
```

### 2. Iniciar el servidor
```bash
./run_server.sh
```

## 📋 Requisitos Previos

- Python 3.8+
- pip3
- git

## 📦 Dependencias Principales

El proyecto utiliza las siguientes librerías principales:

- **Django 4.2.2** - Framework web
- **Pillow 9.5.0** - Procesamiento de imágenes
- **Google Auth** - Autenticación OAuth2
- **QRCode** - Generación de códigos QR
- **Django CKEditor 5** - Editor de texto enriquecido
- **WeasyPrint** - Generación de PDFs
- **MercadoPago SDK** - Integración de pagos
- **Bootstrap 5** - Framework CSS

## 🗂️ Estructura del Proyecto

```
SitioDistriGigante/
├── core/           # Aplicación principal
├── chatbot/        # Módulo de chatbot
├── config/         # Configuración de Django
├── backup/         # Sistema de respaldos
├── static/         # Archivos estáticos
├── media/          # Archivos multimedia
├── venv/           # Entorno virtual
├── .env            # Variables de entorno
├── requirements.txt # Dependencias Python
├── setup_env.sh    # Script de configuración
└── run_server.sh   # Script para iniciar servidor
```

## 🔧 Configuración

### Variables de Entorno (.env)
- `DEBUG` - Modo de depuración
- `SECRET_KEY` - Clave secreta de Django
- `GOOGLE_OAUTH2_CLIENT_*` - Configuración OAuth2
- `EMAIL_*` - Configuración de email
- `GOOGLE_MAPS_API_KEY` - API Key de Google Maps

### Base de Datos
- **Tipo**: SQLite3 (desarrollo)
- **Archivo**: `db.sqlite3`
- **Migraciones**: Automáticas en setup

## 🚀 Servidor de Desarrollo

- **URL**: http://localhost:8000
- **Panel Admin**: http://localhost:8000/admin
- **Usuario**: admin
- **Contraseña**: admin123

## 📝 Comandos Útiles

```bash
# Activar entorno virtual
source venv/bin/activate

# Crear migraciones
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Recolectar archivos estáticos
python manage.py collectstatic

# Crear superusuario
python manage.py createsuperuser

# Iniciar servidor
python manage.py runserver
```

## 🐛 Depuración

- **DEBUG=True** en settings.py para desarrollo
- Logs detallados en consola
- Error pages personalizadas

## 📚 Documentación Adicional

- [Django Documentation](https://docs.djangoproject.com/)
- [Django CKEditor 5](https://github.com/hvlads/django-ckeditor-5)
- [MercadoPago SDK](https://www.mercadopago.com.ar/developers/es/docs)
