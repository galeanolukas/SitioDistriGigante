from .models import ConfiguracionOrdenCatalogo

def config_orden_catalogo(request):
    """
    Context processor para agregar la configuración de orden a todos los templates
    """
    try:
        config = ConfiguracionOrdenCatalogo.objects.get(activo=True)
    except ConfiguracionOrdenCatalogo.DoesNotExist:
        config = None

    return {
        'config_orden': config
    }
