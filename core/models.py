from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.contrib.auth.models import Group
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.conf import settings
from django.dispatch import receiver
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
from location_field.models.plain import PlainLocationField
from colorfield.fields import ColorField
from django_ckeditor_5.fields import CKEditor5Field
from django.db.models import Sum
import datetime
from .utils import *
import sys

def up_doc(instance, filename):
	return "docs/" + filename

def up_img(instance, filename):
	return "productos/" + filename

def up_pdf(instance, filename):
	return "pdf/" + filename

class CargaArchivo(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    fecha = models.DateTimeField(default=timezone.now)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Carga #{self.id} - {self.fecha.strftime('%d/%m/%Y %H:%M')}"

class Cart(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="Carrito")
	products = models.ManyToManyField('Product', through='CartItem', verbose_name="Productos")


	class Meta:
		verbose_name = 'Carrito del usuario'
		verbose_name_plural = 'Carrito de:'

	def get_total_quantity(self):
		total_quantity = 0
		for item in self.cartitem_set.all():
			total_quantity += item.quantity
		return total_quantity

	def __str__(self):
		return "Carrito de {}".format(self.user)

class CarruselImages(models.Model):

	COLOR_PALETTE = [
		("#FFFFFF", "white", ),
		("#000000", "black", ),
	]

	titulo = models.CharField(max_length=200)
	imagen = models.ImageField(upload_to='', default='default_image.png')
	texto = models.TextField(null=True, blank=True)
	color_texto = ColorField(samples=COLOR_PALETTE, default="#FFFFFF")
	color_fondo = ColorField(samples=COLOR_PALETTE, default="#000000")

	class Meta:
		verbose_name = 'Flayer/Imagen'
		verbose_name_plural = 'Cartel Carrousel'
	def __str__(self):
		return self.titulo


class Pedido(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('procesando', 'Procesando'),
        ('entregado', 'Entregado'),
        ('cancelado', 'Cancelado'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Usuario")
    fecha_pedido = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Pedido")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente', verbose_name="Estado")
    total_cantidad = models.PositiveIntegerField(default=0, verbose_name="Total de Cantidad")
    total_precio = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Total de Precio")
    pagado = models.BooleanField(default=False)
    vendedor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
								 related_name='ventas',
								 limit_choices_to=Q(groups__name="vendedor") | Q(groups__name="admin"), help_text="Vendedor asignado al pedido")
    
    # Campos de envío
    opcion_envio = models.ForeignKey('OpcionEnvio', on_delete=models.SET_NULL, null=True, blank=True, 
                                   verbose_name="Opción de envío")
    costo_envio = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Costo de envío")

    class Meta:
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'

    def __str__(self):
        return f"Pedido #{self.id} - {self.estado}"

    def actualizar_pedido(self):
        # Obtiene todos los detalles del pedido
        detalles_pedido = DetallePedido.objects.filter(pedido=self)

        # Actualiza el total de cantidad y total de precio usando agregaciones
        self.total_cantidad = detalles_pedido.aggregate(Sum('cantidad'))['cantidad__sum'] or 0
        self.total_precio = detalles_pedido.aggregate(Sum('subtotal'))['subtotal__sum'] or 0

        # Guarda los cambios en el pedido
        self.save()

class OpcionEnvio(models.Model):
    TIPO_ENVIO_CHOICES = [
        ('retiro_tienda', 'Retiro en Tienda'),
        ('envio_domicilio', 'Envío a Domicilio'),
        ('envio_gratis', 'Envío Gratis'),
        ('retiro_sucursal', 'Retiro en Sucursal'),
    ]
    
    tipo = models.CharField(max_length=20, choices=TIPO_ENVIO_CHOICES, default='retiro_tienda', 
                          verbose_name="Tipo de envío")
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la opción")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    costo = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Costo")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    tiempo_entrega = models.CharField(max_length=50, blank=True, verbose_name="Tiempo de entrega")
    
    class Meta:
        verbose_name = 'Opción de Envío'
        verbose_name_plural = 'Opciones de Envío'
        
    def __str__(self):
        return f"{self.nombre} - ${self.costo}"

class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, related_name='detalles_pedido', on_delete=models.CASCADE)
    producto = models.ForeignKey('Product', on_delete=models.CASCADE, verbose_name="Producto")
    cantidad = models.PositiveIntegerField(default=1, verbose_name="Cantidad")
    subtotal = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Subtotal")

    class Meta:
        verbose_name = 'Detalle de Pedido'
        verbose_name_plural = 'Detalles de Pedido'

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, verbose_name="Carrito")
    product = models.ForeignKey('Product', on_delete=models.CASCADE, verbose_name="Producto")
    pedido = models.ForeignKey(Pedido, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Pedido")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Cantidad")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Producto en Carrito'
        verbose_name_plural = 'Productos en Carrito'


