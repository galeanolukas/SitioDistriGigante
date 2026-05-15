# models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django_ckeditor_5.fields import CKEditor5Field


class AssistantConfig(models.Model):
    """Configuración principal del asistente virtual"""

    ROLE_CHOICES = [
        ('customer_service', 'Servicio al Cliente'),
        ('sales', 'Asistente de Ventas'),
        ('technical', 'Soporte Técnico'),
        ('general', 'Asistente General'),
        ('custom', 'Personalizado'),
    ]

    AI_MODEL_CHOICES = [
        ('gpt-4', 'GPT-4'),
        ('gpt-3.5-turbo', 'GPT-3.5 Turbo'),
        ('claude-2', 'Claude 2'),
        ('llama-2', 'Llama 2'),
        ('custom', 'Modelo Personalizado'),
    ]

    name = models.CharField(
        max_length=100,
        default="Asistente Virtual",
        verbose_name="Nombre del Asistente"
    )

    role = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        default='customer_service',
        verbose_name="Rol del Asistente"
    )

    ai_model = models.CharField(
        max_length=50,
        choices=AI_MODEL_CHOICES,
        default='gpt-3.5-turbo',
        verbose_name="Modelo de IA"
    )

    custom_model_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Nombre del Modelo Personalizado"
    )

    system_prompt = CKEditor5Field('Text', config_name='extends')

    temperature = models.FloatField(
        default=0.7,
        verbose_name="Temperatura",
        help_text="Controla la creatividad (0.0 - 1.0)"
    )

    max_tokens = models.IntegerField(
        default=500,
        verbose_name="Máximo de Tokens",
        help_text="Límite de tokens por respuesta"
    )

    is_active = models.BooleanField(
        default=False,
        verbose_name="Activo",
        help_text="Activar/Desactivar el asistente"
    )

    knowledge_base_enabled = models.BooleanField(
        default=True,
        verbose_name="Habilitar Base de Conocimiento",
        help_text="Acceso a información de la base de datos"
    )

    product_catalog_access = models.BooleanField(
        default=True,
        verbose_name="Acceso a Catálogo",
        help_text="Puede consultar información de productos"
    )

    order_access = models.BooleanField(
        default=False,
        verbose_name="Acceso a Pedidos",
        help_text="Puede consultar información de pedidos (solo para usuarios autenticados)"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='assistant_configs'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración del Asistente"
        verbose_name_plural = "Configuraciones de Asistentes"
        ordering = ['-is_active', '-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"

    def get_ai_model_display_name(self):
        if self.ai_model == 'custom' and self.custom_model_name:
            return self.custom_model_name
        return self.get_ai_model_display()

class AssistantKnowledge(models.Model):
    """Base de conocimiento para el asistente"""

    KNOWLEDGE_TYPE_CHOICES = [
        ('product', 'Información de Productos'),
        ('company', 'Información de la Empresa'),
        ('policy', 'Políticas y Términos'),
        ('faq', 'Preguntas Frecuentes'),
        ('general', 'Información General'),
    ]

    title = models.CharField(max_length=200, verbose_name="Título")
    content = CKEditor5Field('Text', config_name='extends')
    knowledge_type = models.CharField(
        max_length=50,
        choices=KNOWLEDGE_TYPE_CHOICES,
        default='general'
    )

    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(
        default=1,
        choices=[(1, 'Baja'), (2, 'Media'), (3, 'Alta')],
        verbose_name="Prioridad"
    )

    tags = models.CharField(
        max_length=300,
        blank=True,
        help_text="Etiquetas separadas por coma (productos, envíos, garantía, etc.)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conocimiento del Asistente"
        verbose_name_plural = "Base de Conocimiento"
        ordering = ['-priority', 'title']

    def __str__(self):
        return self.title

class AssistantConversation(models.Model):
    """Registro de conversaciones del asistente"""

    session_id = models.CharField(max_length=100, unique=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    message_count = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Conversación"
        verbose_name_plural = "Conversaciones"
        ordering = ['-started_at']

    def __str__(self):
        user_info = self.user.username if self.user else "Anónimo"
        return f"Conversación {self.session_id} - {user_info}"

class AssistantMessage(models.Model):
    """Mensajes individuales de las conversaciones"""

    conversation = models.ForeignKey(
        AssistantConversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )

    message_type = models.CharField(
        max_length=10,
        choices=[('user', 'Usuario'), ('assistant', 'Asistente')]
    )

    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    # Metadata para análisis
    response_time = models.FloatField(null=True, blank=True)  # en segundos
    tokens_used = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Mensaje"
        verbose_name_plural = "Mensajes"
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.message_type}: {self.content[:50]}..."

class AssistantTraining(models.Model):
    """Entrenamiento y fine-tuning del asistente"""

    TRAINING_STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('training', 'Entrenando'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    training_data = models.JSONField(
        help_text="Datos de entrenamiento en formato JSON"
    )

    status = models.CharField(
        max_length=20,
        choices=TRAINING_STATUS_CHOICES,
        default='pending'
    )

    model_version = models.CharField(max_length=50)
    accuracy_score = models.FloatField(null=True, blank=True)

    trained_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    trained_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Entrenamiento"
        verbose_name_plural = "Entrenamientos"

    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"
