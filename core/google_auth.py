import requests
from django.shortcuts import redirect
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.conf import settings
from django.urls import reverse
from django.utils.http import urlencode
from django.contrib import messages
from django.db import models
from .models import Perfil
import secrets

def google_login(request):
    """Inicia el flujo de autenticación con Google"""
    # Generar state para seguridad
    state = secrets.token_urlsafe(16)
    request.session['oauth_state'] = state
    
    # Construir URL de autorización
    params = {
        'client_id': settings.GOOGLE_OAUTH2_CLIENT_ID,
        'redirect_uri': settings.GOOGLE_OAUTH2_REDIRECT_URI,
        'scope': ' '.join(settings.GOOGLE_OAUTH2_SCOPES),
        'response_type': 'code',
        'access_type': 'offline',
        'state': state,
        'prompt': 'select_account'
    }
    
    auth_url = f"{settings.GOOGLE_OAUTH2_AUTH_URL}?{urlencode(params)}"
    return redirect(auth_url)

def google_callback(request):
    """Procesa el callback de Google OAuth"""
    # Verificar state
    state = request.GET.get('state')
    if not state or state != request.session.get('oauth_state'):
        messages.error(request, 'Error de autenticación: state inválido')
        return redirect('login')
    
    # Obtener authorization code
    code = request.GET.get('code')
    if not code:
        messages.error(request, 'Error de autenticación: no se recibió código')
        return redirect('login')
    
    # Intercambiar código por token
    try:
        token_data = {
            'client_id': settings.GOOGLE_OAUTH2_CLIENT_ID,
            'client_secret': settings.GOOGLE_OAUTH2_CLIENT_SECRET,
            'code': code,
            'redirect_uri': settings.GOOGLE_OAUTH2_REDIRECT_URI,
            'grant_type': 'authorization_code'
        }
        
        response = requests.post(settings.GOOGLE_OAUTH2_TOKEN_URL, data=token_data)
        response.raise_for_status()
        token_info = response.json()
        access_token = token_info['access_token']
        
    except requests.RequestException as e:
        messages.error(request, f'Error al obtener token: {str(e)}')
        return redirect('login')
    
    # Obtener información del usuario
    try:
        headers = {'Authorization': f'Bearer {access_token}'}
        user_info_response = requests.get(settings.GOOGLE_OAUTH2_USER_INFO_URL, headers=headers)
        user_info_response.raise_for_status()
        user_info = user_info_response.json()
        
    except requests.RequestException as e:
        messages.error(request, f'Error al obtener información del usuario: {str(e)}')
        return redirect('login')
    
    # Procesar información del usuario
    email = user_info.get('email')
    name = user_info.get('name')
    google_id = user_info.get('id')
    
    if not email:
        messages.error(request, 'No se pudo obtener el email del usuario')
        return redirect('login')
    
    # Buscar o crear usuario
    try:
        # Buscar usuario por email o por google_id
        user = User.objects.filter(
            models.Q(email=email) | models.Q(perfil__google_id=google_id)
        ).first()
        
        if user:
            # Usuario existente - actualizar google_id si no tiene
            if not hasattr(user, 'perfil') or not user.perfil.google_id:
                perfil, created = Perfil.objects.get_or_create(user=user)
                perfil.google_id = google_id
                perfil.save()
            
            messages.success(request, f'¡Bienvenido de nuevo {name}!')
            
        else:
            # Crear nuevo usuario
            username = email.split('@')[0]
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{email.split('@')[0]}{counter}"
                counter += 1
            
            # Generar una contraseña aleatoria para usuarios OAuth
            import secrets
            random_password = secrets.token_urlsafe(16)
            
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=name.split()[0] if name else '',
                last_name=' '.join(name.split()[1:]) if name and len(name.split()) > 1 else '',
                password=random_password  # Contraseña generada para usuarios OAuth
            )
            
            # Crear perfil con google_id
            perfil = Perfil.objects.create(
                user=user,
                google_id=google_id,
                tipo_usuario='cliente'
            )
            
            # Marcar que el usuario es de OAuth
            user.perfil.es_oauth = True
            user.perfil.save()
            
            messages.success(request, f'¡Cuenta creada exitosamente para {name}!')
        
        # Iniciar sesión
        login(request, user)
        
        # Limpiar session
        del request.session['oauth_state']
        
        return redirect('index')
        
    except Exception as e:
        messages.error(request, f'Error al procesar usuario: {str(e)}')
        return redirect('login')