class MainCategory(models.Model):
    nombre = models.CharField(max_length=200)
    mostrar = models.BooleanField(default=True)

    @staticmethod
    def get_all_categories():
       return Category.objects.all()

    class Meta:
        verbose_name = 'Categoria/Rubros'
        verbose_name_plural = 'Categorias/Rubros de Productos'

    def __str__(self):
        return self.nombre

class Category(models.Model):
	nombre = models.CharField(max_length=200)
	main = models.ForeignKey("MainCategory", on_delete=models.CASCADE, blank=True, null=True)

	class Meta:
		verbose_name = 'SubCategoria'
		verbose_name_plural = 'SubCategoria de Productos'

	def __str__(self):
		return self.nombre

class Contacto(models.Model):
	nombre = models.CharField(max_length=200)
	correo = models.EmailField(null=True, blank=True)
	telefono = models.CharField(max_length=12)
	mensaje = CKEditor5Field('Text', config_name='extends')
	fecha = models.DateTimeField(auto_now_add=True)

	class Meta:
		verbose_name = "Mensaje"
		verbose_name_plural = "Mensajes de Contacto"

	def __str__(self):
		return "{a}: {b}".format(a=self.correo, b=self.fecha)

class Ubicacion(models.Model):
	nombre = models.CharField(max_length=200)
	telefono = models.CharField(max_length=12)
	ubicacion = PlainLocationField(based_fields=['Formosa'], zoom=14)

	class Meta:
		verbose_name = "Ubicacion"
		verbose_name_plural = "Ubicaciones"

	def __str__(self):
		return "{a}: {b}".format(a=self.nombre, b=self.telefono)


