from .models import ConfiguracionTienda
from . import tienda_cart


def tienda_context(request):
    """
    Expone la configuración de la tienda y el carrito de sesión
    en todos los templates.
    """
    try:
        config = ConfiguracionTienda.get()
        if config and config.suplai_sync_activo:
            from .suplai import quizas_sincronizar
            quizas_sincronizar()
    except Exception:
        config = None

    return {
        'tienda_cfg': config,
        'wa_numero': config.whatsapp_numero if config else '5493705262361',
        'tienda_cart_count': tienda_cart.cantidad_total(request.session),
    }
