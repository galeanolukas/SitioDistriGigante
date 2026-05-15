# views.py
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views import View
from .models import AssistantConfig, AssistantConversation, AssistantMessage

logger = logging.getLogger(__name__)

class AssistantAPIView(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        try:
            data = json.loads(request.body)
            message = data.get('message', '')
            session_id = data.get('session_id', '')

            # Obtener configuración activa
            config = AssistantConfig.objects.filter(is_active=True).first()

            if not config:
                return JsonResponse({
                    'error': 'Asistente no configurado',
                    'response': 'El asistente virtual no está disponible en este momento.'
                })

            # Procesar mensaje y generar respuesta
            response = self.generate_response(config, message, session_id, request)

            return JsonResponse({
                'response': response,
                'session_id': session_id,
                'status': 'success'
            })

        except Exception as e:
            logger.error(f"Error en AssistantAPI: {str(e)}")
            return JsonResponse({
                'error': 'Error interno del servidor',
                'response': 'Lo siento, estoy teniendo dificultades técnicas. Por favor, intenta nuevamente.'
            })

    def generate_response(self, config, message, session_id, request):
        # Aquí integrarás con tu API de IA (OpenAI, Claude, etc.)
        # Por ahora devolvemos una respuesta de prueba

        # Simular procesamiento de IA
        responses = [
            "¡Hola! Soy tu asistente virtual. ¿En qué puedo ayudarte hoy?",
            "Entiendo que necesitas ayuda. ¿Podrías darme más detalles?",
            "Gracias por tu consulta. Estoy procesando tu solicitud...",
            "Basado en tu pregunta, te recomiendo contactarnos para más detalles.",
            "Parece que buscas información sobre nuestros productos. ¿Te interesa algo específico?"
        ]

        # Respuesta simple por ahora - integrar con IA real aquí
        import random
        return random.choice(responses)