class Product(models.Model):
	nombre = models.CharField(max_length=100)
	descripcion = CKEditor5Field('Descripcion', config_name='extends', null=True)
	precio = models.DecimalField(max_digits=8, decimal_places=2, default=0)
	imagen1 = models.ImageField(upload_to='', default='default_image.png')
	imagen2 = models.ImageField(upload_to='', default='default_image.png')
	imagenurl = models.URLField(max_length=20000, null=True, blank=True)
	stock = models.PositiveIntegerField(default=0, null=True)
	categoria = models.ForeignKey(Category, on_delete=models.CASCADE, blank=True, null=True, related_name="categoria")
	marca = models.CharField(max_length=200, null=True, blank=True)
	numero = models.CharField(max_length=200, null=True, blank=True)
	unidad_x_pack = models.PositiveIntegerField(default=0, blank=True)
	precio_m = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, default=0)
	carga = models.ForeignKey(CargaArchivo, on_delete=models.SET_NULL, null=True, blank=True, related_name='actualizado')
	contador_clicks = models.PositiveIntegerField(default=0)
	contador_carrito = models.PositiveIntegerField(default=0)
	destacado = models.BooleanField(default=False, verbose_name="Producto Destacado")

	class Meta:
		verbose_name = 'Producto'
		verbose_name_plural = 'Productos'

	def __str__(self):
		return "{}".format(self.nombre)

	def save(self, *args, **kwargs):
		self.get_marca()
		output_size = (400, 269)
		output_thumb = BytesIO()
		super().save(*args, **kwargs)
		for imagen in [self.imagen1, self.imagen2]:
			if imagen and os.path.exists(imagen.path):
				with Image.open(imagen.path) as img:
					ancho, alto = img.size
					if ancho > alto:
						nuevo_alto = 900
						nuevo_ancho = int((ancho/alto) * nuevo_alto)
						img = img.resize((nuevo_ancho, nuevo_alto))
						img.save(imagen.path)

					elif alto > ancho:
						nuevo_ancho = 900
						nuevo_alto = int((alto/ancho) * nuevo_ancho )
						img = img.resize((nuevo_ancho, nuevo_alto))
						img.save(imagen.path)
					else:
						img.thumbnail((900, 900))
						img.save(imagen.path)

				with Image.open(imagen.path) as img:
					ancho, alto = img.size
					if ancho > alto:
						left = (ancho - alto) / 2
						top = 0
						right = (ancho + alto) / 2
						bottom = alto
					else:
						left = 0
						top = (alto - ancho) / 2
						right = ancho
						bottom = (alto + ancho) / 2

					img = img.crop((left, top, right, bottom))
					img.save(imagen.path)


	def buscar_imagen(self, q, engine="google", result=0):
		imagen1 = self.imagen1.name.split('.')[0]
		imagen2 = self.imagen2.name.split('.')[0]

		if imagen1 == "default_image" and imagen2 == "default_image":
			search = SIE(sch_engine=engine)
			try:
				# self.imagenurl = search.get_url_img(params, result)
				self.imagenurl = search.get(q, result)

			except Exception as e:
				print("Error al buscar imagen: {}".format(e))
				pass

	def get_marca(self):
		art = ["LA", "LAS", "lOS", "EL", "DON"]
		if self.marca == None or self.marca == "nan":
			palabras = self.nombre.split()
			for palabra in palabras:
				if palabra in art:
					i = palabras.index(palabra)
					j = palabras.index(palabra) + 1
					self.marca = "{a} {b}".format(a=palabras[i], b=palabras[j])
				else:
					if len(palabras) > 4:
						self.marca = "{a} {b}".format(a=palabras[0], b=palabras[1])
					else:
						self.marca = palabras[0]



	def precio_final(self):
		if self.oferta:
			descuento = self.precio * self.descuento / 100
			return self.precio - descuento
		else:
			return self.precio

	def __str__(self):
		return self.nombre

