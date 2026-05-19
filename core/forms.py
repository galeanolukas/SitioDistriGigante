from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import User, Group
from django.contrib import messages
from .models import Perfil  # Asegúrate de importar tu modelo Perfil
from .models import *
from django.forms import ImageField
from django.forms.widgets import TextInput
from colorfield.fields import ColorField
from django_ckeditor_5.widgets import CKEditor5Widget
from captcha.fields import ReCaptchaField
from captcha.widgets import ReCaptchaV2Checkbox

class UserForm(UserCreationForm):
    grupos = forms.ModelChoiceField(label='Selec un Grupo', required=True, queryset=Group.objects.all(), initial=0)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'grupos']

    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({'class':'w3-input w3-border w3-round-large'})
        self.fields["email"].widget.attrs.update({'class':'w3-input w3-border w3-round-large'})
        self.fields["password1"].widget.attrs.update({'class':'w3-input w3-border w3-round-large'})
        self.fields["password2"].widget.attrs.update({'class':'w3-input w3-border w3-round-large'})
        self.fields["grupos"].widget.attrs.update({'class':'w3-select w3-border w3-round-large'})

    def save(self, commit=True):
        user = super(UserForm, self).save(commit)
        user.save()
        user.groups.clear()
        user.groups.add(self.cleaned_data.get('grupos'))
        return user

class RegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'w3-input w3-border w3-round-large'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'w3-input w3-border w3-round-large'}))
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox(attrs={'class': 'w3-margin-top'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            'email': forms.EmailInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Las contraseñas no coinciden.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data['password']
        user.set_password(password)

        if commit:
            user.save()

        return user

class SuperuserCreationForm(UserCreationForm):
    is_superuser = forms.BooleanField(
        label='Superusuario',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'w3-check'})
    )

    class Meta(UserCreationForm.Meta):
        fields = ('username', 'email', 'password1', 'password2', 'is_superuser')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            'email': forms.EmailInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            'password1': forms.PasswordInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            'password2': forms.PasswordInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        user.is_superuser = self.cleaned_data.get('is_superuser', False)

        if commit:
            user.save()

        return user


