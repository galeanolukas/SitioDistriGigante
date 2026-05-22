import contextlib
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.core.mail import send_mail, EmailMultiAlternatives
from django.core.mail.backends.smtp import EmailBackend
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.db import IntegrityError
from django.contrib.auth.models import Group
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.forms import UserCreationForm
from .forms import UserForm, UserEditForm, PerfilForm, MercadoPagoCuentaForm, ProductForm, CartelForm, SuperuserCreationForm, CargarExcelForm, UbicacionForm, AgregarProductoForm, RegistrationForm
from .subprocesos import CargarPoductosAuto
import locale
import qrcode
import qrcode.image.svg
from io import BytesIO
from weasyprint import HTML, CSS
import base64
import mercadopago
import json
import hmac
import hashlib
from .models import *
from .utils import MPCheckOut

# Import EMAIL_HOST_USER from settings
EMAIL_HOST_USER = settings.EMAIL_HOST_USER

class CuentaMpTest:
    """Clase de prueba para cuenta de MercadoPago cuando no hay cuentas configuradas"""
    def __init__(self):
        self.public_key = "TEST-123456789"
        self.access_token = "TEST-123456789"
        self.nombre = "Cuenta de Prueba"
        self.id = None

locale.setlocale(locale.LC_TIME, '')

def index(request):
    change_info(request)
    # Corregir: ordenar productos por contador de clicks para "más buscados" y limitar a 10
    products = Product.objects.all().order_by("-contador_clicks", "-marca")[:10]
    
    # Obtener productos destacados
    productos_destacados = Product.objects.filter(destacado=True, stock__gt=0).order_by("?")[:8]
    
    # Desactivar automáticamente ofertas expiradas
    Oferta.desactivar_ofertas_expiradas()
    
    # Obtener solo ofertas vigentes
    ofertas = Oferta.objects.filter(activa=True)
    imagenes = CarruselImages.objects.all()
    try:
        cart = Cart.objects.get(user=request.user)
        # Realizar cálculos
        total_carrito = cart.get_total_quantity()
    except:
        total_carrito = 0

    context = {'products': products,
                'productos_destacados': productos_destacados,
                'imagenes':imagenes,
                'ofertas': ofertas,
                'placeholder': "Buscar productos aqui..",
                'search_name': "q",
                'search_action': "/buscar/",
                'total_carrito':total_carrito}

    return render(request, 'index.html', context)

#Contador de clicks y productos en carrito
def registrar_accion(producto, accion):
    """
    Función simple para registrar acciones
    accion: 'click' o 'carrito'
    """
    if accion == 'click':
        producto.contador_clicks += 1
    elif accion == 'carrito':
        producto.contador_carrito += 1

    producto.save()

def buscar_productos(request):
    q = request.GET.get('q')
    
    # Cargar categorías para el sidebar
    categorias = {}
    categorys = MainCategory.objects.all()
    
    if categorys.count() > 0:
        for item in categorys:
            categorias[item] = []
            for subitem in Category.objects.all().filter(main__nombre=item.nombre):
                categorias[item].append(subitem)
    
    if q:
        # Realizar la búsqueda y obtener los resultados
        resultados = Product.objects.filter(nombre__icontains=q).order_by('id')
        paginator = Paginator(resultados, 6)  # Mostrar 6 productos por página

        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'resultados': page_obj, 
            'q': q,
            'categorias': categorias,
            'categorys': categorys,
            'catalogo': True  # Para mostrar el sidebar de categorías
        }
        return render(request, 'buscar.html', context)

    else:
        resultados = []
    context = {
        'resultados': resultados, 
        'q': q,
        'categorias': categorias,
        'categorys': categorys,
        'catalogo': True  # Para mostrar el sidebar de categorías
    }
    return render(request, 'buscar.html', context)

##################################################################
def productos_orden(request):
    if request.method == "GET":
        random_product = request.session.get("random_catalogo")
        print(random_product)
        if request.session.get("random_catalogo") == "random":
            request.session["random_catalogo"] = None
        else:
            request.session["random_catalogo"] = "random"
    else:
        pass

    return redirect("catalogo")

def cambiar_orden_catalogo(request):
    if request.method == 'POST':
        campo_orden = request.POST.get('campo_orden')

        if campo_orden:
            # Crear o actualizar la configuración
            orden_config, created = OrdenCatalogo.objects.get_or_create(
                campo_orden=campo_orden,
                defaults={'activo': True}
            )

            if not created:
                orden_config.activo = True
                orden_config.save()

            messages.success(request, f'Ordenamiento cambiado a: {orden_config.get_campo_orden_display()}')
        else:
            messages.error(request, 'Selecciona una opción válida')

        return redirect('product_panel')  # Ajusta el nombre de tu URL