class Oferta(models.Model):
    TIPO_OFERTA_CHOICES = [
        ('descuento', 'Descuento Porcentual'),
        ('combinar', 'Combinar con Producto'),
        ('multiplicidad', '2x1, 3x2, etc.'),
    ]
    
    TIPO_MULTIPLICIDAD_CHOICES = [
        ('2x1', '2x1 - Lleva 2, paga 1'),
        ('3x2', '3x2 - Lleva 3, paga 2'),
        ('4x3', '4x3 - Lleva 4, paga 3'),
        ('5x4', '5x4 - Lleva 5, paga 4'),
    ]
    
    producto = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="en_oferta")
    tipo_oferta = models.CharField(max_length=20, choices=TIPO_OFERTA_CHOICES, default='descuento')
    
    # Campos para descuento porcentual
    descuento = models.PositiveIntegerField(default=0, verbose_name="Descuento de oferta")
    
    # Campos para combinar productos
    producto_combinar = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, 
                                        related_name="combinado_con", verbose_name="Producto a combinar")
    monto_combinar = models.DecimalField(max_digits=10, decimal_places=2, default=0, 
                                        verbose_name="Monto del combo", blank=True, null=True)
    
    # Campos para multiplicidad
    tipo_multiplicidad = models.CharField(max_length=10, choices=TIPO_MULTIPLICIDAD_CHOICES, 
                                         blank=True, null=True, verbose_name="Tipo de multiplicidad")
    
    # Campo para duración de la oferta en días
    duracion_dias = models.PositiveIntegerField(default=30, verbose_name="Duración en días", 
                                                help_text="Duración de la oferta en días desde su creación")
    
    # Campo para stock limitado de ofertas
    stock_oferta = models.PositiveIntegerField(default=0, verbose_name="Stock de la oferta", 
                                                help_text="Número de unidades disponibles para esta oferta. 0 = ilimitado")
    
    # Campo para unidades vendidas de la oferta
    unidades_vendidas = models.PositiveIntegerField(default=0, verbose_name="Unidades vendidas")
    
    # Campos heredados del modelo original
    precio_anterior = models.DecimalField(default=0, max_digits=8, decimal_places=0)
    precio_final = models.DecimalField(default=0, max_digits=8, decimal_places=0)
    activa = models.BooleanField(default=True, verbose_name="Oferta activa")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        verbose_name = "Oferta"
        verbose_name_plural = "Ofertas de Productos"

    def __str__(self):
        if self.tipo_oferta == 'descuento':
            return f"{self.producto.nombre} - {self.descuento}% OFF"
        elif self.tipo_oferta == 'combinar' and self.producto_combinar:
            return f"Combo: {self.producto.nombre} + {self.producto_combinar.nombre}"
        elif self.tipo_oferta == 'multiplicidad':
            return f"{self.producto.nombre} - {self.get_tipo_multiplicidad_display()}"
        return f"{self.producto.nombre} - Oferta"

    def esta_vigente(self):
        """Verifica si la oferta está vigente según su duración"""
        if not self.activa:
            return False
        
        from django.utils import timezone
        import datetime
        
        fecha_limite = self.fecha_creacion + datetime.timedelta(days=self.duracion_dias)
        return timezone.now() <= fecha_limite
    
    def dias_restantes(self):
        """Retorna los días restantes de la oferta"""
        if not self.esta_vigente():
            return 0
            
        from django.utils import timezone
        import datetime
        
        fecha_limite = self.fecha_creacion + datetime.timedelta(days=self.duracion_dias)
        delta = fecha_limite - timezone.now()
        return max(0, delta.days)

    def verificar_y_desactivar_si_expiro(self):
        """Verifica si la oferta ha expirado y la desactiva automáticamente"""
        if self.activa:
            from django.utils import timezone
            import datetime
            
            fecha_limite = self.fecha_creacion + datetime.timedelta(days=self.duracion_dias)
            if timezone.now() > fecha_limite:
                self.activa = False
                self.save()
                return True  # Se desactivó
        return False  # No se desactivó (ya estaba inactiva o no expiró)

    def tiene_stock_disponible(self):
        """Verifica si hay stock disponible para la oferta"""
        if self.stock_oferta == 0:  # 0 significa ilimitado
            return True
        return self.unidades_vendidas < self.stock_oferta
    
    def stock_restante(self):
        """Retorna el stock restante de la oferta"""
        if self.stock_oferta == 0:  # 0 significa ilimitado
            return 999  # Representa ilimitado
        return max(0, self.stock_oferta - self.unidades_vendidas)
    
    def incrementar_venta(self, cantidad=1):
        """Incrementa las unidades vendidas de la oferta"""
        self.unidades_vendidas += cantidad
        self.save()

    @classmethod
    def desactivar_ofertas_expiradas(cls):
        """Desactiva automáticamente todas las ofertas que han expirado"""
        ofertas_expiradas = Oferta.objects.filter(activa=True)
        count = 0
        
        for oferta in ofertas_expiradas:
            if oferta.verificar_y_desactivar_si_expiro():
                count += 1
        
        return count

    def save(self, **kwargs):
        self.precio_anterior = self.producto.precio
        
        if self.tipo_oferta == 'descuento' and self.descuento > 0:
            descuento = self.producto.precio * self.descuento / 100
            self.precio_final = self.producto.precio - descuento
        elif self.tipo_oferta == 'combinar' and self.monto_combinar > 0:
            self.precio_final = self.monto_combinar
        elif self.tipo_oferta == 'multiplicidad':
            # Para ofertas de multiplicidad, el precio final se calcula dinámicamente
            if self.tipo_multiplicidad == '2x1':
                self.precio_final = self.producto.precio  # Paga 1 de 2
            elif self.tipo_multiplicidad == '3x2':
                self.precio_final = self.producto.precio * 2 / 3  # Paga 2 de 3
            elif self.tipo_multiplicidad == '4x3':
                self.precio_final = self.producto.precio * 3 / 4  # Paga 3 de 4
            elif self.tipo_multiplicidad == '5x4':
                self.precio_final = self.producto.precio * 4 / 5  # Paga 4 de 5
        else:
            self.precio_final = self.producto.precio

        super(Oferta, self).save()

