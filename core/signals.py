from django.contrib.auth.models import Group
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.utils import timezone
from .models import Perfil, Pedido, Envio

@receiver(post_save, sender=Perfil)
def add_user_to_client_group(sender, instance, created, **kwargs):
    if created:
        try:
            clientes = Group.objects.get(name='cliente')
            #preventistas = Group.objects.create(name='preventista')            
            #administrativos = Group.objects.create(name='administrativo')   
        except Group.DoesNotExist:
            clientes = Group.objects.create(name='cliente')
            #preventistas = Group.objects.create(name='preventista')            
            #administrativos = Group.objects.create(name='administrativo')
            
        instance.user.groups.add(clientes)
        #instance.user.groups.add(preventistas)
        #instance.user.groups.add(administrativos)

@receiver(post_save, sender=Pedido)
def crear_envio_automatico(sender, instance, created, **kwargs):
    """
    Crear automáticamente un envío cuando un pedido es confirmado
    y tiene opción de envío a domicilio
    """
    if not created:  # Solo para pedidos actualizados
        return
    
    # Verificar si el pedido tiene opción de envío que requiere transporte
    if (instance.opcion_envio and 
        instance.opcion_envio.tipo in ['envio_domicilio', 'envio_gratis'] and
        instance.estado != 'cancelado'):
        
        # Obtener dirección del pedido (debería estar en los datos del formulario)
        direccion = getattr(instance, 'direccion_calle', '') + ' ' + \
                   getattr(instance, 'direccion_barrio', '') + ', ' + \
                   getattr(instance, 'direccion_cp', '')
        
        if not direccion.strip():
            direccion = 'Dirección no especificada'
        
        # Crear el envío
        envio = Envio.objects.create(
            pedido=instance,
            estado='pendiente',  # Pendiente de asignación a transportista
            direccion_entrega=direccion,
            observaciones=f'Envío automático para pedido #{instance.id}'
        )
        
        # Generar código QR
        envio.generar_qr_code()
        
        print(f"Envío #{envio.id} creado automáticamente para el pedido #{instance.id}")