def pedi_preventista(request):
    if request.user:
        form = UbicacionForm()
    else:
        form = UbicacionForm(initial={"nombre":user.perfil.nombre})

    if request.method == "POST":
        form = UbicacionForm(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.save()
            messages.success(request, "Exito!!! Solicitud de preventista enviada...")
            return redirect("/")

    context = {'form':form}
    return render(request, 'preventista.html', context)

def obtener_orden_configurado():
    """
    Obtiene el campo de ordenamiento configurado desde la base de datos
    """
    try:
        orden_config = OrdenCatalogo.objects.get(activo=True)
        return orden_config.campo_orden
    except OrdenCatalogo.DoesNotExist:
        # Si no hay configuración, crear una por defecto
        orden_config = OrdenCatalogo.objects.create(
            campo_orden='categoria',
            activo=True
        )
        return orden_config.campo_orden
    except OrdenCatalogo.MultipleObjectsReturned:
        # Si hay múltiples activos, usar el primero y desactivar los demás
        primero = OrdenCatalogo.objects.filter(activo=True).first()
        OrdenCatalogo.objects.filter(activo=True).exclude(id=primero.id).update(activo=False)
        return primero.campo_orden

def catalogo(request, tp=None):
    products = []
    categorias = {}
    categorys = MainCategory.objects.all()
    catalogo = True

    try:
        cart = Cart.objects.get(user=request.user)
        total_carrito = cart.get_total_quantity()
    except:
        total_carrito = 0

    if request.get_host() == "localhost:8000":
        host = "http://" + request.get_host()
    else:
        host = "https://" + request.get_host()

    # Obtener el orden configurado
    orden = obtener_orden_configurado()

    if categorys.count() > 0:
        for item in categorys:
            categorias[item] = []
            for subitem in Category.objects.all().filter(main__nombre=item.nombre):
                categorias[item].append(subitem)

    if tp:
        if tp == "ofertas":
            # Para ofertas, obtener productos y luego ordenarlos
            ofertas = Oferta.objects.all().select_related('producto')
            products_list = [p.producto for p in ofertas]

            # Aplicar ordenamiento manual a la lista
            if orden.startswith('-'):
                reverse = True
                campo = orden[1:]
            else:
                reverse = False
                campo = orden

            # Función para obtener el valor de ordenamiento
            def get_sort_key(product):
                if campo == 'categoria':
                    return getattr(product.categoria, 'nombre', '') if product.categoria else ''
                elif campo == 'marca':
                    return getattr(product, 'marca', '')
                elif campo == 'nombre':
                    return getattr(product, 'nombre', '')
                elif campo == 'precio':
                    return getattr(product, 'precio', 0)
                elif campo == 'id':
                    return getattr(product, 'id', 0)
                return ''

            products = sorted(products_list, key=get_sort_key, reverse=reverse)

        else:
            # Para categoría específica, usar order_by de QuerySet
            products = Product.objects.filter(categoria__nombre=tp).order_by(orden)
    else:
        # Para todos los productos, usar order_by de QuerySet
        products = Product.objects.all().order_by(orden)

    paginator = Paginator(products, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'products': page_obj,
        'categorys': categorys,
        'categorias': categorias,
        'catalogo': True,
        'tp': tp,
        'host_link': host,
        'total_carrito': total_carrito,
        'orden_actual': orden,
    }
    return render(request, 'catalogo.html', context)


def login_view(request):
    # Obtener la URL de la página anterior o la actual
    next_page = request.GET.get('next')
    error = None
    if not next_page:
        # Si no hay 'next', usar HTTP_REFERER o la página por defecto
        next_page = request.META.get('HTTP_REFERER', reverse('index'))

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            # Redirigir a la página que estaba intentando acceder
            pass
        else:
            # Pasar el 'next' al template para mantenerlo en el formulario
            error = "Usuario o contraseña invalidos!.."
            messages.error(request, f"No se pudo ingresar: {error}")

    # Pasar el 'next' al template para el formulario GET
    return redirect(next_page)

def logout_view(request):
    logout(request)
    return redirect('index')

def register(request, reset_id=None):
    reset_pass = request.session.get('reset_pass')
    host = request.get_host()
    # Ejemplo: "localhost:8000" o "midominio.com"

    # Obtener solo el nombre del host (sin puerto)
    host_name = request.META.get('HTTP_HOST').split(':')[0]
    # Ejemplo: "localhost" o "midominio.com"

    # Obtener el esquema (http o https)
    scheme = request.scheme
    # Ejemplo: "http" o "https"

    # Construir la URL base completa
    base_url = f"{scheme}://{host}"

    if reset_pass:
        if reset_id:
            instance = User.objects.get(id=reset_id)
        else:
             request.session.pop('reset_pass')
    else:
        instance = None

    if request.method == 'POST':
        # Manejar peticiones AJAX para el modal
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if reset_pass:
                if request.POST.get("password") == request.POST.get("confirm_password"):
                    instance.active = True
                    instance.password = request.POST.get("password")
                    instance.save()
                    request.session.pop('reset_pass')
                    messages.success(request, "Exito!!! Recuperaste tu cuenta...")
                    login(request, instance)
                    return JsonResponse({'success': True, 'message': 'Cuenta recuperada exitosamente', 'redirect': '/'})
                else:
                    return JsonResponse({'success': False, 'message': 'Las contraseñas ingresadas no coinciden!'})
            else:
                form = RegistrationForm(request.POST)
                if form.is_valid():
                    instance = form.save()
                    instance.active = False
                    # Genera el código de validación una vez
                    validation_code = get_random_string(length=6).upper()
                    print("Código generado:", validation_code)

                    # Almacena el código de validación en la sesión
                    request.session["validation_code"] = validation_code
                    print("Código almacenado en la sesión:", request.session["validation_code"])

                    # Construye el enlace de validación
                    validation_link = reverse('validate_code', kwargs={'ID': instance.id})
                    validation_link = f'{base_url}{validation_link}?code={validation_code}'

                    # Renderiza la plantilla de correo
                    response_html = render_to_string('email_verification.html', {
                        'username': instance.username.upper(),
                        'validation_code': validation_code,
                        'validation_link': validation_link,
                    })

                    try:
                        # Envía el correo electrónico
                        mail = EmailMultiAlternatives("DISTRIBUIDORA GIGANTE", response_html, EMAIL_HOST_USER, [instance.email])
                        mail.attach_alternative(response_html, "text/html")
                        mail.send()

                        # Guarda el usuario
                        instance.save()
                        messages.success(request, "Exito!!! Revisa tu correo electrónico para completar tu registro.")
                        return JsonResponse({'success': True, 'message': 'Registro exitoso. Revisa tu correo para validar.', 'redirect': f'/registro/validar/{instance.id}/'})

                    except BadHeaderError:
                        instance.delete()
                        messages.error(request, "Fallo!! No se pudo enviar un correo a la dirección ingresada.")
                        return JsonResponse({'success': False, 'message': 'No se pudo enviar el correo de verificación.'})
                else:
                    # Devolver errores de formulario
                    errors = {}
                    for field, error_list in form.errors.items():
                        errors[field] = error_list[0]
                    return JsonResponse({'success': False, 'errors': errors})
        else:
            # Comportamiento original para peticiones no AJAX
            if reset_pass:
                if request.POST.get("password") == request.POST.get("confirm_password"):
                    instance.active = True
                    instance.password = request.POST.get("password")
                    instance.save()
                    request.session.pop('reset_pass')
                    messages.success(request, "Exito!!! Recuperaste tu cuenta...")
                    login(request, instance)
                    return redirect("/")
                else:
                    messages.error(request, "Las contraseñas ingresadas no coinciden!")
                    return redirect("reset_register", reset_id=reset_id)
            else:
                form = RegistrationForm(request.POST)
                if form.is_valid():
                    instance = form.save()
                    instance.active = False
                    validation_code = get_random_string(length=6).upper()
                    request.session["validation_code"] = validation_code
                    validation_link = reverse('validate_code', kwargs={'ID': instance.id})
                    validation_link = f'{base_url}{validation_link}?code={validation_code}'
                    response_html = render_to_string('email_verification.html', {
                        'username': instance.username.upper(),
                        'validation_code': validation_code,
                        'validation_link': validation_link,
                    })
                    try:
                        mail = EmailMultiAlternatives("DISTRIBUIDORA GIGANTE", response_html, EMAIL_HOST_USER, [instance.email])
                        mail.attach_alternative(response_html, "text/html")
                        mail.send()
                        instance.save()
                        messages.success(request, "Exito!!! Revisa tu correo electrónico para completar tu registro.")
                        return redirect('validate_code', ID=instance.id)
                    except BadHeaderError:
                        instance.delete()
                        messages.error(request, "Fallo!! No se pudo enviar un correo a la dirección ingresada.")

    # Para peticiones GET, redirigir al home con el modal de registro abierto
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return redirect(f"/?showRegisterModal=true")
    
    # Respuesta por defecto para AJAX
    return JsonResponse({'success': False, 'message': 'Método no permitido'})

def validar_registro(request, ID=None):
    print("ID recibido en la vista:", ID)
    user = get_object_or_404(User, id=ID)
    print("Usuario encontrado en la base de datos:", user)
    validation_code = request.session.get("validation_code")
    if ID:
        email_validate_code = request.GET.get('code')

    error_message = None

    if request.method == "POST":
        validate_code = request.POST.get('vcode')
        # Asegúrate de que el código de validación se está generando correctamente
        print("validate_code recibido:", validate_code)
        print("session_validation_code:", )

        if validate_code == validation_code:
            if request.session.get('reset_pass'):
                request.session.pop("validation_code")
                # Redirige al usuario a la página principal o a donde desees
                messages.success(request, "Exito!!! Validación correcta!!!")
                return redirect('reset_register', reset_id=ID)

            else:
                user.is_active = True
                user.save()
                request.session.pop("validation_code")
                login(request, user)
                messages.success(request, "Exito!!! Validación correcta!!!")
                return redirect('confirm_register', ID=ID)

        else:
            error_message = ":( Error!!! Codigo de validación incorrecto!!"
            messages.error(request, error_message)
            return redirect('validate_code', ID=ID)

    else:
        if validation_code:
            context = {'error_message': error_message, 'ID':ID, "email_validate_code":email_validate_code}
            return render(request, 'validate_code.html', context)
        else:
            return redirect('register')

@login_required
def confirm_register(request, ID=None):
    # Obtén el usuario relacionado o lanza un error 404
    registro = get_object_or_404(User, id=ID)

    # Validar permisos: solo puede editar su propio perfil, excepto admin/vendedor
    perfil_usuario = Perfil.objects.get(user=request.user)
    es_admin_o_vendedor = (request.user.is_staff or 
                          request.user.is_superuser or 
                          perfil_usuario.tipo_usuario in ['admin', 'vendedor'] or
                          request.user.groups.filter(name__in=['admin', 'vendedor']).exists())
    
    # Si no es admin/vendedor y no es su propio perfil, denegar acceso
    if not es_admin_o_vendedor and request.user.id != ID:
        messages.error(request, "No tienes permiso para acceder a este perfil.")
        return redirect('carrito')

    # Obtén el perfil existente
    perfil_existente = Perfil.objects.get(user=registro)

    # Determinar dónde redirigir después de guardar
    redirect_to = request.GET.get('redirect_to', None)

    if request.method == 'POST':
        # Obtén la acción seleccionada (confirm_now o confirm_later)
        action = request.POST.get('action')

        # Crea el formulario con los datos enviados
        form = PerfilForm(request.POST, request.FILES or None, instance=perfil_existente)

        if action == 'confirm_now':
            if form.is_valid():
                # Guarda los cambios del formulario
                instance = form.save(commit=False)
                # Actualizar también el first_name del usuario si está en el formulario
                if 'nombre' in form.cleaned_data and form.cleaned_data["nombre"]:
                    registro.first_name = form.cleaned_data["nombre"]
                    registro.save()
                instance.save()

                messages.success(request, "¡Perfil actualizado correctamente!")

                # Redirigir según el parámetro redirect_to
                if redirect_to == 'carrito':
                    return redirect('carrito')
                else:
                    return redirect('registro_actualizado', perfil_id=perfil_existente.id)
            else:
                messages.error(request, "Por favor, corrija los errores en el formulario.")

        elif action == 'confirm_later':
            messages.info(request, "Puede completar su perfil más tarde.")
            # Redirigir según el parámetro redirect_to
            if redirect_to == 'carrito':
                return redirect('carrito')
            else:
                return redirect('/')

    else:
        # Crea un formulario vacío o inicializado con datos existentes
        form = PerfilForm(instance=perfil_existente)
        # Establecer el valor inicial del campo nombre desde first_name
        if not perfil_existente.nombre and registro.first_name:
            form.initial['nombre'] = registro.first_name

    # Prepara el contexto para el template
    context = {
        "form": form,
        "perfil_existente": perfil_existente,
        "usuario": registro,
        "redirect_to": redirect_to,
    }
    return render(request, 'valida_perfil.html', context)


def recuperar_pass(request):
    instance = None
    if request.method == "POST":
        try:
            instance = User.objects.get(email=request.POST.get("email"))
            # Genera el código de validación una vez
            validation_code = get_random_string(length=6).upper()
            print("Código generado:", validation_code)

            # Almacena el código de validación en la sesión
            request.session["validation_code"] = validation_code
            print("Código almacenado en la sesión:", request.session["validation_code"])

            # Construye el enlace de validación
            validation_link = reverse('validate_code', kwargs={'ID': instance.id})
            validation_link += f'?code={validation_code}'

            # Construye el cuerpo del correo electrónico
            response_html = f"""<h1>HOLA {instance.username.upper()}!</h1>
                                        <p>Te olvidaste tu password, Recupera tu contraseña</p>
                                        <p>Ingresa el siguiente código <h3>{validation_code}</h3> o haz clic en el enlace para cambiar tu contraseña:</p>
                                        <a href="{request.build_absolute_uri(validation_link)}"><button>Cambiar Contraseña</button></a>
                                        <p><h2>Saludos!!!</h2></p>"""


                # Envía el correo electrónico
            try:
                mail = EmailMultiAlternatives("DISTRIBUIDORA GIGANTE", response_html, EMAIL_HOST_USER, [instance.email])
                mail.attach_alternative(response_html, "text/html")
                mail.send()

                # Guarda el usuario y realiza la redirección
                messages.success(request, "Exito!!! Revisa tu correo electrónico para seguir.")
                # Redirige directamente a la vista validate_code
                request.session["reset_pass"] = True
                return redirect('validate_code', ID=instance.id)

            except BadHeaderError:
                request.session.pop("validation_code")
                messages.error(request, "Fallo!! correo ingresado invalido o no existe.")


        except:
            messages.error(request, "Fallo!! No se pudo verificar correo ingresado.")
            pass

    return render(request, 'reset_pass.html')

def registro_actualizado(request, perfil_id=None):
    perfil = get_object_or_404(Perfil, id=perfil_id)

    context = {"perfil": perfil}
    return render(request, 'registro_actualizado.html', context)

@login_required
def admin_panel(request):
    usuarios = User.objects.all()
    mensajes = Contacto.objects.all()
    mensaje_ultimo = Contacto.objects.last()
    cont_visitas_hoy = DayNumber.objects.last()
    if mensaje_ultimo:
        mensaje_ultimo = mensaje_ultimo.fecha

    cont_visitas = VisitNumber.objects.all()[0]
    
    # Determinar tipo de usuario
    es_vendedor = request.user.groups.filter(name='vendedor').exists() or (Perfil.objects.filter(user=request.user).first() and Perfil.objects.filter(user=request.user).first().tipo_usuario == 'vendedor')
    es_administrador = request.user.is_staff or request.user.is_superuser
    
    # Filtrar pedidos según el tipo de usuario
    if es_vendedor:
        # Para vendedores: solo sus pedidos
        pedidos = Pedido.objects.filter(vendedor=request.user)
    else:
        # Para administradores y otros: todos los pedidos
        pedidos = Pedido.objects.all()
    
    # Calcular clientes sin vendedor asignado
    clientes_perfil = Perfil.objects.filter(tipo_usuario='cliente')
    clientes_con_vendedor = ClienteVendedor.objects.all().values_list('cliente_id', flat=True)
    clientes_sin_vendedor = clientes_perfil.exclude(id__in=clientes_con_vendedor).count()
    
    # Calcular clientes relacionados con el vendedor logueado
    mis_clientes_count = 0
    if es_vendedor:
        # Obtener el perfil del vendedor actual
        perfil_vendedor = Perfil.objects.filter(user=request.user).first()
        if perfil_vendedor:
            mis_clientes_count = ClienteVendedor.objects.filter(vendedor=perfil_vendedor).count()
    
    context = {"total_usuarios":usuarios.count(),
               "total_clientes":usuarios.filter(groups__name='cliente').count,
               "total_mensajes":mensajes.count(),
               "total_vendedores":usuarios.filter(groups__name='vendedor').count,
               "mensaje_ultimo":mensaje_ultimo,
               'total_visitas':cont_visitas,
               'total_visitas_hoy':cont_visitas_hoy.count,
               'pedidos':pedidos.count(),
               'clientes_sin_vendedor': clientes_sin_vendedor,
               'mis_clientes_count': mis_clientes_count,
               'notificaciones_no_leidas': NotificacionAdmin.contar_no_leidas()}

    return render(request, 'admin_panel.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def user_panel(request):
    users = User.objects.all().select_related('perfil').prefetch_related('groups')
    # Obtener todos los grupos disponibles
    groups = Group.objects.all()

    # Búsqueda
    busqueda_query = request.GET.get('user')
    if busqueda_query:
        users = users.filter(
            Q(username__icontains=busqueda_query) |
            Q(email__icontains=busqueda_query) |
            Q(first_name__icontains=busqueda_query) |
            Q(last_name__icontains=busqueda_query)
        )

    # Paginación
    paginator = Paginator(users, 6)  # 10 usuarios por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Formulario
    form = UserForm()
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario creado con éxito!")
            return redirect('user_panel')

    context = {
        'form': form,
        'users': page_obj,
        'search_name': "user",
        'placeholder': "Buscar Usuario...",
        'search_action': '/panel_usuario',
        'groups': groups,
    }
    return render(request, 'user_panel.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def product_panel(request):
    search_query = request.GET.get('p', '')
    products = Product.objects.all()

    if search_query:
        products = products.filter(nombre__icontains=search_query)

    try:
        orden_config = OrdenCatalogo.objects.get(activo=True)
        orden = orden_config.campo_orden

    except OrdenCatalogo.DoesNotExist:
        orden = 'categoria'  # Valor por defecto

    paginator = Paginator(products, 6)  # 10 productos por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    form = ProductForm()
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('product_panel')

    context = {
        'search_name': 'p',
        'placeholder': 'Buscar Producto...',
        'search_action': '/admin_panel/productos/',
        'product_list': page_obj,  # Cambiar a 'page_obj'
        'form': form,
        'orden_actual': orden_config if 'orden_config' in locals() else None,
        'opciones_orden': OrdenCatalogo.OPCIONES_ORDEN,
    }
    return render(request, 'product_panel.html', context)


@login_required
def detalle_pedido(request, pedido_id):
    perfil = Perfil(user=request.user)
    if request.user.is_superuser:
        # Si es superusuario o miembro del personal, permite ver todos los pedidos
        pedido = get_object_or_404(Pedido, id=pedido_id)
    elif request.user.groups.filter(name__in=['vendedor']).exists():
        # Si es vendedor, permite ver los pedidos asignados a él
        pedido = get_object_or_404(Pedido, id=pedido_id, vendedor=request.user)
    else:
        # Si es un cliente regular, solo permite ver sus propios pedidos
        pedido = get_object_or_404(Pedido, id=pedido_id, user=request.user)

    detalles_pedido = DetallePedido.objects.filter(pedido=pedido)
    
    # Calcular subtotal de productos (sin costo de envío)
    subtotal_productos = sum(detalle.subtotal for detalle in detalles_pedido)
    
    # Calcular total con envío
    total_con_envio = subtotal_productos + pedido.costo_envio

    context = {
        'pedido': pedido,
        'detalles_pedido': detalles_pedido,
        'perfil': perfil,
        'subtotal_productos': subtotal_productos,
        'total_con_envio': total_con_envio,
    }

    return render(request, 'detalle_pedido.html', context)


@login_required
def pedidos_panel(request):
    # Obtener pedidos según el tipo de usuario
    if request.user.is_superuser or request.user.groups.filter(name__in=['admin']).exists():
        pedidos_list = Pedido.objects.all()
        
        # Obtener listas de vendedores y clientes únicos
        from django.db.models import Count
        vendedores = User.objects.filter(
            groups__name='vendedor',
            pedido__isnull=False
        ).annotate(
            pedido_count=Count('pedido')
        ).distinct().order_by('username')
        
        clientes = User.objects.filter(
            pedido__isnull=False
        ).exclude(
            groups__name__in=['admin', 'vendedor']
        ).annotate(
            pedido_count=Count('pedido')
        ).distinct().order_by('username')
        
    elif request.user.groups.filter(name__in=['vendedor']).exists():
        # Para vendedores: mostrar pedidos donde están asignados como vendedor
        pedidos_list = Pedido.objects.filter(vendedor=request.user)
        vendedores = User.objects.filter(groups__name='vendedor').distinct().order_by('username')
        clientes = User.objects.filter(pedido__isnull=False).exclude(
            groups__name__in=['admin', 'vendedor']
        ).distinct().order_by('username')
    else:
        pedidos_list = Pedido.objects.filter(user=request.user)
        vendedores = User.objects.filter(groups__name='vendedor').distinct().order_by('username')
        clientes = User.objects.filter(pedido__isnull=False).exclude(
            groups__name__in=['admin', 'vendedor']
        ).distinct().order_by('username')
    
    # Guardar la lista completa para estadísticas
    pedidos_completos = pedidos_list

    # Aplicar filtro de estado si existe
    estado_filter = request.GET.get('estado')
    if estado_filter:
        pedidos_list = pedidos_list.filter(estado=estado_filter)
    
    # Aplicar filtros de vendedor y cliente si existen
    vendedor_filter = request.GET.get('vendedor')
    cliente_filter = request.GET.get('cliente')
    
    if vendedor_filter:
        pedidos_list = pedidos_list.filter(user__username=vendedor_filter)
    
    if cliente_filter:
        pedidos_list = pedidos_list.filter(user__username=cliente_filter)
    
    # Ordenamiento con prioridad: pendientes primero, luego pagados, luego por fecha
    from django.db.models import Case, When, Value, IntegerField
    pedidos_list = pedidos_list.annotate(
        prioridad=Case(
            When(estado='pendiente', then=Value(1)),
            When(estado='pagado', then=Value(2)),
            When(estado='procesando', then=Value(3)),
            When(estado='entregado', then=Value(4)),
            When(estado='cancelado', then=Value(5)),
            default=Value(6),
            output_field=IntegerField()
        )
    ).order_by('prioridad', '-fecha_pedido')

    # Configurar paginación
    paginator = Paginator(pedidos_list, 10)  # 10 pedidos por página
    page = request.GET.get('page')

    try:
        pedidos = paginator.page(page)
    except PageNotAnInteger:
        # Si la página no es un entero, mostrar la primera página
        pedidos = paginator.page(1)
    except EmptyPage:
        # Si la página está fuera de rango, mostrar la última página
        pedidos = paginator.page(paginator.num_pages)

    # Estadísticas calculadas sobre la lista completa de pedidos
    pedidos_entregados = pedidos_completos.filter(estado='entregado').count()
    pedidos_pendientes = pedidos_completos.filter(estado='pendiente').count()
    pedidos_pagados = pedidos_completos.filter(estado='pagado').count()

    context = {
        'pedidos_panel': pedidos,
        'pedidos_entregados': pedidos_entregados,
        'pedidos_pendientes': pedidos_pendientes,
        'pedidos_pagados': pedidos_pagados,
        'total_pedidos': pedidos_completos.count(),
        'estado_actual': estado_filter or '',
        'vendedor_actual': vendedor_filter or '',
        'cliente_actual': cliente_filter or '',
        'vendedores': vendedores,
        'clientes': clientes
    }

    return render(request, 'pedidos_panel.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def cambiar_estado_pedido(request, pedido_id):

    pedido = get_object_or_404(Pedido, id=pedido_id)
    # Lógica para cambiar el estado del pedido según tus necesidades
    pedido.estado = 'Entregado'  # Cambiar a tu lógica específica
    pedido.save()

    return redirect('pedidos_panel')

@login_required
@user_passes_test(lambda u: u.is_staff)
def modificar_pedido(request, pedido_id):

    pedido = get_object_or_404(Pedido, id=pedido_id)
    cart = Cart.objects.get_or_create(user=request.user)[0]
    productos_catalogo = Product.objects.all()
    detalles_pedido = DetallePedido.objects.filter(pedido=pedido)

    if request.method == 'POST':
        eliminar_producto_id = request.POST.get('eliminar_producto_id')
        if eliminar_producto_id:
            detalle_a_eliminar = get_object_or_404(DetallePedido, id=eliminar_producto_id)
            detalle_a_eliminar.delete()
            pedido.actualizar_pedido()
            messages.error(request, f"El producto ha sido eliminado con éxito!!! Precio Actualizado: ${pedido.total_precio}")
            return redirect('modificar_pedido', pedido_id=pedido.id)

        form = AgregarProductoForm(request.POST)
        if form.is_valid():
            producto_id = form.cleaned_data['nuevo_producto']
            cantidad = form.cleaned_data['nueva_cantidad_nuevo']
            producto = get_object_or_404(Product, id=producto_id)
            subtotal = producto.precio * cantidad

            DetallePedido.objects.create(
                pedido=pedido,
                producto=producto,
                cantidad=cantidad,
                subtotal=subtotal
            )
            messages.success(request, f"El producto ha sido agregado con éxito!!! Precio Actualizado: ${pedido.total_precio}")
            return redirect('modificar_pedido', pedido_id=pedido.id)

    context = {
        'pedido': pedido,
        'cart': cart,
        'detalles_pedido': detalles_pedido,
        'productos_catalogo': productos_catalogo,
    }

    return render(request, 'modificar_pedido.html', context)

# Vista para agregar un nuevo producto al pedido
def agregar_producto(request, pedido_id):

    pedido = get_object_or_404(Pedido, id=pedido_id)
    productos_catalogo = Product.objects.all()

    if request.method == 'POST':
        form = AgregarProductoForm(request.POST)
        if form.is_valid():
            producto_id = form.cleaned_data['nuevo_producto']
            cantidad = form.cleaned_data['nueva_cantidad_nuevo']
            producto = get_object_or_404(Product, id=producto_id)
            subtotal = producto.precio * cantidad

            DetallePedido.objects.create(
                pedido=pedido,
                producto=producto,
                cantidad=cantidad,
                subtotal=subtotal
            )
            pedido.actualizar_pedido()
            return redirect('modificar_pedido', pedido_id=pedido.id)

    else:
        form = AgregarProductoForm()

    context = {
        'pedido': pedido,
        'form': form,
        'productos_catalogo': productos_catalogo,
    }

    return render(request, 'agregar_producto.html', context)

@login_required
def eliminar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    pedido.delete()
    messages.error(request, "Se ha eliminado el Pedido!")
    return redirect('pedidos_panel')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def limpiar_precios(request):
    productos = Product.objects.all()
    for producto in productos:
        producto.precio_m = 0
        producto.precio = 0
        producto.save()

    messages.info(request, "Se limpiaron los todos los Precios!")
    return redirect('product_panel')

@login_required
def carrito(request):
    cart = Cart.objects.get_or_create(user=request.user)[0]

    # Realizar cálculos
    total_quantity = cart.get_total_quantity()
    total_price = calculate_total_price(cart)
    shipping_cost = 5000
    discount = 0
    discounted_total = total_price + shipping_cost - discount
    boton_mp = None

    # Obtener perfil del usuario actual
    perfil, created = Perfil.objects.get_or_create(user=request.user)

    # Verificar si el perfil está completo (según los campos requeridos)
    perfil_completo = all([
        perfil.nombre,
        perfil.direccion,
        perfil.telefono,
        perfil.localidad
    ])

    # Determinar tipo de usuario basado en el perfil y grupos (más robusto)
    es_cliente = perfil.tipo_usuario == 'cliente' or request.user.groups.filter(name='cliente').exists()
    es_vendedor = perfil.tipo_usuario == 'vendedor' or request.user.groups.filter(name='vendedor').exists()
    es_administrador = perfil.tipo_usuario == 'admin' or request.user.is_staff or request.user.is_superuser

    # Debug logs para verificar detección de usuario
    print(f"DEBUG: Usuario: {request.user.username}")
    print(f"DEBUG: Perfil tipo_usuario: {perfil.tipo_usuario}")
    print(f"DEBUG: es_cliente: {es_cliente}")
    print(f"DEBUG: es_vendedor: {es_vendedor}")
    print(f"DEBUG: es_administrador: {es_administrador}")

    # Obtener lista de clientes para vendedores/administradores
    clientes = None
    if es_vendedor:
        # Para vendedores: solo sus clientes asignados a través de ClienteVendedor
        # Obtener el perfil del vendedor actual
        perfil_vendedor = Perfil.objects.get(user=request.user)
        clientes_ids = ClienteVendedor.objects.filter(
            vendedor=perfil_vendedor
        ).values_list('cliente_id', flat=True)
        
        print(f"DEBUG: IDs de clientes asignados al vendedor: {list(clientes_ids)}")
        
        clientes = Perfil.objects.filter(
            id__in=clientes_ids,
            tipo_usuario='cliente',
            user__is_active=True
        ).select_related('user').exclude(user=request.user)
        
        print(f"DEBUG: Número de clientes filtrados: {clientes.count()}")
    elif es_administrador:
        # Para administradores: todos los clientes
        clientes = Perfil.objects.filter(
            tipo_usuario='cliente',
            user__is_active=True
        ).select_related('user').exclude(user=request.user)
        
        print(f"DEBUG: Número total de clientes (admin): {clientes.count()}")

    # Asignar vendedor por defecto para clientes
    vendedor = None
    if es_cliente:
        # Usar el vendedor asignado o buscar uno por defecto
        vendedor = perfil.vendedor_asignado or User.objects.filter(
            perfil__tipo_usuario='vendedor'
        ).first()

    if request.method == 'POST':
        if total_quantity != 0:
            if 'crear_pedido' in request.POST:
                # Para vendedores/administradores: obtener cliente seleccionado
                cliente_id = request.POST.get('cliente_id')
                if es_vendedor or es_administrador:
                    if not cliente_id:
                        messages.error(request, "Debe seleccionar un cliente para el pedido.")
                        return redirect('carrito')

                    try:
                        cliente = User.objects.get(id=cliente_id, perfil__tipo_usuario='cliente')
                        usuario_pedido = cliente
                        # Usar el vendedor que está haciendo el pedido
                        vendedor_pedido = request.user
                    except User.DoesNotExist:
                        messages.error(request, "Cliente seleccionado no válido.")
                        return redirect('carrito')
                else:
                    # Para clientes: verificar perfil completo
                    if not perfil_completo:
                        messages.error(request, "Debe completar su perfil antes de realizar el pedido.")
                        return redirect('carrito')
                    usuario_pedido = request.user
                    vendedor_pedido = vendedor

                with transaction.atomic():
                    # Crear nuevo pedido
                    pedido = Pedido.objects.create(
                        user=usuario_pedido,
                        estado='pendiente',
                        vendedor=vendedor_pedido
                    )

                    # Agregar items al pedido
                    for item in cart.cartitem_set.all():
                        DetallePedido.objects.create(
                            pedido=pedido,
                            producto=item.product,
                            cantidad=item.quantity,
                            subtotal=item.subtotal
                        )

                    # Actualizar y limpiar
                    pedido.actualizar_pedido()
                    cart.products.clear()

                    messages.success(request, "¡Pedido registrado exitosamente!")

                    # Redirigir según el tipo de usuario
                    if es_vendedor or es_administrador:
                        return redirect('pedidos_panel')
                    else:
                        # Para clientes, redirigir a confirmación o pago
                        return redirect('procesar_pago', pedido_id=pedido.id)

    context = {
        'cart': cart,
        'total_quantity': total_quantity,
        'total_price': total_price,
        'shipping_cost': shipping_cost,
        'discount': discount,
        'discounted_total': discounted_total,
        'total_carrito': total_quantity,
        'perfil_completo': perfil_completo,
        'perfil': perfil,
        'es_cliente': es_cliente,
        'es_vendedor': es_vendedor,
        'es_administrador': es_administrador,
        'clientes': clientes,
        'vendedor': vendedor,
    }

    return render(request, 'carrito.html', context)

def calculate_total_price(cart):
    total_price = 0
    for item in cart.cartitem_set.all():
        total_price += item.subtotal
    return total_price

@login_required
@require_POST
def agregar_al_carrito(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = Cart.objects.get_or_create(user=request.user)[0]
    cart_item, item_created = CartItem.objects.get_or_create(cart=cart, product=product)

    precio_final = 0

    # Si el artículo ya está en el carrito, aumenta la cantidad
    if not item_created:
        cart_item.quantity += 1
    else:
        cart_item.quantity = 1

    # Actualiza el subtotal
    try:
        oferta = get_object_or_404(Oferta, producto__id=product.id)
        
        # Verificar stock disponible de la oferta
        if not oferta.tiene_stock_disponible():
            messages.error(request, "<h5>¡La oferta ha agotado su stock!</h5>")
            return redirect('/catalogo')
        
        precio_final = oferta.precio_final
        
        # Incrementar venta de la oferta
        oferta.incrementar_venta(1)
        
    except:
        precio_final = product.precio

    cart_item.subtotal = cart_item.quantity * precio_final

    cart_item.save()

    registrar_accion(product, "carrito")
    messages.success(request, "<h5>Se agregó {} al carrito!</h5>".format(product.nombre))
    return redirect('/catalogo')

@login_required
def modificar_cantidad(request, cart_item_id):
    cart_item = get_object_or_404(CartItem, id=cart_item_id)
    cantidad = int(request.POST.get('cantidad', 1))

    if cantidad < 1:
        # Si la cantidad es menor a 1, se establece en 1 como mínimo
        cantidad = 1

    cart_item.quantity = cantidad
    try:
        oferta = get_object_or_404(Oferta, producto__id=cart_item.product.id)
        cart_item.subtotal = cart_item.quantity * oferta.precio_final
    except:
        cart_item.subtotal = cart_item.quantity * cart_item.product.precio

    cart_item.save()

    return redirect('carrito')

@login_required
def pago_online(request):
    host = None
    carrito = Cart.objects.get(user=request.user)[0]
    total_precio = calculate_total_price(carrito)

    # Cargo la cuenta a utilzar de MP
    if MercadoPagoCuenta.objects.first():
        cuenta_mp = MercadoPagoCuenta.objects.first()
    else:
        cuenta_mp = CuentaMpTest()

    if request.get_host() == "localhost:8000":
        host = "http://" + request.get_host()
    else:
        host = "https://" + request.get_host()

    if request.method == "POST":
        return redirect('/')

    return redirect('/')

def enviar_email_confirmacion_compra(pedido, estado_pago):
    """Envía email de confirmación de compra al cliente con QR del envío"""
    try:
        # Obtener email del cliente
        email_cliente = pedido.user.email
        if not email_cliente:
            print(f"El cliente {pedido.user.username} no tiene email configurado")
            return False

        # Crear envío y generar QR
        envio = None
        qr_image = None
        
        try:
            # Crear envío asociado al pedido
            direccion = getattr(pedido.user.perfil, 'direccion', 'No especificada') if hasattr(pedido.user, 'perfil') else 'No especificada'
            
            envio = Envio.objects.create(
                pedido=pedido,
                direccion_entrega=direccion,
                estado='pendiente'
            )
            
            # Generar QR del envío
            qr_image = envio.generar_qr_code()
            print(f"Envío #{envio.id} creado con QR para pedido #{pedido.id}")
            
        except Exception as e:
            print(f"Error al crear envío/QR: {str(e)}")
            # Continuar sin QR si hay error

        # Preparar contexto para el email
        contexto = {
            'pedido': pedido,
            'estado_pago': estado_pago,
            'detalles': pedido.detalles_pedido.all(),
            'cliente_nombre': pedido.user.perfil.nombre if pedido.user.perfil.nombre else pedido.user.username,
            'envio': envio,
            'qr_image': qr_image,
        }

        # Crear contenido HTML del email
        html_content = render_to_string('emails/confirmacion_compra.html', contexto)
        text_content = strip_tags(html_content)

        # Configurar email
        asunto = f"Tu pedido #{pedido.id} - {estado_pago.title()}"
        
        email = EmailMultiAlternatives(
            subject=asunto,
            body=text_content,
            from_email=EMAIL_HOST_USER,
            to=[email_cliente]
        )
        
        # Adjuntar QR si existe
        if qr_image:
            # Decodificar base64 y adjuntar como imagen
            import base64
            from io import BytesIO
            
            qr_data = base64.b64decode(qr_image)
            email.attach('qr_envio.png', qr_data, 'image/png')
        
        email.attach_alternative(html_content, "text/html")
        
        # Enviar email
        email.send()
        print(f"Email con QR enviado exitosamente a {email_cliente}")
        return True

    except Exception as e:
        print(f"Error al enviar email de confirmación: {str(e)}")
        return False


def respuesta_pago_mp(request, pedido_id):
    """Maneja las respuestas de pago de MercadoPago con pedido_id"""
    try:
        # Obtener el pedido según el tipo de usuario
        if request.user.is_superuser:
            pedido = get_object_or_404(Pedido, id=pedido_id)
        elif request.user.groups.filter(name__in=['vendedor']).exists():
            pedido = get_object_or_404(Pedido, id=pedido_id, vendedor=request.user)
        else:
            pedido = get_object_or_404(Pedido, id=pedido_id, user=request.user)
        
        # Determinar el estado desde la URL
        if 'pago-exitoso' in request.path:
            estado = 'exito'
        elif 'pago-fallido' in request.path:
            estado = 'fallido'
        elif 'pago-pendiente' in request.path:
            estado = 'pendiente'
        else:
            estado = 'desconocido'
        
        # Procesar según el estado
        if estado == 'exito':
            if pedido.estado == 'pendiente':  # Solo procesar si aún está pendiente
                pedido.pagado = True
                pedido.estado = 'pagado'
                pedido.save()
                
                # Vaciar el carrito
                try:
                    cart = Cart.objects.get(user=request.user)
                    cart.products.clear()
                except Cart.DoesNotExist:
                    pass
                
                # Enviar email de confirmación
                enviar_email_confirmacion_compra(pedido, "Pago Exitoso")
                
                messages.success(request, f"¡Pedido #{pedido.id} pagado exitosamente!")
            else:
                messages.info(request, f"El pedido #{pedido.id} ya fue procesado anteriormente.")
        
        elif estado == 'pendiente':
            # No hacer nada, mantener el pedido como pendiente
            messages.info(request, f"Tu pago está pendiente de confirmación.")
            
        elif estado == 'fallido':
            if pedido.estado == 'pendiente':  # Solo actualizar si aún está pendiente
                pedido.pagado = False
                pedido.estado = 'cancelado'
                pedido.save()
                
                # No vaciar carrito en pago fallido, podría querer reintentar
                
                messages.error(request, f"El pago del pedido #{pedido.id} falló. Puedes intentarlo nuevamente.")
        
        context = {
            "estado": estado,
            "pedido": pedido,
            "mensaje": None  # El mensaje se manejará con las messages de Django
        }
        
        return render(request, 'respuesta_pago.html', context)
        
    except Exception as e:
        messages.error(request, f"Error al procesar la respuesta del pago: {str(e)}")
        return redirect('agregar_cuenta_mercado_pago')


@csrf_exempt
@require_POST
def mercadopago_webhook(request):
    """
    Webhook para recibir notificaciones de MercadoPago
    """
    try:
        # Obtener datos del webhook
        data = json.loads(request.body)
        
        # Log para debugging
        print(f"Webhook recibido: {data}")
        
        # Verificar si es una notificación de pago
        if data.get('type') == 'payment':
            payment_id = data.get('data', {}).get('id')
            
            if payment_id:
                # Obtener información del pago desde MercadoPago
                sdk = mercadopago.SDK("TEST-7867507306076979-091418-7e221cf9b9d21514d56b55c7143e0ecd-33669542")  # Usar token de cuenta activa
                
                payment_info = sdk.payment().get(payment_id)
                
                if payment_info['status'] == 200:
                    payment = payment_info['response']
                    
                    # Buscar el pedido asociado (usando referencia externa)
                    external_reference = payment.get('external_reference')
                    
                    if external_reference:
                        # El external_reference debería contener el ID del pedido
                        try:
                            pedido_id = int(external_reference.split('-')[-1])  # Formato: "pedido-{id}"
                            pedido = Pedido.objects.get(id=pedido_id)
                            
                            # Actualizar estado del pedido según el estado del pago
                            payment_status = payment.get('status')
                            
                            if payment_status == 'approved':
                                if pedido.estado == 'pendiente':
                                    pedido.estado = 'pagado'
                                    pedido.save()
                                    
                                    # Vaciar carrito
                                    try:
                                        cart = Cart.objects.get(user=pedido.user)
                                        cart.products.clear()
                                    except Cart.DoesNotExist:
                                        pass
                                    
                                    # Enviar email de confirmación
                                    enviar_email_confirmacion_compra(pedido, "Pago Exitoso")
                                    
                                    print(f"Pedido #{pedido.id} marcado como pagado vía webhook")
                                    
                            elif payment_status == 'rejected':
                                pedido.estado = 'cancelado'
                                pedido.save()
                                print(f"Pedido #{pedido.id} marcado como cancelado vía webhook")
                                
                        except (ValueError, Pedido.DoesNotExist) as e:
                            print(f"No se encontró pedido para external_reference {external_reference}: {e}")
                    
        return JsonResponse({'status': 'ok'}, status=200)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        print(f"Error en webhook de MercadoPago: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def respuesta_pago(request, estado=None, usuario=None):
    """Maneja las respuestas de pago de MercadoPago"""
    # Obtener el pedido desde los parámetros GET o POST
    pedido_id = request.GET.get('pedido_id') or request.POST.get('pedido_id')
    
    if not pedido_id:
        messages.error(request, "No se encontró el pedido.")
        return redirect('carrito')
    
    try:
        if request.user.is_superuser:
            pedido = Pedido.objects.get(id=pedido_id)
        elif request.user.groups.filter(name__in=['vendedor']).exists():
            pedido = Pedido.objects.get(id=pedido_id, vendedor=request.user)
        else:
            pedido = Pedido.objects.get(id=pedido_id, user=request.user)
    except Pedido.DoesNotExist:
        messages.error(request, "El pedido no existe.")
        return redirect('carrito')
    
    # Solo procesar si el pago es exitoso
    if estado == "exito":
        # Confirmar y guardar el pedido solo cuando el pago es exitoso
        if pedido.estado == 'pendiente':  # Solo procesar si aún está pendiente
            pedido.pagado = True
            pedido.estado = 'pagado'
            pedido.save()
            
            # Vaciar el carrito
            try:
                cart = Cart.objects.get(user=request.user)
                cart.products.clear()
            except Cart.DoesNotExist:
                pass
            
            # Enviar email de confirmación
            enviar_email_confirmacion_compra(pedido, "Pago Exitoso")
            
            messages.success(request, f"¡Pedido #{pedido.id} pagado exitosamente!")
        else:
            messages.info(request, f"El pedido #{pedido.id} ya fue procesado anteriormente.")
    
    elif estado == "pendiente":
        # No hacer nada, mantener el pedido como pendiente
        messages.info(request, f"Tu pago está pendiente de confirmación.")
        
    else:  # pago fallido
        if pedido.estado == 'pendiente':  # Solo actualizar si aún está pendiente
            pedido.pagado = False
            pedido.estado = 'cancelado'
            pedido.save()
            
            # No vaciar carrito en pago fallido, podría querer reintentar
            
            messages.error(request, f"El pago del pedido #{pedido.id} falló. Puedes intentarlo nuevamente.")
    
    context = {
        "estado": estado,
        "pedido": pedido,
        "mensaje": None  # El mensaje se manejará con las messages de Django
    }
    
    return render(request, 'respuesta_pago.html', context)


@login_required
def eliminar_producto(request, cart_item_id):
    cart_item = get_object_or_404(CartItem, id=cart_item_id)
    cart_item.delete()
    messages.error(request, "Se ha eliminado el producto!")
    return redirect('carrito')

@login_required
@user_passes_test(lambda u: u.is_staff)
def flayer_panel(request, ID=None):
    cartel = None
    carteles = None
    if ID:
        cartel = CarruselImages.objects.get(id=ID)
        form = CartelForm(instance=cartel)
    else:
        form = CartelForm()

    carteles = CarruselImages.objects.all()

    if request.method == 'POST':
        if ID:
            form = CartelForm(request.POST, request.FILES, instance=cartel)
        else:
            form = CartelForm(request.POST, request.FILES)

        if form.is_valid():
            form.save()
            if ID:
                return redirect('create_flayer_id', ID=ID)
            else:
                return redirect('create_flayer')

    context = {
        'carteles': carteles,
        'form': form
    }
    return render(request, 'create_flayer.html', context)

@login_required
def eliminar_cartel(request, ID=None):
    if request.method == "POST":
        try:
            cartel = CarruselImages.objects.get(id=ID)
            cartel.delete()
            messages.success(request, f"Se elimino {cartel.titulo} con exito!!")

        except CarruselImages.DoesNotExist():
            messages.error(request, f"Error al eliminar cartel")

    return redirect('create_flayer')

@login_required
@user_passes_test(lambda u: u.is_staff)
def create_user(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            # Guardar el usuario primero
            user = form.save()
            # Obtener el grupo seleccionado
            grupo_id = request.POST.get('grupo')

            if grupo_id:
                try:
                    grupo = Group.objects.get(id=grupo_id)
                    # ASIGNAR GRUPO AL USUARIO
                    user.groups.add(grupo)

                    # ACTUALIZAR EL TIPO_USUARIO EN EL PERFIL SEGÚN EL GRUPO
                    perfil, created = Perfil.objects.get_or_create(user=user)

                    # Mapear grupo a tipo_usuario
                    if grupo.name in ['admin', 'administrador']:
                        perfil.tipo_usuario = 'admin'
                        perfil.user.is_staff = True

                    elif grupo.name in ['vendedor', 'vendedores']:
                        perfil.tipo_usuario = 'vendedor'
                        perfil.user.is_staff = True
                    else:
                        perfil.tipo_usuario = 'cliente'

                    perfil.save()

                    messages.success(request, f"Usuario {user.username} creado con éxito y asignado al grupo {grupo.name}!")

                except Group.DoesNotExist:
                    # Si el grupo no existe, crear perfil con tipo por defecto
                    perfil, created = Perfil.objects.get_or_create(user=user)
                    perfil.tipo_usuario = 'cliente'
                    perfil.save()

                    messages.warning(request, f"Usuario {user.username} creado, pero el grupo seleccionado no existe. Se asignó tipo 'cliente' por defecto.")
            else:
                # Si no se seleccionó grupo, crear perfil con tipo por defecto
                perfil, created = Perfil.objects.get_or_create(user=user)
                perfil.tipo_usuario = 'cliente'
                perfil.save()

                messages.success(request, f"Usuario {user.username} creado con éxito (tipo 'cliente' por defecto)!")

            return redirect('user_panel')
        else:
            # Mostrar errores de forma más legible
            error_message = "No se pudo registrar el usuario. Errores:<br>"
            for field, errors in form.errors.items():
                error_message += f"- {field}: {', '.join(errors)}<br>"

            messages.error(request, error_message)

    return redirect('user_panel')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_user(request, user_id):
    user = User.objects.get(pk=user_id)
    if request.method == 'POST':
        user.delete()
        messages.success(request, "Se ha eliminado el Usuario!")
        return redirect('user_panel')

    mensaje = "Vas a eliminar al usuario {}, desea continuar?".format(user.username)
    titulo = "Eliminar Usuario?"
    url_close = "/panel_usuario/"
    return render(request, 'delete_msj.html', {'titulo': titulo, 'mensaje':mensaje, 'url_close':url_close})

@login_required
@user_passes_test(lambda u: u.is_staff)
def create_superuser(request):
    if request.method == 'POST':
        form = SuperuserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('user_panel')
    else:
        form = SuperuserCreationForm()
    return render(request, 'create_superuser.html', {'form': form})

@login_required
@user_passes_test(lambda u: u.is_staff)
def edit_user(request, user_id=None):
    try:
        user = None

        if user_id:
            user = get_object_or_404(User, id=user_id)

        if request.method == 'POST':
            form = UserEditForm(request.POST, instance=user)

            if form.is_valid():
                try:
                    form.save()
                    messages.success(request, f'Usuario {user.username} actualizado correctamente!')
                    return redirect('user_panel')
                except Exception as e:
                    messages.error(request, f'Error al guardar el usuario: {str(e)}')
            else:
                messages.error(request, 'Por favor, corrija los errores en el formulario.')
        else:
            form = UserEditForm(instance=user)

        context = {
            'form': form,
            'user_id': user_id,
        }

        return render(request, 'edit_user.html', context)
    
    except Exception as e:
        messages.error(request, f'Error al cargar el formulario de edición: {str(e)}')
        return redirect('user_panel')

@login_required
@user_passes_test(lambda u: u.is_staff)
def create_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            return redirect('product_panel')
    else:
        form = ProductForm()

    context = {'form': form}
    return render(request, 'create_product.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def edit_product(request, product_id):
    product = Product.objects.get(id=product_id)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Se edito producto con exito!!")

        else:
            error = form.errors
            messages.error(request, f"Se produjo un error al editar:<br>{error}")

    else:
        form = ProductForm(instance=product)

    context = {
        'form': form,
        'product_id': product_id,
    }

    return render(request, 'edit_product.html', context)


@login_required
@user_passes_test(lambda u: u.is_staff)
def crear_oferta(request, product_id):
    producto = Product.objects.get(id=product_id)
    
    if request.method == 'POST':
        tipo_oferta = request.POST.get('tipo_oferta')
        duracion_dias = request.POST.get('duracion_dias', '30')  # Default 30 días
        
        # Validar duración
        try:
            duracion_dias = int(duracion_dias)
            if duracion_dias < 1 or duracion_dias > 365:
                return JsonResponse({'success': False, 'message': 'La duración debe estar entre 1 y 365 días'})
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'Duración inválida'})
        
        # Eliminar oferta existente si hay una
        Oferta.objects.filter(producto=producto).delete()
        
        # Crear nueva oferta según el tipo
        if tipo_oferta == 'descuento':
            descuento = request.POST.get('descuento')
            if descuento:
                oferta = Oferta.objects.create(
                    producto=producto,
                    tipo_oferta='descuento',
                    descuento=int(descuento),
                    duracion_dias=duracion_dias
                )
        elif tipo_oferta == 'combinar':
            producto_combinar_id = request.POST.get('producto_combinar')
            monto_combinar = request.POST.get('monto_combinar')
            if producto_combinar_id and monto_combinar:
                producto_combinar = Product.objects.get(id=producto_combinar_id)
                oferta = Oferta.objects.create(
                    producto=producto,
                    tipo_oferta='combinar',
                    producto_combinar=producto_combinar,
                    monto_combinar=float(monto_combinar),
                    duracion_dias=duracion_dias
                )
        elif tipo_oferta == 'multiplicidad':
            tipo_multiplicidad = request.POST.get('tipo_multiplicidad')
            if tipo_multiplicidad:
                oferta = Oferta.objects.create(
                    producto=producto,
                    tipo_oferta='multiplicidad',
                    tipo_multiplicidad=tipo_multiplicidad,
                    duracion_dias=duracion_dias
                )
        
        return JsonResponse({'success': True, 'message': 'Oferta creada exitosamente'})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})

@login_required
@user_passes_test(lambda u: u.is_staff)
def api_productos(request):
    """API para cargar productos dinámicamente en el modal"""
    productos = Product.objects.all().values('id', 'nombre')
    return JsonResponse(list(productos), safe=False)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def gestion_ofertas(request):
    """Vista para gestionar todas las ofertas"""
    
    # Desactivar automáticamente ofertas expiradas
    ofertas_expiradas = Oferta.desactivar_ofertas_expiradas()
    
    # Obtener todas las ofertas (activas e inactivas)
    todas_ofertas = Oferta.objects.all().order_by('-fecha_creacion')
    
    # Separar ofertas activas e inactivas
    ofertas_activas = todas_ofertas.filter(activa=True)
    ofertas_inactivas = todas_ofertas.filter(activa=False)
    
    context = {
        'ofertas_activas': ofertas_activas,
        'ofertas_inactivas': ofertas_inactivas,
        'ofertas_expiradas_count': ofertas_expiradas,
    }
    
    return render(request, 'gestion_ofertas.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def toggle_oferta(request, oferta_id):
    """API para activar/desactivar una oferta"""
    if request.method == 'POST':
        try:
            oferta = Oferta.objects.get(id=oferta_id)
            oferta.activa = not oferta.activa
            oferta.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Oferta {"activada" if oferta.activa else "desactivada"} exitosamente',
                'activa': oferta.activa
            })
        except Oferta.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Oferta no encontrada'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def eliminar_oferta(request, oferta_id):
    """API para eliminar una oferta"""
    if request.method == 'POST':
        try:
            oferta = Oferta.objects.get(id=oferta_id)
            producto_nombre = oferta.producto.nombre
            oferta.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Oferta de "{producto_nombre}" eliminada exitosamente'
            })
        except Oferta.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Oferta no encontrada'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})

@login_required
@user_passes_test(lambda u: u.is_staff)
def modif_stock(request):
    productos = Product.objects.all()
    total_stock = sum(producto.stock or 0 for producto in productos)

    if request.method == "POST":
        try:
            cantidad = int(request.POST.get("unidad", 0))

            # Agregar stock masivo (desde el modal)
            if 'modif_stock' in request.POST:
                aplicar_a = request.POST.get('aplicar_a', 'todos')

                if aplicar_a == 'sin_stock':
                    productos_a_actualizar = productos.filter(stock=0)
                elif aplicar_a == 'con_stock':
                    productos_a_actualizar = productos.filter(stock__gt=0)
                else:  # todos
                    productos_a_actualizar = productos

                productos_afectados = productos_a_actualizar.update(stock=cantidad)
                messages.success(request, f"Se actualizó el stock a {cantidad} unidades para {productos_afectados} productos.")

            # Vaciar solo productos con stock existente
            elif 'vaciar_stock' in request.POST:
                productos_con_stock = productos.filter(stock__gt=0)
                productos_afectados = productos_con_stock.update(stock=0)
                messages.warning(request, f"Se vació el stock de {productos_afectados} productos que tenían stock.")

            # Limpiar TODO el stock (a 0)
            elif 'limpiar_todo' in request.POST:
                productos_afectados = productos.update(stock=0)
                messages.warning(request, f"Se limpió el stock de {productos_afectados} productos.")

            # Establecer stock mínimo
            elif 'stock_minimo' in request.POST:
                productos_afectados = productos.update(stock=cantidad)
                messages.info(request, f"Se estableció stock mínimo de {cantidad} unidades para {productos_afectados} productos.")

        except ValueError:
            messages.error(request, "La cantidad debe ser un número válido.")
        except Exception as e:
            messages.error(request, f"Error al modificar stock: {str(e)}")

    return redirect('product_panel')


@login_required
@user_passes_test(lambda u: u.is_staff)
def delete_product(request, product_id):
    product = Product.objects.get(pk=product_id)
    product.delete()
    messages.error(request, "Se ha eliminado el Producto!")
    return redirect('product_panel')

def product_detail(request, product_id):
    precio_x_unidad = 0
    product = Product.objects.get(id=product_id)
    ofertas = Oferta.objects.all()

    try:
        precio_final = product.en_oferta.precio_final
    except:
        precio_final = product.precio

    if product.unidad_x_pack != 0:
        precio_x_unidad = product.precio / product.unidad_x_pack
    else:
        precio_x_unidad = 0

    # Configurar meta tags para Open Graph (Facebook)
    request.META['OG_TITLE'] = f"{(product.nombre or 'Producto')} - Distribuidora Gigante"
    request.META['OG_DESCRIPTION'] = f"{product.descripcion[:200]}..." if product.descripcion and len(product.descripcion) > 200 else product.descripcion or ""
    request.META['OG_IMAGE'] = f"{request.scheme}://{request.get_host()}{product.imagen1.url}" if product.imagen1 and product.imagen1 != "default_image.png" else f"{request.scheme}://{request.get_host()}/static/img/logo.png"
    request.META['OG_URL'] = f"{request.scheme}://{request.get_host()}{request.path}"
    request.META['OG_TYPE'] = "product"
    request.META['OG_SITE_NAME'] = "Distribuidora Gigante"

    context = {
        'product': product, 
        'precio_x_unidad': round(precio_x_unidad), 
        'precio_final': precio_final,
        'og_title': request.META['OG_TITLE'],
        'og_description': request.META['OG_DESCRIPTION'],
        'og_image': request.META['OG_IMAGE'],
        'og_url': request.META['OG_URL'],
        'og_type': request.META['OG_TYPE'],
        'og_site_name': request.META['OG_SITE_NAME']
    }

    registrar_accion(product, "click")
    return render(request, 'product_detail.html', context)

def acerca(request):
    template_name = "acerca.html"
    return render(request, template_name)

def contacto(request):
    template_name = "contacto.html"
    contacto = Contacto()
    if request.method == "POST":
        contacto.nombre = request.POST.get("nombre")
        contacto.correo = request.POST.get("correo")
        contacto.telefono = request.POST.get("telefono")
        contacto.mensaje = request.POST.get("mensaje")
        contacto.save()
        messages.success(request, "Su mensaje ha sido enviado con exito!!!")
        return redirect("/contacto")

    return render(request, template_name)

@login_required
def gestion_mensajes(request):
    """Vista para gestionar mensajes de contacto con paginación"""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "No tienes permisos para acceder a esta página.")
        return redirect('admin_panel')
    
    # Configuración de paginación
    mensajes_por_pagina = 10
    pagina_actual = request.GET.get('pagina', 1)
    
    try:
        pagina_actual = int(pagina_actual)
    except ValueError:
        pagina_actual = 1
    
    # Obtener todos los mensajes ordenados por fecha (más recientes primero)
    todos_mensajes = Contacto.objects.all().order_by('-fecha')
    total_mensajes = todos_mensajes.count()
    
    # Calcular paginación
    total_paginas = (total_mensajes + mensajes_por_pagina - 1) // mensajes_por_pagina
    inicio = (pagina_actual - 1) * mensajes_por_pagina
    fin = inicio + mensajes_por_pagina
    
    # Obtener mensajes de la página actual
    mensajes = todos_mensajes[inicio:fin]
    
    context = {
        'mensajes': mensajes,
        'total_mensajes': total_mensajes,
        'pagina_actual': pagina_actual,
        'total_paginas': total_paginas,
        'mensajes_por_pagina': mensajes_por_pagina,
        'rango_paginas': range(max(1, pagina_actual - 2), min(total_paginas + 1, pagina_actual + 3)),
    }
    
    return render(request, 'gestion_mensajes.html', context)