class MercadoPagoCuenta(models.Model):
        nombre = models.CharField(max_length=50, null=True, blank=True)
        public_key = models.CharField(max_length=200)
        access_token = models.CharField(max_length=200)
        client_secret = models.CharField(max_length=100, null=True, blank=True)
        activa = models.BooleanField(default=False)

        class Meta:
                verbose_name = 'Cuenta de cobro'
                verbose_name_plural = 'Cuentas MercadoPago'

        def __str__(self):
                return ("%s" % self.nombre)

class Promo(models.Model):
    titulo = models.CharField(max_length=200)
    fecha = models.DateTimeField(auto_now_add=True)
    vigencia = models.DateTimeField(null=True, blank=True)
    producto = models.ForeignKey(Product, on_delete=models.CASCADE)
    base = models.TextField(null=True, blank=True)
    precio = models.DecimalField(default=0, max_digits=8, decimal_places=0)

    class Meta:
        verbose_name = 'Promociones'
        verbose_name_plural = 'Promos'


class GrillaExcel(models.Model):
	archivo = models.FileField(upload_to=up_doc)
	json_data = models.JSONField(null=True, blank=True)
	actualizado = models.DateTimeField(auto_now_add=True)

	class Meta:
		verbose_name = "Planilla Excel/CSV"
		verbose_name_plural = "Plantillas Excel/CSV"

	def __str__(self):
		return self.archivo.name.split('.')[0].upper()

	def get_titles_columns(self):
		file = LoadExcel(self.archivo.path)
		titles = file.get_title()
		return titles

	def get_size(self):
		file = LoadExcel(self.archivo.path)
		return file.size

	def get_data_json(self):
		file = LoadExcel(self.archivo.path)
		json = {}
		for item in self.json_data:
			colum_name = self.json_data[item][0]
			if colum_name == "Ninguno":
				json[item] = None
			else:
				json[item] = file.get_data(colum_name)

		return json