class UserEditForm(forms.ModelForm):
    password = forms.CharField(
        label='Nueva contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'w3-input w3-border w3-round-large',
            'placeholder': 'Dejar vacío para mantener la contraseña actual'
        }),
        required=False,
        help_text='Ingrese solo si desea cambiar la contraseña'
    )

    confirm_password = forms.CharField(
        label='Confirmar nueva contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'w3-input w3-border w3-round-large',
            'placeholder': 'Repita la nueva contraseña'
        }),
        required=False,
        help_text='Confirme la nueva contraseña'
    )

    current_password_info = forms.CharField(
        label='Contraseña actual',
        widget=forms.TextInput(attrs={
            'class': 'w3-input w3-border w3-round-large',
            'readonly': 'readonly',
            'style': 'background-color: #f5f5f5;'
        }),
        required=False,
        initial='******** (encriptada)'
    )

    is_superuser = forms.BooleanField(
        label='Superusuario',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'w3-check'})
    )

    grupos = forms.ModelChoiceField(
        label='Selecciona un Grupo',
        required=True,
        queryset=Group.objects.all(),
        widget=forms.Select(attrs={
            'class': 'w3-select w3-border w3-round-large',
            'onchange': 'actualizarTipoUsuario()'  # Opcional: JavaScript para feedback en tiempo real
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'current_password_info', 'password', 'confirm_password', 'is_superuser', 'grupos')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            'email': forms.EmailInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
        }

    def __init__(self, *args, **kwargs):
        super(UserEditForm, self).__init__(*args, **kwargs)

        # Establecer el grupo inicial si existe una instancia
        if self.instance and self.instance.pk:
            initial_group = self.instance.groups.first()
            if initial_group:
                self.fields['grupos'].initial = initial_group

            self.fields['current_password_info'].initial = '******** (contraseña encriptada - ingrese nueva solo para cambiar)'

            # Opcional: Mostrar el tipo_usuario actual en el formulario
            try:
                perfil = self.instance.perfil
                self.fields['grupos'].help_text = f'Tipo de usuario actual: {perfil.get_tipo_usuario_display()}'
            except Perfil.DoesNotExist:
                pass

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password or confirm_password:
            if password != confirm_password:
                raise forms.ValidationError('Las contraseñas no coinciden.')

            if password and len(password) < 8:
                raise forms.ValidationError('La contraseña debe tener al menos 8 caracteres.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        grupo = self.cleaned_data.get('grupos')

        # Solo actualizar la contraseña si se proporcionó una nueva
        if password:
            user.set_password(password)

        user.is_staff = self.cleaned_data.get('is_superuser', False)
        user.is_superuser = self.cleaned_data.get('is_superuser', False)

        # Manejar grupos
        user.groups.clear()
        if grupo:
            user.groups.add(grupo)

        if commit:
            # Si hay contraseña nueva, guardar todos los campos
            if password:
                user.save()
            else:
                user.save(update_fields=['username', 'email', 'is_staff', 'is_superuser'])

            # Actualizar grupos
            user.groups.set([grupo] if grupo else [])

            # ACTUALIZAR EL PERFIL DEL USUARIO según el grupo
            self.actualizar_perfil_usuario(user, grupo)

        return user

    def actualizar_perfil_usuario(self, user, grupo):
        """
        Actualiza el campo tipo_usuario del perfil basado en el grupo seleccionado
        """
        try:
            # Obtener o crear el perfil del usuario
            perfil, created = Perfil.objects.get_or_create(user=user)

            # Mapeo de grupos a tipos de usuario (ajusta según tus necesidades)
            mapeo_grupo_tipo = {
                'admin': 'admin',
                'vendedor': 'vendedor',
                'cliente': 'cliente',
                # Agrega más mapeos según tus grupos y tipos de usuario
            }

            # Determinar el tipo_usuario basado en el grupo
            if grupo and grupo.name.lower() in mapeo_grupo_tipo:
                perfil.tipo_usuario = mapeo_grupo_tipo[grupo.name.lower()]
                if perfil.tipo_usuario == 'vendedor' or perfil.tipo_usuario == 'admin':
                    user.is_staff = True
                    user.save()
            else:
                # Tipo por defecto si no hay coincidencia
                perfil.tipo_usuario = 'cliente'
                user.is_staff = False
                user.save()

            perfil.save()

        except Exception as e:
            # Manejar cualquier error en la actualización del perfil
            print(f"Error al actualizar perfil: {e}")

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['nombre', 'descripcion', 'precio', 'precio_m', 'marca', 'stock', 'numero', 'imagen1', 'imagen2', 'imagenurl', 'categoria', 'unidad_x_pack']
        widgets = {
            "descripcion": CKEditor5Widget(
                attrs={"class": "django_ckeditor_5 w3-input w3-border w3-round-large"},
                config_name="extends"
            ),
            "nombre": forms.TextInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            "precio": forms.NumberInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            "precio_m": forms.NumberInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            "marca": forms.TextInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            "stock": forms.NumberInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            "numero": forms.NumberInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            "imagen1": forms.FileInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            "imagen2": forms.FileInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            "imagenurl": forms.URLInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            "categoria": forms.Select(attrs={'class': 'w3-select w3-border w3-round-large'}),
            "unidad_x_pack": forms.NumberInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
        }

    def __init__(self, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        self.fields["descripcion"].required = False

class CartelForm(forms.ModelForm):
    class Meta:
        model = CarruselImages
        fields = ['titulo', 'imagen', 'texto', 'color_texto', 'color_fondo']
        widgets = {
            'color_texto': TextInput(attrs={'type': 'color', 'class': 'w3-input w3-border w3-round-large'}),
            "texto": CKEditor5Widget(
                attrs={"class": "django_ckeditor_5 w3-input w3-border w3-round-large"},
                config_name="extends"
            ),
            "titulo": forms.TextInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            "imagen": forms.FileInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            "color_fondo": TextInput(attrs={'type': 'color', 'class': 'w3-input w3-border w3-round-large'}),
        }

    def __init__(self, *args, **kwargs):
        super(CartelForm, self).__init__(*args, **kwargs)
        self.fields["texto"].required = False

class OfertaForm(forms.ModelForm):
    class Meta:
        model = Oferta
        fields = ['tipo_oferta', 'descuento', 'producto_combinar', 'monto_combinar', 'tipo_multiplicidad']
        widgets = {
            "tipo_oferta": forms.Select(attrs={'class': 'w3-select w3-border w3-round-large'}),
            "descuento": forms.NumberInput(attrs={'class': 'w3-input w3-border w3-round-large', 'min': '1', 'max': '100'}),
            "producto_combinar": forms.Select(attrs={'class': 'w3-select w3-border w3-round-large'}),
            "monto_combinar": forms.NumberInput(attrs={'class': 'w3-input w3-border w3-round-large', 'step': '0.01'}),
            "tipo_multiplicidad": forms.Select(attrs={'class': 'w3-select w3-border w3-round-large'}),
        }
    
    def __init__(self, *args, **kwargs):
        super(OfertaForm, self).__init__(*args, **kwargs)
        # Filtrar el campo de producto_combinar para excluir el producto actual
        if 'instance' in kwargs and kwargs['instance'] and kwargs['instance'].producto:
            producto_actual = kwargs['instance'].producto
            self.fields['producto_combinar'].queryset = Product.objects.exclude(id=producto_actual.id)
        
        # Hacer campos requeridos según el tipo de oferta
        self.fields['descuento'].required = False
        self.fields['producto_combinar'].required = False
        self.fields['monto_combinar'].required = False
        self.fields['tipo_multiplicidad'].required = False

class PerfilForm(forms.ModelForm):
    nombre = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
        required=False
    )

    class Meta:
        model = Perfil
        fields = ['nombre', 'direccion', 'localidad', 'ubicacion', 'telefono', 'imagen']
        labels = {
            "localidad": "Localidad/Cuidad",
            "telefono": "Tel/Celular",
            "nombre": "Nombre y Apellido",
            "ubicacion": "Ubicación GPS (coordenadas)"
        }
        widgets = {
            "direccion": forms.TextInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            "localidad": forms.TextInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            "ubicacion": forms.TextInput(attrs={'class': 'w3-input w3-border w3-round-large', 'readonly': True}),
            "telefono": forms.TextInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
            "imagen": forms.FileInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
        }

class CargarExcelForm(forms.ModelForm):
    class Meta:
        model = GrillaExcel
        fields = ['archivo']
        widgets = {
            "archivo": forms.FileInput(attrs={'class': 'w3-input w3-border w3-round-large'}),
        }

class UbicacionForm(forms.ModelForm):
    class Meta:
        model = Ubicacion
        fields = ['nombre', 'telefono', 'ubicacion']
        widgets = {
            "nombre": forms.TextInput(attrs={
                'class': 'w3-input w3-border w3-round-large',
                'placeholder': 'NOMBRE Y APELLIDO'
            }),
            "telefono": forms.TextInput(attrs={
                'class': 'w3-input w3-border w3-round-large',
                'placeholder': 'TU TELEFONO/CELULAR'
            }),
            "ubicacion": forms.TextInput(attrs={
                'class': 'w3-input w3-border w3-round-large',
                'value': '-26.18518513298023,-58.17475318908692'
            }),
        }

class IseConfigForm(forms.Form):
    CHOICES = (
        ('png', 'PNG'),
        ('jpg', 'JPG'),
        ('webp', 'WEBP'),
        ('gif', 'GIF')
    )
    LANGUAGES = (
        ('es', 'Español'),
        ('en', 'Ingles'),
        ('fr', 'Frances')
    )
    REGION = (
        ("es_ar", "Argentina"),
        ('es', 'España'),
        ('en', 'EEUU'),
        ('fr', 'Francia')
    )

    formato = forms.ChoiceField(
        choices=CHOICES,
        widget=forms.Select(attrs={'class': 'w3-select w3-border w3-round-large'})
    )
    ancho = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'w3-input w3-border w3-round-large'})
    )
    alto = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'w3-input w3-border w3-round-large'})
    )
    locale = forms.ChoiceField(
        choices=REGION,
        widget=forms.Select(attrs={'class': 'w3-select w3-border w3-round-large'})
    )
    lenguaje = forms.ChoiceField(
        choices=LANGUAGES,
        widget=forms.Select(attrs={'class': 'w3-select w3-border w3-round-large'})
    )
    marca = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'w3-check'})
    )
    descrip = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'w3-input w3-border w3-round-large'})
    )

class AgregarProductoForm(forms.Form):
    nuevo_producto = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'w3-input w3-border w3-round-large'})
    )
    nueva_cantidad_nuevo = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'w3-input w3-border w3-round-large'})
    )


class MercadoPagoCuentaForm(forms.ModelForm):
    class Meta:
        model = MercadoPagoCuenta
        fields = ['nombre', 'public_key', 'access_token', 'client_secret']
        widgets = {
            'public_key': forms.TextInput(attrs={
                'class': 'w3-input w3-border w3-round',
                'placeholder': 'PUB_KEY_... o cualquier formato'
            }),
            'access_token': forms.TextInput(attrs={
                'class': 'w3-input w3-border w3-round',
                'placeholder': 'APP_USR_... o cualquier formato'
            }),
            'client_secret': forms.TextInput(attrs={
                'class': 'w3-input w3-border w3-round',
                'placeholder': 'Tu client secret'
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'w3-input w3-border w3-round',
                'placeholder': 'Nombre descriptivo de la cuenta'
            })
        }