@login_required
def api_mensajes_contacto(request):
    """API para obtener mensajes de contacto"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'No tienes permisos'})
    
    mensajes = Contacto.objects.all().order_by('-fecha')
    mensajes_data = []
    
    for mensaje in mensajes:
        mensajes_data.append({
            'id': mensaje.id,
            'nombre': mensaje.nombre,
            'correo': mensaje.correo,
            'telefono': mensaje.telefono,
            'mensaje': mensaje.mensaje[:100] + '...' if len(mensaje.mensaje) > 100 else mensaje.mensaje,
            'fecha': mensaje.fecha.isoformat(),
            'leido': getattr(mensaje, 'leido', False)  # Agregar campo leido si existe
        })
    
    return JsonResponse({'success': True, 'mensajes': mensajes_data})

@login_required
def api_eliminar_mensaje(request, mensaje_id):
    """API para eliminar un mensaje de contacto"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'No tienes permisos'})
    
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        mensaje = Contacto.objects.get(id=mensaje_id)
        mensaje.delete()
        return JsonResponse({'success': True, 'message': 'Mensaje eliminado correctamente'})
    except Contacto.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Mensaje no encontrado'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def api_ver_mensaje(request, mensaje_id):
    """API para obtener detalles de un mensaje específico"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'No tienes permisos'})
    
    try:
        mensaje = Contacto.objects.get(id=mensaje_id)
        mensaje_data = {
            'id': mensaje.id,
            'nombre': mensaje.nombre,
            'correo': mensaje.correo,
            'telefono': mensaje.telefono,
            'mensaje': mensaje.mensaje,
            'fecha': mensaje.fecha.isoformat(),
            'leido': getattr(mensaje, 'leido', False)
        }
        return JsonResponse({'success': True, 'mensaje': mensaje_data})
    except Contacto.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Mensaje no encontrado'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def faq(request):
    template_name = "faq.html"
    return render(request, template_name)

def ofertas(request):
    # Desactivar automáticamente ofertas expiradas
    Oferta.desactivar_ofertas_expiradas()
    
    # Obtener solo ofertas vigentes
    ofertas = Oferta.objects.filter(activa=True)
    imagenes = CarruselImages.objects.all()
    return render(request, 'ofertas.html', {'imagenes':imagenes, 'ofertas':ofertas })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def buscar_imagenes(request, ID=None):
    produc_con_url = 0
    produc_sin_imagen = 0
    produc_con_imagen = 0
    total_productos = 0
    name = None
    params = None
    form = None
    productos = None
    imagen_resul = 0

    if ID:
        productos = [Product.objects.get(id=ID)]
        total_productos = len(productos)
    else:
        productos = Product.objects.all()
        total_productos = productos.count()

    if request.method == "POST":
        sch_engine = request.POST.getlist("engine")[0]
        descrip_nombre = request.POST.get("nombre_descripcion")
        print(sch_engine)
        if ID:
            if len(request.POST.getlist("sinimagen")) > 0:
                messages.info(request, "Imagen del producto eliminada!")
                for producto in productos:
                    producto.imagenurl = ""
                    producto.save()

            else:
                messages.info(request, "Buscando imagen del producto!")
                for producto in productos:
                    data = "{a} {b}".format(a=descrip_nombre, b=producto.marca)
                    producto.buscar_imagen(q=data, engine=sch_engine, result=None)
                    producto.save()


            return redirect("product_img_search_id", ID=ID)

        else:
            messages.warning(request, "Buscando imagenes todos los productos!")
            if total_productos < 50:
                for producto in productos:
                    data = "{a} {b}".format(a=producto.nombre, b=producto.marca)
                    producto.buscar_imagen(q=data, engine=sch_engine, result=imagen_resul)
                    producto.save()
            else:
                CargarImagenes(request, productos=productos, engine=sch_engine, num_result=imagen_resul).start()

            return redirect("product_img_search")

    else:
        for producto in productos:
            if producto.imagen1 != "default_image.png" or producto.imagen2 != "default_image.png":
                produc_con_imagen += 1
            else:
                if producto.imagenurl:
                    produc_con_url += 1
                else:
                    produc_sin_imagen = total_productos - 1



    context = {"total_productos":total_productos,
                    "sin_imagen":produc_sin_imagen,
                    "con_imagen":produc_con_imagen,
                    "con_url":produc_con_url,
                    "productos":productos,
                    "ID":ID}

    return render(request, "autocompleteimg.html", context)


@login_required
@user_passes_test(lambda u: u.is_staff)
def cargar_archivo(request, ID=None):
    context = {}
    planilla = None
    planillas = None
    selec_dict = {}
    config = False
    fecha = None
    #Campos para completar
    fields = ["nombre", "precio", "precio_m", "descripcion", "marca", "stock",
             "categoria", "subcategoria", "numero", "unidad_x_pack"]

    if ID:
        planilla = GrillaExcel.objects.get(id=ID)
    else:
        planillas = GrillaExcel.objects.all()

    if request.method == "POST":
        if planilla:
            form = CargarExcelForm(request.POST, request.FILES, instance=planilla)
            for item in fields:
                selec_dict[item] = request.POST.getlist(f"{item}-selec")

        else:
            form = CargarExcelForm(request.POST, request.FILES)

        if form.is_valid():
            instancia = form.save(commit=True)
            if planilla:
                instancia.json_data = selec_dict

            instancia.fecha = timezone.now()
            instancia.save()

        messages.warning(request, "Cargando Planilla!")
        return redirect('cargar_archivo_id', ID=instancia.id)

    else:
        if planilla:
            if planilla.json_data:
                selec_dict = planilla.json_data
                config = True

            else:
                items = planilla.get_titles_columns()
                items.insert(0, "Ninguno")

                for item in fields:
                    selec_dict[item] = items

            form = CargarExcelForm(instance=planilla)

            fecha = planilla.actualizado

        else:
            form = CargarExcelForm()


    context = {"form":form, "planilla":planilla,
               "planillas":planillas,
               "selec_dict":selec_dict, "config":config,
               "fecha":fecha}

    return render(request, "cargar_desde.html", context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def eliminar_archivo(request, ID):
    planilla = get_object_or_404(GrillaExcel, id=ID)
    planilla.delete()
    messages.error(request, "se ha eliminado el archivo!")
    return redirect(cargar_archivo)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def cargar_productos(request, ID):
    planilla = GrillaExcel.objects.get(id=ID)
    n_elem = None
    n_created = 0
    n_updates = 0
    last_catego = {}
    subproceso = False
    atributos = {"nombre":None, "precio":None, "precio_m":None,
                 "stock":None, "marca":None,
                 "categoria":None, "subcategoria":None, "numero":None,
                 "unidad_x_pack":None, "descripcion":None}

    defaults_update = {}

    if request.method == "POST":
        data = planilla.get_data_json()
        n_elem = data["nombre"].count()
        cargar_db = CargarPoductosAuto(request, n_elem, data, atributos, "Productos")
        #Bucle principal de creacion de elementos
        if cargar_db.cargar_datos():
            messages.success(request, f"Se cargaron con exito {n_elem}....")
            return redirect("catalogo")
        else:
            messages.error(request, f"Fallo al cargar los datos:{cargar_db.error}..")

        return redirect("cargar_productos", ID=ID)

    context = {'config_selec': planilla.json_data, "subproceso":subproceso}

    return render(request, "cargar_productos.html", context)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def actualizar_productos(request, ID):
    planilla = GrillaExcel.objects.get(id=ID)
    if request.method == "POST":
        pass

    context = {}
    return render(request, context)

def render_to_pdf(template_path, context_dict, request):
    template = get_template(template_path)
    html_string = template.render(context_dict)
    # css_url = os.path.join(BASE_DIR, "core/static/lib/css/bootstrap-grid.min.css")
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'filename="catalogo-chl.pdf"'
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)

    return response

def renderpdf_from(request, products=None, orden=None):
    mes = timezone.now().strftime("%B - %Y")
    num_productos_x_pagina = 16
    max_productos = {}  # Inicializa la lista de páginas
    num_de_pagina = 1
    max_productos[num_de_pagina] = []
    marcas_por_categorias = {}
    productos_por_marca = []
    productos_por_fila = 4
    titulo = None

    # Organiza los productos por categoría
    if orden:
        if isinstance(orden, list):
            titulo = ' - '.join(orden)

            for categ in orden:
                marcas_por_categorias[categ] = {}
        else:
            titulo = orden
    # Recorre todos los productos
    for product in products:
        categoria_nombre = product.categoria.nombre
        marca = product.marca
        # Clasifica las marcas_dentro de las categorias y los productos dentro de las marcas
        if categoria_nombre not in marcas_por_categorias:
            marcas_por_categorias[categoria_nombre] = {}

        if marca not in marcas_por_categorias[categoria_nombre]:
            marcas_por_categorias[categoria_nombre][marca] = []

        marcas_por_categorias[categoria_nombre][marca].append(product)

    context = {
        'marcas_por_categorias': marcas_por_categorias,
        'num_productos_x_pagina': num_productos_x_pagina,
        'productos_por_fila':productos_por_fila,
        'date': mes,
        'titulo': titulo,
        'orden':orden,
    }

    # Ruta de la plantilla HTML
    template_path = 'catalogo_template.html'  # Reemplaza con la ruta de tu plantilla HTML

    # Renderiza el PDF y devuelve la respuesta
    return render_to_pdf(template_path, context, request)

def catalogo_pdf(request, orden=None):
    # Obtén la lista de productos
    if orden:
        products = Product.objects.all().filter(categoria__nombre=orden).order_by('-categoria__nombre')
    else:
        products = Product.objects.all().order_by('-categoria__nombre')

    # Renderiza el PDF y devuelve la respuesta
    return renderpdf_from(request, products, orden)

def selec_catalogo_pdf(request):
    categorias = Category.objects.all()
    productos = Product.objects.all()
    msj = None

    if request.method == "POST":
        selec_lista = request.POST.getlist("lista-categorias")
        if len(selec_lista) != 0:
            categorias_selec = productos.filter(categoria__nombre__in=selec_lista).order_by('-categoria__nombre')
            return renderpdf_from(request, categorias_selec, selec_lista)
        else:
            msj = "Debe tildar alguna categoria.."


    context = {'categorias':categorias, 'msj':msj}
    return render(request, 'catalogo_a_pdf.html', context)


def change_info(request):       #Modificar información como visitas al sitio web y visitar ip
    # Por cada visita, agregue 1 al número total de visitas al sitio web
    count_nums = VisitNumber.objects.filter(id=1)
    if count_nums:
        count_nums = count_nums[0]
        count_nums.count += 1
    else:
        count_nums = VisitNumber()
        count_nums.count = 1
    count_nums.save()

    # Registre el número de visitas a ip y cada ip
    if 'HTTP_X_FORWARDED_FOR' in request.META:  # Obtener ip
        client_ip = request.META['HTTP_X_FORWARDED_FOR']
        client_ip = client_ip.split(",")[0]  # Así que aquí está la ip real
    else:
        client_ip = request.META['REMOTE_ADDR']  # Obtenga proxy ip aquí
    # print(client_ip)

    ip_exist = Userip.objects.filter(ip=str(client_ip))
    if ip_exist:  # Determinar si existe la ip
        uobj = ip_exist[0]
        uobj.count += 1
    else:
        uobj = Userip()
        uobj.ip = client_ip
        uobj.count = 1
    uobj.save()

    # Incrementar las visitas de hoy
    date = timezone.now().date()
    today = DayNumber.objects.filter(day=date)
    if today:
        temp = today[0]
        temp.count += 1
    else:
        temp = DayNumber()
        temp.dayTime = date
        temp.count = 1
    temp.save()


def deshacer_ultima_carga(request):
    ultima_carga = CargaArchivo.objects.filter(usuario=request.user).order_by('-fecha').first()

    if not ultima_carga:
        messages.warning(request, "No se encontró una carga para deshacer.")
        return redirect('productos')

    productos_eliminados = Product.objects.filter(carga=ultima_carga).delete()
    ultima_carga.delete()

    messages.success(request, f"Se deshicieron los cambios. Productos eliminados: {productos_eliminados[0]}")
    return redirect('productos')

@login_required
def actualizar_perfil(request):
    if request.method == 'POST':
        perfil = request.user.perfil

        # Actualizar campos del perfil
        perfil.nombre = request.POST.get('nombre', '')
        perfil.direccion = request.POST.get('direccion', '')
        perfil.localidad = request.POST.get('localidad', '')
        perfil.telefono = request.POST.get('telefono', '')
        perfil.save()

        messages.success(request, "Perfil actualizado correctamente.")

        # Redirigir a la página indicada o al carrito por defecto
        next_url = request.POST.get('next', reverse('carrito'))
        return redirect(next_url)

    return redirect('carrito')

@login_required
@user_passes_test(lambda u: u.is_staff or u.groups.filter(name='vendedor').exists() or u.is_superuser)
def panel_gestion_clientes(request):
    # Obtener o crear el perfil del usuario actual
    perfil_usuario, created = Perfil.objects.get_or_create(
        user=request.user,
        defaults={'tipo_usuario': 'vendedor' if request.user.groups.filter(name='vendedor').exists() else 'admin'}
    )

    # Verificar el tipo de usuario
    es_vendedor = request.user.groups.filter(name='vendedor').exists() or (perfil_usuario and perfil_usuario.tipo_usuario == 'vendedor')
    es_administrador = request.user.is_staff or request.user.is_superuser or (perfil_usuario and perfil_usuario.tipo_usuario == 'admin')

    # Obtener TODOS los perfiles de clientes
    todos_los_perfiles_clientes = Perfil.objects.filter(tipo_usuario="cliente")

    # Obtener clientes asignados según el tipo de usuario
    if es_vendedor:
        clientes_asignados = ClienteVendedor.objects.filter(vendedor=perfil_usuario).select_related('cliente', 'cliente__user')
    else:
        clientes_asignados = None

    # Lógica de visualización según tipo de usuario
    if es_administrador:
        # Para administradores: todos los clientes, todos los vendedores y todas las asignaciones
        todos_clientes = todos_los_perfiles_clientes  # ✅ ESTA ES LA LÍNEA IMPORTANTE
        
        # Obtener usuarios vendedores del grupo 'vendedores' y administradores (is_staff=True)
        vendedor_users = User.objects.filter(groups__name='vendedores').distinct()
        admin_users = User.objects.filter(is_staff=True).distinct()
        superusers = User.objects.filter(is_superuser=True).distinct()
        
        # Combinar todos los usuarios que pueden ser vendedores
        todos_vendedores_users = (vendedor_users | admin_users | superusers).distinct()
        
        # Obtener o crear perfiles para todos estos usuarios
        todos_vendedores = Perfil.objects.none()
        for user in todos_vendedores_users:
            perfil, created = Perfil.objects.get_or_create(
                user=user,
                defaults={'tipo_usuario': 'admin' if user.is_staff or user.is_superuser else 'vendedor'}
            )
            todos_vendedores = todos_vendedores | Perfil.objects.filter(id=perfil.id)
        
        # Incluir también perfiles existentes con tipo_usuario vendedor o admin
        todos_vendedores = todos_vendedores | Perfil.objects.filter(
            tipo_usuario__in=['vendedor', 'admin']
        ).select_related('user')
        
        # Asegurarse de que no haya duplicados
        todos_vendedores = todos_vendedores.distinct().select_related('user')

        todas_asignaciones = ClienteVendedor.objects.all().select_related('cliente', 'vendedor', 'cliente__user', 'vendedor__user')

    elif es_vendedor:
        # Para vendedores: clientes sin asignar y clientes de otros vendedores
        clientes_sin_asignar = todos_los_perfiles_clientes.exclude(
            id__in=ClienteVendedor.objects.all().values_list('cliente_id', flat=True)
        )

        clientes_de_otros_vendedores = Perfil.objects.filter(
            tipo_usuario='cliente',
            id__in=ClienteVendedor.objects.exclude(vendedor=perfil_usuario).values_list('cliente_id', flat=True)
        )

        todos_clientes = clientes_sin_asignar | clientes_de_otros_vendedores
        todos_vendedores = Perfil.objects.filter(tipo_usuario='vendedor').select_related('user')
        todas_asignaciones = None
    else:
        # Para otros tipos de usuarios
        todos_clientes = Perfil.objects.none()
        todos_vendedores = Perfil.objects.none()
        todas_asignaciones = None

    # Formulario para crear nuevo cliente
    form = UserCreationForm()

    if request.method == 'POST':
        if 'crear_cliente' in request.POST:
            form = UserCreationForm(request.POST)
            if form.is_valid():
                # Crear el usuario
                user = form.save()
                
                # Crear el perfil del cliente
                perfil_cliente, created = Perfil.objects.get_or_create(
                    user=user,
                    defaults={'tipo_usuario': 'cliente'}
                )
                
                # Si el perfil ya existía, actualizar su tipo a cliente
                if not created:
                    perfil_cliente.tipo_usuario = 'cliente'
                    perfil_cliente.save()
                
                # Si es vendedor, asignar automáticamente el cliente al vendedor actual
                if es_vendedor:
                    ClienteVendedor.objects.create(
                        cliente=perfil_cliente,
                        vendedor=perfil_usuario
                    )
                    messages.success(request, f'Cliente "{user.username}" creado y asignado exitosamente.')
                else:
                    messages.success(request, f'Cliente "{user.username}" creado exitosamente.')
                
                return redirect('gestion_clientes')
        
        elif 'asignar_cliente' in request.POST:
            cliente_id = request.POST.get('cliente_id')
            
            if cliente_id:
                try:
                    cliente = Perfil.objects.get(id=cliente_id, tipo_usuario='cliente')
                    
                    # Para vendedores: siempre asignar a sí mismos
                    if es_vendedor:
                        vendedor = perfil_usuario
                        messages.success(request, f'Cliente "{cliente.user.username}" asignado a ti exitosamente.')
                    else:
                        # Para administradores: usar el vendedor seleccionado
                        vendedor_id = request.POST.get('vendedor_id')
                        if vendedor_id:
                            vendedor = Perfil.objects.get(id=vendedor_id)
                            messages.success(request, f'Cliente "{cliente.user.username}" asignado a "{vendedor.user.username}" exitosamente.')
                        else:
                            messages.error(request, 'Por favor seleccione un vendedor.')
                            return redirect('gestion_clientes')
                    
                    # Crear o actualizar la asignación
                    asignacion, created = ClienteVendedor.objects.get_or_create(
                        cliente=cliente,
                        defaults={'vendedor': vendedor}
                    )
                    
                    if not created:
                        asignacion.vendedor = vendedor
                        asignacion.save()
                        if not es_vendedor:
                            messages.success(request, f'Asignación actualizada: "{cliente.user.username}" ahora está asignado a "{vendedor.user.username}".')
                    
                except Exception as e:
                    messages.error(request, f'Error al asignar cliente: {str(e)}')
            else:
                messages.error(request, 'Por favor seleccione un cliente.')
            
            return redirect('gestion_clientes')
        
        elif 'eliminar_asignacion' in request.POST:
            asignacion_id = request.POST.get('asignacion_id')
            if asignacion_id:
                try:
                    asignacion = ClienteVendedor.objects.get(id=asignacion_id)
                    cliente_nombre = asignacion.cliente.user.username
                    asignacion.delete()
                    messages.success(request, f'Asignación del cliente "{cliente_nombre}" eliminada exitosamente.')
                except Exception as e:
                    messages.error(request, f'Error al eliminar asignación: {str(e)}')
            
            return redirect('gestion_clientes')

    context = {
        'clientes_asignados': clientes_asignados,
        'es_administrador': es_administrador,
        'es_vendedor': es_vendedor,
        'form': form,
        'todos_clientes': todos_clientes,  # ✅ Esto debe incluir TODOS los clientes para admins
        'todos_vendedores': todos_vendedores,
        'todas_asignaciones': todas_asignaciones,
        'perfil_usuario': perfil_usuario,
    }

    return render(request, 'gestion_clientes.html', context)

@login_required
def procesar_pago(request, pedido_id):
    """Procesa el pago con MercadoPago con mejor manejo de errores"""
    try:
        if request.user.is_superuser:
            pedido = Pedido.objects.get(id=pedido_id)
        elif request.user.groups.filter(name__in=['vendedor']).exists():
            pedido = Pedido.objects.get(id=pedido_id, vendedor=request.user)
        else:
            pedido = Pedido.objects.get(id=pedido_id, user=request.user)
    except Pedido.DoesNotExist:
        # Buscar si el pedido existe pero pertenece a otro usuario
        if Pedido.objects.filter(id=pedido_id).exists():
            messages.error(request, f"El pedido #{pedido_id} no te pertenece. Solo puedes pagar tus propios pedidos.")
        else:
            messages.error(request, f"El pedido #{pedido_id} no existe. Verifica el número de pedido.")
        return redirect('carrito')

    # Verificar que el pedido esté pendiente
    if pedido.estado != 'pendiente':
        messages.warning(request, "Este pedido ya ha sido procesado.")
        return redirect('detalle_pedido', pedido_id=pedido.id)

    # Validar que el pedido tenga un monto válido
    if pedido.total_precio <= 0:
        messages.error(request, "El monto del pedido no es válido.")
        return redirect('detalle_pedido', pedido_id=pedido.id)

    # Obtener la cuenta activa de MercadoPago configurada en admin panel
    cuenta_mp = None
    try:
        # Buscar la cuenta activa (la que tiene el campo activa=True)
        cuenta_mp = MercadoPagoCuenta.objects.filter(activa=True).first()
        
        if cuenta_mp:
            # Usar cuenta activa sin mostrar mensaje
            pass
        else:
            # Si no hay cuentas activas, usar cuenta de prueba
            cuenta_mp = CuentaMpTest()
            
    except Exception as e:
        # En caso de error, usar cuenta de prueba
        cuenta_mp = CuentaMpTest()

    # Configurar SDK de MercadoPago usando MPCheckOut
    try:
        # Usar la clase MPCheckOut del utils.py
        mp_checkout = MPCheckOut(cuenta_mp)
        
        # Configurar el pago con el total completo (productos + envío)
        total_con_envio = float(pedido.total_precio) + float(pedido.costo_envio or 0)
        
        mp_checkout.config(
            titulo=f"PEDIDO N°:{pedido.id} - {pedido.user.username}",
            monto=total_con_envio,
            unidad=1,
            ID="service",
            external_reference=f"pedido-{pedido.id}"
        )
        
        # Configurar URLs de respuesta con webhook
        webhook_url = request.build_absolute_uri('/webhook/mercadopago/')
        mp_checkout.respuestas_urls(
            exito=request.build_absolute_uri(f'/pago-exitoso/{pedido.id}/'),
            fallo=request.build_absolute_uri(f'/pago-fallido/{pedido.id}/'),
            pendiente=request.build_absolute_uri(f'/pago-pendiente/{pedido.id}/'),
            notification_url=webhook_url
        )
        
        # Generar el botón de pago
        boton_mp = mp_checkout.boton(label='PAGAR PEDIDO')
        
        # Verificar si hubo error
        if boton_mp.startswith('Error:'):
            raise Exception(boton_mp)

        print(f"Botón MP generado exitosamente")

    except Exception as e:
        print(f"Error al procesar pago con MercadoPago: {str(e)}")
        messages.error(request, f"Error al procesar el pago: {str(e)}")
        return redirect('carrito')

    context = {
        'pedido': pedido,
        'boton_mp': boton_mp,
    }

    return render(request, 'procesar_pago.html', context)

@login_required
@require_POST
def toggle_featured(request, product_id):
    """Toggle featured status of a product via AJAX"""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'No tienes permisos para realizar esta acción'})
    
    try:
        product = Product.objects.get(id=product_id)
        product.destacado = not product.destacado
        product.save()
        
        return JsonResponse({
            'success': True,
            'featured': product.destacado,
            'message': f'Producto {"marcado como destacado" if product.destacado else "quitado de destacados"} exitosamente'
        })
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Producto no encontrado'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@user_passes_test(lambda u: u.is_superuser)
def agregar_cuenta_mercado_pago(request):
    """Agregar nueva cuenta de MercadoPago"""
    cuentas = MercadoPagoCuenta.objects.all().order_by('-id')
    cuenta_activa = cuentas.filter(activa=True).first()  # Buscar la cuenta activa
    
    # Manejar selección de cuenta de prueba (eliminado, ya no se usa)
    cuenta_prueba = None

    if request.method == 'POST':
        form = MercadoPagoCuentaForm(request.POST)
        if form.is_valid():
            cuenta = form.save()
            
            # Si es la primera cuenta, activarla automáticamente
            if MercadoPagoCuenta.objects.count() == 1:
                cuenta.activa = True
                cuenta.save()
            
            # Respuesta JSON para AJAX
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Cuenta {cuenta.nombre or "sin nombre"} agregada correctamente'
                })
            
            messages.success(request, f'Cuenta {cuenta.nombre or "sin nombre"} agregada correctamente')
            return redirect('agregar_cuenta_mercado_pago')
        else:
            # Respuesta JSON para AJAX con errores
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors,
                    'message': 'Por favor corrige los errores del formulario'
                })
    else:
        form = MercadoPagoCuentaForm()

    context = {
        'form': form,
        'title': 'CUENTAS MERCADOPAGO',
        'section': 'mercado_pago',
        'cuentas': cuentas,
        'cuenta_activa': cuenta_activa,
        'cuenta_prueba': cuenta_prueba,
    }
    return render(request, 'create_cuenta_mp.html', context)

@user_passes_test(lambda u: u.is_superuser)
def toggle_activar_cuenta_mercado_pago(request, cuenta_id):
    """Activar/desactivar cuenta de MercadoPago (solo una activa a la vez)"""
    try:
        cuenta = get_object_or_404(MercadoPagoCuenta, id=cuenta_id)
        
        if cuenta.activa:
            # Si ya está activa, desactivarla
            cuenta.activa = False
            cuenta.save()
            message = f'Cuenta "{cuenta.nombre or "Sin nombre"}" desactivada'
        else:
            # Si está inactiva, activarla y desactivar todas las demás
            MercadoPagoCuenta.objects.exclude(id=cuenta_id).update(activa=False)
            cuenta.activa = True
            cuenta.save()
            message = f'Cuenta "{cuenta.nombre or "Sin nombre"}" activada correctamente'
        
        # Respuesta JSON para AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': message,
                'activa': cuenta.activa
            })
        
        messages.success(request, message)
        return redirect('agregar_cuenta_mercado_pago')
        
    except Exception as e:
        # Respuesta JSON para AJAX con errores
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': f'Error al cambiar estado: {str(e)}'
            })
        
        messages.error(request, f'Error al cambiar estado: {str(e)}')
        return redirect('agregar_cuenta_mercado_pago')


@user_passes_test(lambda u: u.is_superuser)
def eliminar_cuenta_mercado_pago(request, cuenta_id):
    """Eliminar cuenta de MercadoPago"""
    try:
        cuenta = get_object_or_404(MercadoPagoCuenta, id=cuenta_id)
        nombre_cuenta = cuenta.nombre or "Sin nombre"
        
        # Eliminar la cuenta
        cuenta.delete()
        
        # Respuesta JSON para AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Cuenta "{nombre_cuenta}" eliminada correctamente'
            })
        
        messages.success(request, f'Cuenta "{nombre_cuenta}" eliminada correctamente')
        return redirect('agregar_cuenta_mercado_pago')
        
    except Exception as e:
        # Respuesta JSON para AJAX con errores
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': f'Error al eliminar la cuenta: {str(e)}'
            })
        
        messages.error(request, f'Error al eliminar la cuenta: {str(e)}')
        return redirect('agregar_cuenta_mercado_pago')


def generar_pdf_pedido(request, pedido_id):
    try:
        # Obtener el pedido según el tipo de usuario
        if request.user.is_superuser:
            pedido = Pedido.objects.get(id=pedido_id)
        elif request.user.groups.filter(name__in=['vendedor']).exists():
            pedido = Pedido.objects.get(id=pedido_id, vendedor=request.user)
        else:
            pedido = Pedido.objects.get(id=pedido_id, user=request.user)
        
        detalles_pedido = DetallePedido.objects.filter(pedido=pedido)

        # Crear QR code con información del pedido
        qr_data = f"""
        Pedido ID: {pedido.id}
        Cliente: {pedido.user.username}
        Total: ${pedido.total_precio}
        Fecha: {pedido.fecha_pedido.strftime('%d/%m/%Y %H:%M')}
        Estado: {pedido.estado}
        Pagado: {'Sí' if pedido.pagado else 'No'}
        """

        # Generar QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()

        context = {
            'pedido': pedido,
            'detalles_pedido': detalles_pedido,
            'qr_code': qr_base64,
            'fecha_generacion': timezone.now().strftime('%d/%m/%Y %H:%M'),
        }

        # Renderizar template HTML simple
        html_string = render_to_string('pdf_pedido_simple.html', context)

        # CSS para el PDF
        css_string = """
        @page {
            size: A4;
            margin: 2cm;
            @top-center {
                content: "Resumen del Pedido";
                font-size: 16px;
                color: #666;
            }
            @bottom-center {
                content: "Página " counter(page) " de " counter(pages);
                font-size: 12px;
                color: #666;
            }
        }

        body {
            font-family: Arial, sans-serif;
            line-height: 1.4;
            color: #333;
        }

        .header {
            text-align: center;
            border-bottom: 2px solid #f44336;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }

        .header h1 {
            color: #f44336;
            margin: 0;
            font-size: 24px;
        }

        .info-section {
            margin-bottom: 25px;
            padding: 15px;
            background-color: #f9f9f9;
            border-radius: 5px;
        }

        .info-grid {
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }

        .info-card {
            flex: 1;
            min-width: 200px;
            margin: 0 10px 10px 0;
            padding: 15px;
            background: white;
            border: 1px solid #ddd;
            border-radius: 5px;
        }

        .table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }

        .table th {
            background-color: #f44336;
            color: white;
            padding: 12px;
            text-align: left;
        }

        .table td {
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }

        .table tfoot th {
            background-color: #e0e0e0;
            color: #333;
        }

        .qr-section {
            text-align: center;
            margin-top: 30px;
            padding: 20px;
            border-top: 1px solid #ddd;
        }

        .qr-code {
            max-width: 160px;
            margin: 0 auto;
        }

        .status-tag {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 15px;
            font-weight: bold;
            font-size: 12px;
        }

        .completado { background-color: #4CAF50; color: white; }
        .pendiente { background-color: #FFC107; color: black; }
        .cancelado { background-color: #f44336; color: white; }

        .footer {
            margin-top: 40px;
            text-align: center;
            font-size: 12px;
            color: #666;
        }
        """

        # Generar PDF - solución simple
        try:
            # Intentar con WeasyPrint básico
            from weasyprint import HTML
            html_doc = HTML(string=html_string)
            pdf_bytes = html_doc.write_pdf()
        except Exception as e:
            # Si WeasyPrint falla, generar HTML como fallback
            return HttpResponse(html_string, content_type='text/html')

        # Crear respuesta HTTP
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="pedido_{pedido.id}_{timezone.now().strftime("%Y%m%d")}.pdf"'

        return response

    except Pedido.DoesNotExist:
        return HttpResponse("Pedido no encontrado", status=404)
    except Exception as e:
        return HttpResponse(f"Error al generar PDF: {str(e)}", status=500)

@login_required
def confirmar_pedido(request):
    """Vista para confirmar pedido con opciones de envío"""
    if request.method != 'POST':
        return redirect('carrito')
    
    try:
        # Obtener datos del formulario
        opcion_envio_id = request.POST.get('opcion_envio')
        direccion_calle = request.POST.get('direccion_calle', '')
        direccion_barrio = request.POST.get('direccion_barrio', '')
        direccion_cp = request.POST.get('direccion_cp', '')
        direccion_referencias = request.POST.get('direccion_referencias', '')
        observaciones = request.POST.get('observaciones', '')
        
        # Validar que se seleccionó una opción de envío
        if not opcion_envio_id:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Por favor selecciona una opción de envío.'})
            messages.error(request, 'Por favor selecciona una opción de envío.')
            return redirect('carrito')
        
        # Obtener el carrito del usuario
        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tienes productos en el carrito.'})
            messages.error(request, 'No tienes productos en el carrito.')
            return redirect('carrito')
        
        # Verificar que el carrito tenga productos
        cart_items = cart.cartitem_set.all()
        if not cart_items.exists():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Tu carrito está vacío.'})
            messages.error(request, 'Tu carrito está vacío.')
            return redirect('carrito')
        
        # Obtener opción de envío
        try:
            opcion_envio = OpcionEnvio.objects.get(id=opcion_envio_id)
        except OpcionEnvio.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'La opción de envío seleccionada no es válida.'})
            messages.error(request, 'La opción de envío seleccionada no es válida.')
            return redirect('carrito')
        
        # Crear el pedido
        pedido = Pedido.objects.create(
            user=request.user,
            estado='pendiente',
            total_cantidad=sum(item.quantity for item in cart_items),
            total_precio=sum(item.subtotal for item in cart_items),
            opcion_envio=opcion_envio,
            costo_envio=opcion_envio.costo
        )
        
        # Crear detalles del pedido
        for item in cart_items:
            DetallePedido.objects.create(
                pedido=pedido,
                producto=item.product,
                cantidad=item.quantity,
                subtotal=item.subtotal
            )
        
        # Actualizar total del pedido con costo de envío
        pedido.actualizar_pedido()
        
        # Guardar información de dirección si aplica
        if opcion_envio.costo > 0:  # Si es envío a domicilio
            # Aquí podríamos guardar la dirección en un modelo separado si es necesario
            pass
        
        # Limpiar carrito
        cart.cartitem_set.all().delete()
        
        # Enviar email de confirmación con QR
        enviar_email_confirmacion_compra(pedido, "Pendiente de Pago")
        
        # Respuesta AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True, 
                'message': f'¡Pedido #{pedido.id} confirmado exitosamente!',
                'pedido_id': pedido.id
            })
        
        # Respuesta normal
        messages.success(request, f'¡Pedido #{pedido.id} confirmado exitosamente! Te enviaremos un email con los detalles.')
        return redirect('procesar_pago', pedido_id=pedido.id)
        
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': f'Error al confirmar el pedido: {str(e)}'})
        messages.error(request, f'Error al confirmar el pedido: {str(e)}')
        return redirect('carrito')

@login_required
@user_passes_test(lambda u: u.is_staff)
def api_notificaciones(request):
    """API endpoint para obtener notificaciones del administrador"""
    if request.method == 'GET':
        notificaciones = NotificacionAdmin.objects.all().order_by('-fecha_creacion')[:50]
        
        notificaciones_data = []
        for notif in notificaciones:
            notificaciones_data.append({
                'id': notif.id,
                'tipo': notif.tipo,
                'titulo': notif.titulo,
                'mensaje': notif.mensaje,
                'leido': notif.leido,
                'fecha_creacion': notif.fecha_creacion.isoformat(),
                'fecha_lectura': notif.fecha_lectura.isoformat() if notif.fecha_lectura else None,
                'referencia_id': notif.referencia_id,
                'referencia_tipo': notif.referencia_tipo
            })
        
        return JsonResponse({
            'success': True,
            'notificaciones': notificaciones_data,
            'no_leidas': NotificacionAdmin.contar_no_leidas()
        })
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@user_passes_test(lambda u: u.is_staff)
def api_marcar_notificaciones_leidas(request):
    """API endpoint para marcar todas las notificaciones como leídas"""
    if request.method == 'POST':
        try:
            notificaciones_no_leidas = NotificacionAdmin.obtener_no_leidas()
            count = notificaciones_no_leidas.count()
            
            for notificacion in notificaciones_no_leidas:
                notificacion.marcar_como_leido()
            
            return JsonResponse({
                'success': True,
                'message': f'Se marcaron {count} notificaciones como leídas'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@user_passes_test(lambda u: u.is_staff)
def api_marcar_notificacion_leida(request, notificacion_id):
    """API endpoint para marcar una notificación específica como leída"""
    if request.method == 'POST':
        try:
            notificacion = NotificacionAdmin.objects.get(id=notificacion_id)
            notificacion.marcar_como_leido()
            
            return JsonResponse({
                'success': True,
                'message': 'Notificación marcada como leída'
            })
        except NotificacionAdmin.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Notificación no encontrada'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@user_passes_test(lambda u: u.is_staff)
def gestion_envios(request):
    """Vista para gestionar opciones de envío"""
    opciones_envio = OpcionEnvio.objects.all().order_by('nombre')
    
    if request.method == 'POST':
        # Crear nueva opción de envío
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        costo = request.POST.get('costo', '0')
        tiempo_entrega = request.POST.get('tiempo_entrega', '').strip()
        activo = request.POST.get('activo') == 'on'
        
        if nombre:
            try:
                costo_float = float(costo)
                OpcionEnvio.objects.create(
                    nombre=nombre,
                    descripcion=descripcion,
                    costo=costo_float,
                    tiempo_entrega=tiempo_entrega,
                    activo=activo
                )
                messages.success(request, f'Opción de envío "{nombre}" creada exitosamente.')
            except ValueError:
                messages.error(request, 'El costo debe ser un número válido.')
        else:
            messages.error(request, 'El nombre es obligatorio.')
        
        return redirect('gestion_envios')
    
    context = {
        'opciones_envio': opciones_envio
    }
    return render(request, 'gestion_envios.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def inicializar_envios(request):
    """Vista para inicializar opciones de envío por defecto"""
    if OpcionEnvio.objects.exists():
        messages.info(request, 'Las opciones de envío ya han sido inicializadas.')
        return redirect('gestion_envios')
    
    # Crear opciones de envío por defecto
    opciones_defecto = [
        {
            'nombre': 'Retiro en Sucursal',
            'descripcion': 'Retira tu pedido en nuestra sucursal',
            'costo': 0,
            'tiempo_entrega': 'Inmediato',
            'activo': True
        },
        {
            'nombre': 'Envío a Domicilio',
            'descripcion': 'Envío directo a tu domicilio',
            'costo': 500,
            'tiempo_entrega': '2-3 días hábiles',
            'activo': True
        },
        {
            'nombre': 'Envío Express',
            'descripcion': 'Envío prioritario a domicilio',
            'costo': 800,
            'tiempo_entrega': '24 horas',
            'activo': True
        }
    ]
    
    for opcion_data in opciones_defecto:
        OpcionEnvio.objects.create(**opcion_data)
    
    messages.success(request, f'Se han creado {len(opciones_defecto)} opciones de envío por defecto.')
    return redirect('gestion_envios')

@login_required
def api_opciones_envio(request):
    """API para obtener opciones de envío activas"""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    try:
        opciones = OpcionEnvio.objects.filter(activo=True).order_by('costo')
        opciones_data = []
        
        for opcion in opciones:
            opciones_data.append({
                'id': opcion.id,
                'nombre': opcion.nombre,
                'descripcion': opcion.descripcion,
                'costo': opcion.costo,
                'tiempo_entrega': opcion.tiempo_entrega,
                'texto_costo': f'${opcion.costo}' if opcion.costo > 0 else 'Gratis'
            })
        
        return JsonResponse({
            'success': True,
            'opciones': opciones_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al cargar opciones de envío: {str(e)}'
        })


# Vistas para Sistema de Transportistas
@login_required
@user_passes_test(lambda u: u.groups.filter(name='transportista').exists() or u.is_superuser)
def panel_transportista(request):
    """Panel principal para transportistas"""
    try:
        transportista = Transportista.objects.get(usuario=request.user)
        
        # Obtener envíos asignados
        envios = Envio.objects.filter(transportista=transportista).order_by('-fecha_creacion')
        
        # Estadísticas
        envios_pendientes = envios.filter(estado='asignado').count()
        envios_en_transito = envios.filter(estado='en_transito').count()
        envios_entregados = envios.filter(estado='entregado').count()
        
        context = {
            'transportista': transportista,
            'envios': envios[:10],  # Últimos 10 envíos
            'envios_pendientes': envios_pendientes,
            'envios_en_transito': envios_en_transito,
            'envios_entregados': envios_entregados,
        }
        return render(request, 'panel_transportista.html', context)
        
    except Transportista.DoesNotExist:
        messages.error(request, 'No tienes perfil de transportista registrado.')
        return redirect('admin_panel')


@login_required
@user_passes_test(lambda u: u.groups.filter(name='transportista').exists() or u.is_superuser)
def gestion_envios_transportista(request):
    """Gestión completa de envíos para transportistas"""
    try:
        transportista = Transportista.objects.get(usuario=request.user)
        envios = Envio.objects.filter(transportista=transportista).order_by('-fecha_creacion')
        
        # Filtros
        estado_filter = request.GET.get('estado')
        if estado_filter:
            envios = envios.filter(estado=estado_filter)
        
        # Paginación
        paginator = Paginator(envios, 20)
        page = request.GET.get('page')
        envios_page = paginator.get_page(page)
        
        context = {
            'envios': envios_page,
            'transportista': transportista,
            'estado_filter': estado_filter,
        }
        return render(request, 'gestion_envios_transportista.html', context)
        
    except Transportista.DoesNotExist:
        messages.error(request, 'No tienes perfil de transportista registrado.')
        return redirect('admin_panel')


@login_required
def escanear_qr_publico(request):
    """Vista pública para escanear QR y confirmar entrega (transportista y admin)"""
    if request.method == 'POST':
        qr_data = request.POST.get('qr_data', '')
        observaciones = request.POST.get('observaciones', '')
        
        try:
            qr_parts = qr_data.split('|')
            if len(qr_parts) >= 3:
                qr_code = qr_parts[0]
                pedido_id = qr_parts[1]
                cliente_id = qr_parts[2]
                
                envio = Envio.objects.get(qr_code=qr_code)
                
                # Verificar permisos: transportista asignado o admin
                if not request.user.is_superuser:
                    try:
                        transportista = Transportista.objects.get(usuario=request.user)
                        if envio.transportista != transportista:
                            messages.error(request, 'Este envío no está asignado a ti.')
                            return redirect('escanear_qr_publico')
                    except Transportista.DoesNotExist:
                        messages.error(request, 'No tienes permisos para confirmar envíos.')
                        return redirect('escanear_qr_publico')
                
                if envio.estado == 'entregado':
                    messages.warning(request, 'Este envío ya fue confirmado como entregado.')
                    return redirect('escanear_qr_publico')
                
                # Crear confirmación de entrega
                ConfirmacionEntrega.objects.create(
                    envio=envio,
                    qr_escaneado=qr_data,
                    transportista=envio.transportista,
                    observaciones=observaciones
                )
                
                # Confirmar entrega
                envio.confirmar_entrega()
                
                messages.success(request, f'Entrega del envío #{envio.id} confirmada exitosamente.')
                return redirect('escanear_qr_publico')
            else:
                messages.error(request, 'Código QR inválido.')
                
        except Envio.DoesNotExist:
            messages.error(request, 'El código QR escaneado no corresponde a ningún envío.')
        except Exception as e:
            messages.error(request, f'Error al procesar el QR: {str(e)}')
    
    return render(request, 'escanear_qr_publico.html')
    """Vista para escanear QR y confirmar entrega"""
    if request.method == 'POST':
        qr_data = request.POST.get('qr_data', '')
        observaciones = request.POST.get('observaciones', '')
        
        try:
            # Parsear datos del QR
            qr_parts = qr_data.split('|')
            if len(qr_parts) >= 3:
                qr_code = qr_parts[0]
                pedido_id = qr_parts[1]
                cliente_id = qr_parts[2]
                
                # Buscar envío por código QR
                envio = Envio.objects.get(qr_code=qr_code)
                transportista = Transportista.objects.get(usuario=request.user)
                
                if envio.transportista != transportista:
                    messages.error(request, 'Este envío no está asignado a ti.')
                    return redirect('escanear_qr_entrega')
                
                if envio.estado == 'entregado':
                    messages.warning(request, 'Este envío ya fue confirmado como entregado.')
                    return redirect('gestion_envios_transportista')
                
                # Crear confirmación de entrega
                ConfirmacionEntrega.objects.create(
                    envio=envio,
                    qr_escaneado=qr_data,
                    transportista=transportista,
                    observaciones=observaciones
                )
                
                # Confirmar entrega
                envio.confirmar_entrega()
                
                messages.success(request, f'Entrega del envío #{envio.id} confirmada exitosamente.')
                return redirect('gestion_envios_transportista')
            else:
                messages.error(request, 'Código QR inválido.')
                
        except Envio.DoesNotExist:
            messages.error(request, 'El código QR escaneado no corresponde a ningún envío.')
        except Exception as e:
            messages.error(request, f'Error al procesar el QR: {str(e)}')
    
    return render(request, 'escanear_qr_entrega.html')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def gestion_transportistas(request):
    """Vista para administrar transportistas (solo admin)"""
    if request.method == 'POST':
        username = request.POST.get('username')
        telefono = request.POST.get('telefono')
        vehiculo = request.POST.get('vehiculo')
        patente = request.POST.get('patente')
        
        try:
            user = User.objects.get(username=username)
            # Agregar al grupo transportista
            group, created = Group.objects.get_or_create(name='transportista')
            user.groups.add(group)
            
            # Crear perfil de transportista
            transportista, created = Transportista.objects.get_or_create(
                usuario=user,
                defaults={
                    'telefono': telefono,
                    'vehiculo': vehiculo,
                    'patente': patente
                }
            )
            
            if not created:
                transportista.telefono = telefono
                transportista.vehiculo = vehiculo
                transportista.patente = patente
                transportista.save()
            
            messages.success(request, f'Transportista {username} actualizado correctamente.')
            
        except User.DoesNotExist:
            messages.error(request, f'El usuario {username} no existe.')
        
        return redirect('gestion_transportistas')
    
    transportistas = Transportista.objects.all()
    context = {
        'transportistas': transportistas,
        'users_disponibles': User.objects.all()
    }
    return render(request, 'gestion_transportistas.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def asignar_envio_transportista(request, envio_id):
    """Asignar un envío a un transportista"""
    envio = get_object_or_404(Envio, id=envio_id)
    
    if request.method == 'POST':
        transportista_id = request.POST.get('transportista_id')
        transportista = get_object_or_404(Transportista, id=transportista_id)
        
        envio.transportista = transportista
        envio.estado = 'asignado'
        envio.fecha_asignacion = timezone.now()
        envio.save()
        
        # Generar QR para el envío
        envio.generar_qr_code()
        
        messages.success(request, f'Envío #{envio.id} asignado a {transportista.usuario.username}')
        return redirect('gestion_envios')
    
    transportistas = Transportista.objects.filter(activo=True)
    context = {
        'envio': envio,
        'transportistas': transportistas,
    }
    return render(request, 'asignar_envio.html', context)


# ==================== VISTAS DE UBER API ====================

@csrf_exempt
def uber_webhook(request):
    """Webhook para recibir eventos de Uber"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    try:
        from .uber_integration import procesar_webhook_uber
        from .models import Envio
        
        webhook_data = json.loads(request.body)
        resultado = procesar_webhook_uber(webhook_data)
        
        if resultado['success']:
            # Actualizar el envío basado en el evento
            delivery_id = resultado.get('delivery_id')
            accion = resultado.get('action')
            
            if delivery_id:
                try:
                    envio = Envio.objects.get(uber_delivery_id=delivery_id)
                    
                    if accion == 'actualizar_estado':
                        uber_status = webhook_data.get('status')
                        from .uber_integration import UberIntegration
                        uber = UberIntegration()
                        nuevo_estado = uber.mapear_estado_uber(uber_status)
                        envio.estado = nuevo_estado
                        envio.uber_status = uber_status
                        envio.save()
                        
                    elif accion == 'completar':
                        envio.estado = 'entregado'
                        envio.fecha_entrega = timezone.now()
                        envio.save()
                        
                    elif accion == 'cancelar':
                        envio.estado = 'cancelado'
                        envio.save()
                        
                except Envio.DoesNotExist:
                    logger.warning(f"Envío con Uber delivery ID {delivery_id} no encontrado")
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Error en webhook de Uber: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def uber_crear_delivery(request, envio_id):
    """Crear un delivery en Uber para un envío existente"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'No tienes permisos'}, status=403)
    
    try:
        from .uber_integration import UberIntegration
        from .models import Envio, Pedido
        
        envio = Envio.objects.get(id=envio_id)
        pedido = envio.pedido
        
        # Verificar que el envío no tenga ya un delivery de Uber
        if envio.uber_delivery_id:
            return JsonResponse({'success': False, 'error': 'Este envío ya tiene un delivery de Uber'})
        
        # Obtener datos del pedido para el delivery
        pickup_address = "Av. Nestor Kirchner 6770, Formosa, Argentina"  # Dirección de la empresa
        dropoff_address = envio.direccion_entrega
        
        # Datos de contacto
        pickup_name = "Distribuidora Gigante"
        pickup_phone = "+543705262361"
        dropoff_name = pedido.usuario.get_full_name() or pedido.usuario.username
        dropoff_phone = pedido.usuario.perfil.telefono if hasattr(pedido.usuario, 'perfil') else ""
        
        # Coordenadas (si están disponibles en el perfil)
        pickup_latitude = -26.1849  # Formosa, Argentina (aproximado)
        pickup_longitude = -58.1731
        dropoff_latitude = None
        dropoff_longitude = None
        
        # Crear el delivery
        uber = UberIntegration()
        resultado = uber.crear_delivery(
            pickup_address=pickup_address,
            dropoff_address=dropoff_address,
            pickup_name=pickup_name,
            pickup_phone=pickup_phone,
            dropoff_name=dropoff_name,
            dropoff_phone=dropoff_phone,
            pickup_latitude=pickup_latitude,
            pickup_longitude=pickup_longitude,
            dropoff_latitude=dropoff_latitude,
            dropoff_longitude=dropoff_longitude
        )
        
        if resultado['success']:
            # Actualizar el envío con los datos de Uber
            delivery_data = resultado['data']
            envio.uber_delivery_id = delivery_data.get('id')
            envio.uber_status = delivery_data.get('status')
            envio.tipo_transporte = 'uber'
            envio.estado = 'asignado'
            envio.fecha_asignacion = timezone.now()
            envio.save()
            
            return JsonResponse({
                'success': True,
                'delivery_id': envio.uber_delivery_id,
                'status': envio.uber_status,
                'message': 'Delivery de Uber creado exitosamente'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': resultado.get('error', 'Error desconocido al crear delivery')
            })
            
    except Envio.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Envío no encontrado'}, status=404)
    except Exception as e:
        logger.error(f"Error al crear delivery de Uber: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def uber_estado_delivery(request, delivery_id):
    """Obtener el estado actual de un delivery de Uber"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'No tienes permisos'}, status=403)
    
    try:
        from .uber_integration import UberIntegration
        
        uber = UberIntegration()
        resultado = uber.obtener_delivery(delivery_id)
        
        if resultado['success']:
            return JsonResponse({
                'success': True,
                'data': resultado['data']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': resultado.get('error', 'Error desconocido')
            })
            
    except Exception as e:
        logger.error(f"Error al obtener estado de delivery: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def uber_cancelar_delivery(request, delivery_id):
    """Cancelar un delivery de Uber"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'No tienes permisos'}, status=403)
    
    try:
        from .uber_integration import UberIntegration
        from .models import Envio
        
        # Buscar el envío asociado
        envio = Envio.objects.get(uber_delivery_id=delivery_id)
        
        uber = UberIntegration()
        resultado = uber.cancelar_delivery(delivery_id)
        
        if resultado['success']:
            # Actualizar el estado del envío
            envio.estado = 'cancelado'
            envio.uber_status = 'canceled'
            envio.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Delivery cancelado exitosamente'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': resultado.get('error', 'Error desconocido al cancelar delivery')
            })
            
    except Envio.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Envío no encontrado'}, status=404)
    except Exception as e:
        logger.error(f"Error al cancelar delivery: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)