class Perfil(models.Model):
    TIPOS_USUARIO = [
        ('cliente', 'Cliente'),
        ('vendedor', 'Vendedor'),
        ('admin', 'Administrador'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil", verbose_name="User")
    imagen = models.ImageField(default='/static/img/usuario_defecto.webp', upload_to='usuarios/', verbose_name='Imagen de perfil', null=True, blank=True)
    direccion = models.CharField(max_length=150, null=True, blank=True, verbose_name='Dirección')
    localidad = models.CharField(max_length=150, null=True, blank=True, verbose_name='Barrio/Cuidad')
    ubicacion = models.CharField(max_length=100, null=True, blank=True, verbose_name='Ubicación GPS (coordenadas)')
    telefono = models.CharField(max_length=50, null=True, blank=True, verbose_name='Teléfono')
    vendedor_asignado = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clientes_asignados",
        limit_choices_to={"groups__name": "vendedor"}
    )
    tipo_usuario = models.CharField(max_length=20, choices=TIPOS_USUARIO, default='cliente')
    nombre = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nombre Completo")
    google_id = models.CharField(max_length=100, null=True, blank=True, verbose_name='Google ID')
    es_oauth = models.BooleanField(default=False, verbose_name='Usuario OAuth')

    def get_clientes_asignados(self):
        """Obtiene todos los clientes asignados a este vendedor"""
        return ClienteVendedor.objects.filter(vendedor=self).select_related('cliente__user')

    def get_vendedor_asignado(self):
        """Obtiene el vendedor asignado a este cliente"""
        try:
            return ClienteVendedor.objects.get(cliente=self).vendedor
        except ClienteVendedor.DoesNotExist:
            return None

    @property
    def vendedor_asignado(self):
        """Obtiene el vendedor asignado a través del modelo ClienteVendedor"""
        try:
            asignacion = ClienteVendedor.objects.get(cliente=self)
            return asignacion.vendedor.user
        except ClienteVendedor.DoesNotExist:
            return None

    def obtener_nombre_mostrar(self):
        """
        Devuelve el nombre para mostrar, o "Sin perfil" si no hay información
        """
        if self.nombre:
            return self.nombre
        elif self.user.get_full_name():
            return self.user.get_full_name()
        elif self.user.first_name:
            return self.user.first_name
        else:
            return "Perfil Incompleto"

    class Meta:
        verbose_name = 'perfil'
        verbose_name_plural = 'perfiles'
        ordering = ['-id']

    def __str__(self):
        return self.user.username

# Función para manejar la creación o actualización del perfil y asignación de grupos
@receiver(post_save, sender=User)
def manage_user_profile(sender, instance, created, **kwargs):
    """
    Maneja la creación o actualización del perfil y asigna grupos al usuario,
    evitando ciclos infinitos.
    """
    if created:
        # Crear perfil asociado al usuario recién creado
        Perfil.objects.create(user=instance)

    # Asignar grupo según el tipo de usuario
    try:
        nombre_grupo = "cliente"
        if instance.is_superuser:
            nombre_grupo = "admin"
        elif instance.is_staff:
            nombre_grupo = "vendedor"

        # Obtener o crear el grupo correspondiente
        grupo, _ = Group.objects.get_or_create(name=nombre_grupo)

        # Sobrescribir los grupos actuales del usuario
        instance.groups.set([grupo])

        # Desconectar la señal temporalmente para evitar ciclos infinitos
        post_save.disconnect(manage_user_profile, sender=User)

        # Guardar el perfil si existe
        if hasattr(instance, 'perfil'):
            instance.perfil.save()

        # Reconectar la señal después de guardar
        post_save.connect(manage_user_profile, sender=User)

    except Exception as e:
        # Loguea el error o maneja el fallo
        print(f"Error al gestionar el perfil o grupo del usuario: {e}")


# Dirección IP y número de visitas al sitio web
class Userip(models.Model):
    ip=models.CharField(verbose_name='Dirección IP',max_length=30)    #ip address
    count=models.IntegerField(verbose_name='Visitas',default=0) # Las visitas ip
    class Meta:
        verbose_name = 'Acceder a la información del usuario'
        verbose_name_plural = verbose_name
    def __str__(self):
        return self.ip

#Total de visitas al sitio web
class VisitNumber(models.Model):
    count=models.IntegerField(verbose_name='Total de visitas al sitio web',default=0) #Total de visitas al sitio web

    class Meta:
        verbose_name = 'Total de visitas al sitio web'
        verbose_name_plural = verbose_name

    def __str__(self):
        return str(self.count)

class DayNumber(models.Model):
    day=models.DateField(verbose_name='Fecha',default=timezone.now)
    count=models.IntegerField(verbose_name='Número de visitas al sitio web',default=0) #Total de visitas al sitio web

    class Meta:
        verbose_name = 'Estadísticas de visitas diarias al sitio web'
        verbose_name_plural = verbose_name

    def __str__(self):
        return str(self.day)


class ClienteVendedor(models.Model):
    cliente = models.ForeignKey(
        Perfil,
        on_delete=models.CASCADE,
        related_name="relaciones_vendedores"
    )
    vendedor = models.ForeignKey(
        Perfil,
        on_delete=models.CASCADE,
        related_name="clientes_relacionados"
    )
    fecha_asignacion = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Cliente/Vendedor"
        verbose_name_plural = 'Vendedores Asignados'

    def __str__(self):
        return f"{self.cliente} asignado a {self.vendedor}"

class OrdenCatalogo(models.Model):
    OPCIONES_ORDEN = [
        ('categoria', 'Por Categoría (A-Z)'),
        ('-categoria', 'Por Categoría (Z-A)'),
        ('marca', 'Por Marca (A-Z)'),
        ('-marca', 'Por Marca (Z-A)'),
        ('nombre', 'Por Nombre (A-Z)'),
        ('-nombre', 'Por Nombre (Z-A)'),
        ('precio', 'Por Precio (Menor a Mayor)'),
        ('-precio', 'Por Precio (Mayor a Menor)'),
        ('id', 'Por ID (Más Antiguo)'),
        ('-id', 'Por ID (Más Nuevo)'),
    ]

    campo_orden = models.CharField(
        max_length=20,
        choices=OPCIONES_ORDEN,
        default='categoria',
        verbose_name='Campo de Ordenamiento'
    )

    activo = models.BooleanField(default=True, verbose_name='Activo')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Orden del Catálogo'
        verbose_name_plural = 'Órdenes del Catálogo'

    def __str__(self):
        return f"Orden: {self.get_campo_orden_display()}"

    def save(self, *args, **kwargs):
        if self.activo:
            # Desactivar otras configuraciones activas
            OrdenCatalogo.objects.exclude(id=self.id).update(activo=False)
        super().save(*args, **kwargs)


class NotificacionAdmin(models.Model):
    """Sistema de notificaciones internas para administradores"""
    
    TIPO_NOTIFICACION = [
        ('pedido', 'Nuevo Pedido'),
        ('compra', 'Nueva Compra'),
        ('contacto', 'Mensaje de Contacto'),
        ('producto', 'Producto Agotado'),
        ('oferta', 'Nueva Oferta Creada'),
        ('usuario', 'Nuevo Usuario Registrado'),
        ('sistema', 'Alerta del Sistema'),
    ]
    
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_NOTIFICACION,
        verbose_name='Tipo de Notificación'
    )
    
    titulo = models.CharField(
        max_length=200,
        verbose_name='Título'
    )
    
    mensaje = models.TextField(
        verbose_name='Mensaje'
    )
    
    leido = models.BooleanField(
        default=False,
        verbose_name='Leído'
    )
    
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    
    fecha_lectura = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Lectura'
    )
    
    # Referencia al objeto relacionado (opcional)
    referencia_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='ID de Referencia'
    )
    
    referencia_tipo = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='Tipo de Referencia'
    )
    
    class Meta:
        verbose_name = 'Notificación Administrativa'
        verbose_name_plural = 'Notificaciones Administrativas'
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.get_tipo_display()}: {self.titulo}"
    
    def marcar_como_leido(self):
        """Marcar notificación como leída"""
        if not self.leido:
            self.leido = True
            self.fecha_lectura = timezone.now()
            self.save()
    
    @classmethod
    def crear_notificacion(cls, tipo, titulo, mensaje, referencia_id=None, referencia_tipo=None):
        """Crear nueva notificación"""
        return cls.objects.create(
            tipo=tipo,
            titulo=titulo,
            mensaje=mensaje,
            referencia_id=referencia_id,
            referencia_tipo=referencia_tipo
        )
    
    @classmethod
    def obtener_no_leidas(cls):
        """Obtener notificaciones no leídas"""
        return cls.objects.filter(leido=False)
    
    @classmethod
    def contar_no_leidas(cls):
        """Contar notificaciones no leídas"""
        return cls.objects.filter(leido=False).count()


