"""
Módulo de integración con Uber Direct API para envíos
"""
import requests
import json
import logging
from django.conf import settings
from datetime import datetime

logger = logging.getLogger(__name__)


class UberIntegration:
    """Clase principal para integración con Uber Direct API"""
    
    def __init__(self):
        self.client_id = settings.UBER_CLIENT_ID
        self.client_secret = settings.UBER_CLIENT_SECRET
        self.access_token = settings.UBER_ACCESS_TOKEN
        self.environment = settings.UBER_ENVIRONMENT
        self.base_url = settings.UBER_API_BASE_URL.get(self.environment)
        self.timeout = settings.UBER_API_TIMEOUT
        
    def get_headers(self):
        """Obtener headers para requests a Uber API"""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def crear_delivery(self, pickup_address, dropoff_address, pickup_name, 
                      pickup_phone, dropoff_name, dropoff_phone, 
                      pickup_latitude=None, pickup_longitude=None,
                      dropoff_latitude=None, dropoff_longitude=None):
        """
        Crear un delivery usando Uber Direct API
        
        Args:
            pickup_address: Dirección de recolección
            dropoff_address: Dirección de entrega
            pickup_name: Nombre del contacto en recolección
            pickup_phone: Teléfono del contacto en recolección
            dropoff_name: Nombre del contacto en entrega
            dropoff_phone: Teléfono del contacto en entrega
            pickup_latitude: Latitud de recolección (opcional)
            pickup_longitude: Longitud de recolección (opcional)
            dropoff_latitude: Latitud de entrega (opcional)
            dropoff_longitude: Longitud de entrega (opcional)
            
        Returns:
            dict: Respuesta de Uber API con detalles del delivery
        """
        try:
            url = f"{self.base_url}/deliveries"
            
            # Construir payload para Uber Direct API
            payload = {
                "pickup": {
                    "location": {
                        "address": pickup_address
                    },
                    "contact": {
                        "name": pickup_name,
                        "phone": pickup_phone
                    }
                },
                "dropoff": {
                    "location": {
                        "address": dropoff_address
                    },
                    "contact": {
                        "name": dropoff_name,
                        "phone": dropoff_phone
                    }
                }
            }
            
            # Agregar coordenadas si están disponibles
            if pickup_latitude and pickup_longitude:
                payload["pickup"]["location"]["latitude"] = pickup_latitude
                payload["pickup"]["location"]["longitude"] = pickup_longitude
            
            if dropoff_latitude and dropoff_longitude:
                payload["dropoff"]["location"]["latitude"] = dropoff_latitude
                payload["dropoff"]["location"]["longitude"] = dropoff_longitude
            
            response = requests.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                logger.info(f"Delivery creado exitosamente: {response.json()}")
                return {
                    'success': True,
                    'data': response.json()
                }
            else:
                logger.error(f"Error al crear delivery: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': response.text,
                    'status_code': response.status_code
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de conexión con Uber API: {str(e)}")
            return {
                'success': False,
                'error': f'Error de conexión: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Error inesperado al crear delivery: {str(e)}")
            return {
                'success': False,
                'error': f'Error inesperado: {str(e)}'
            }
    
    def obtener_delivery(self, delivery_id):
        """
        Obtener detalles de un delivery existente
        
        Args:
            delivery_id: ID del delivery en Uber
            
        Returns:
            dict: Detalles del delivery
        """
        try:
            url = f"{self.base_url}/deliveries/{delivery_id}"
            
            response = requests.get(
                url,
                headers=self.get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'data': response.json()
                }
            else:
                logger.error(f"Error al obtener delivery: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': response.text,
                    'status_code': response.status_code
                }
                
        except Exception as e:
            logger.error(f"Error al obtener delivery: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancelar_delivery(self, delivery_id):
        """
        Cancelar un delivery existente
        
        Args:
            delivery_id: ID del delivery en Uber
            
        Returns:
            dict: Resultado de la cancelación
        """
        try:
            url = f"{self.base_url}/deliveries/{delivery_id}/cancel"
            
            response = requests.post(
                url,
                headers=self.get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                logger.info(f"Delivery {delivery_id} cancelado exitosamente")
                return {
                    'success': True,
                    'data': response.json()
                }
            else:
                logger.error(f"Error al cancelar delivery: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': response.text,
                    'status_code': response.status_code
                }
                
        except Exception as e:
            logger.error(f"Error al cancelar delivery: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def mapear_estado_uber(self, uber_status):
        """
        Mapear estado de Uber a estado del sistema de envíos
        
        Args:
            uber_status: Estado de Uber (pending, scheduled, en_route_to_pickup, at_pickup, en_route_to_dropoff, at_dropoff, completed, canceled)
            
        Returns:
            str: Estado equivalente en el sistema
        """
        mapeo_estados = {
            'pending': 'pendiente',
            'scheduled': 'pendiente',
            'en_route_to_pickup': 'pendiente',
            'at_pickup': 'pendiente',
            'en_route_to_dropoff': 'en_transito',
            'at_dropoff': 'en_transito',
            'completed': 'entregado',
            'canceled': 'cancelado',
            'returning': 'en_transito',
            'returned': 'cancelado'
        }
        
        return mapeo_estados.get(uber_status, 'pendiente')
    
    def verificar_disponibilidad(self, pickup_latitude, pickup_longitude, 
                                 dropoff_latitude, dropoff_longitude):
        """
        Verificar disponibilidad de Uber en una zona específica
        
        Args:
            pickup_latitude: Latitud de recolección
            pickup_longitude: Longitud de recolección
            dropoff_latitude: Latitud de entrega
            dropoff_longitude: Longitud de entrega
            
        Returns:
            dict: Disponibilidad y estimaciones
        """
        try:
            url = f"{self.base_url}/deliveries/estimate"
            
            payload = {
                "pickup": {
                    "location": {
                        "latitude": pickup_latitude,
                        "longitude": pickup_longitude
                    }
                },
                "dropoff": {
                    "location": {
                        "latitude": dropoff_latitude,
                        "longitude": dropoff_longitude
                    }
                }
            }
            
            response = requests.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'data': response.json()
                }
            else:
                return {
                    'success': False,
                    'error': response.text,
                    'status_code': response.status_code
                }
                
        except Exception as e:
            logger.error(f"Error al verificar disponibilidad: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


def procesar_webhook_uber(webhook_data):
    """
    Procesar webhook recibido de Uber
    
    Args:
        webhook_data: Datos del webhook
        
    Returns:
        dict: Resultado del procesamiento
    """
    try:
        event_type = webhook_data.get('event_type')
        delivery_id = webhook_data.get('delivery_id')
        
        logger.info(f"Webhook Uber recibido: {event_type} - Delivery: {delivery_id}")
        
        # Mapear eventos de Uber a acciones del sistema
        eventos_soportados = {
            'delivery.created': 'crear',
            'delivery.status_updated': 'actualizar_estado',
            'delivery.canceled': 'cancelar',
            'delivery.completed': 'completar'
        }
        
        accion = eventos_soportados.get(event_type)
        
        if accion:
            return {
                'success': True,
                'action': accion,
                'delivery_id': delivery_id,
                'data': webhook_data
            }
        else:
            logger.warning(f"Evento de webhook no soportado: {event_type}")
            return {
                'success': False,
                'error': f'Evento no soportado: {event_type}'
            }
            
    except Exception as e:
        logger.error(f"Error al procesar webhook: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