# Modelos para Sistema de Transporte y Entregas
class Transportista(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="Usuario transportista")
    telefono = models.CharField(max_length=20, verbose_name="Teléfono de contacto")
    vehiculo = models.CharField(max_length=100, verbose_name="Tipo de vehículo")
    patente = models.CharField(max_length=10, verbose_name="Patente del vehículo")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    
    class Meta:
        verbose_name = 'Transportista'
        verbose_name_plural = 'Transportistas'
    
    def __str__(self):
        return f"{self.usuario.username} - {self.vehiculo}"


class Envio(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de asignación'),
        ('asignado', 'Asignado a transportista'),
        ('en_transito', 'En tránsito'),
        ('entregado', 'Entregado'),
        ('cancelado', 'Cancelado'),
    ]
    
    TIPO_TRANSPORTE_CHOICES = [
        ('local', 'Transportista Local'),
        ('uber', 'Uber Direct'),
    ]
    
    pedido = models.OneToOneField('Pedido', on_delete=models.CASCADE, verbose_name="Pedido asociado")
    transportista = models.ForeignKey('Transportista', on_delete=models.SET_NULL, null=True, blank=True, 
                                   verbose_name="Transportista asignado")
    tipo_transporte = models.CharField(max_length=20, choices=TIPO_TRANSPORTE_CHOICES, default='local',
                                      verbose_name="Tipo de transporte")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente', 
                             verbose_name="Estado del envío")
    qr_code = models.CharField(max_length=255, unique=True, verbose_name="Código QR")
    fecha_asignacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de asignación")
    fecha_entrega = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de entrega")
    direccion_entrega = models.TextField(verbose_name="Dirección de entrega")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    
    # Campos para integración con Uber
    uber_delivery_id = models.CharField(max_length=255, null=True, blank=True, 
                                       verbose_name="ID de delivery en Uber")
    uber_status = models.CharField(max_length=50, null=True, blank=True,
                                  verbose_name="Estado en Uber")
    uber_tracking_url = models.URLField(null=True, blank=True,
                                       verbose_name="URL de tracking de Uber")
    uber_quote_id = models.CharField(max_length=255, null=True, blank=True,
                                    verbose_name="ID de cotización en Uber")
    uber_costo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                     verbose_name="Costo del delivery Uber")
    
    class Meta:
        verbose_name = 'Envío'
        verbose_name_plural = 'Envíos'
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"Envío #{self.id} - Pedido #{self.pedido.id}"
    
    def generar_qr_code(self):
        """Generar código QR único para el envío"""
        import uuid
        import qrcode
        from io import BytesIO
        import base64
        
        if not self.qr_code:
            # Generar código único
            self.qr_code = f"ENVIO-{self.id}-{uuid.uuid4().hex[:8].upper()}"
            self.save()
        
        # Generar imagen QR
        qr_data = f"{self.qr_code}|{self.pedido.id}|{self.pedido.user.id}"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_image = base64.b64encode(buffer.getvalue()).decode()
        
        return qr_image
    
    def confirmar_entrega(self):
        """Confirmar entrega del envío"""
        self.estado = 'entregado'
        self.fecha_entrega = timezone.now()
        self.pedido.estado = 'entregado'
        self.pedido.save()
        self.save()


class ConfirmacionEntrega(models.Model):
    envio = models.ForeignKey('Envio', on_delete=models.CASCADE, verbose_name="Envío confirmado")
    fecha_confirmacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de confirmación")
    qr_escaneado = models.CharField(max_length=255, verbose_name="QR escaneado")
    transportista = models.ForeignKey('Transportista', on_delete=models.CASCADE, verbose_name="Transportista que confirmó")
    ubicacion_gps = models.CharField(max_length=255, blank=True, verbose_name="Ubicación GPS")
    foto_entrega = models.ImageField(upload_to='entregas/', blank=True, verbose_name="Foto de entrega")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones de la entrega")
    
    class Meta:
        verbose_name = 'Confirmación de Entrega'
        verbose_name_plural = 'Confirmaciones de Entrega'
        ordering = ['-fecha_confirmacion']
    
    def __str__(self):
        return f"Confirmación envío #{self.envio.id}"
