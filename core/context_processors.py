from django.db.models import Count, Prefetch

from .models import ConfiguracionTienda, MainCategory, Category
from . import tienda_cart


def subs_visibles():
    """Subcategorías visibles con al menos un producto (para el nav de la tienda)."""
    return (Category.objects.filter(visible=True)
            .annotate(n_prods=Count('categoria'))
            .filter(n_prods__gt=0)
            .order_by('orden', 'nombre'))


def rubros_nav():
    """Categorías principales con sus subcategorías visibles precargadas."""
    mains = (MainCategory.objects.filter(mostrar=True)
             .prefetch_related(Prefetch('category_set',
                                        queryset=subs_visibles(),
                                        to_attr='subs_visibles')))
    rubros = [m for m in mains if m.subs_visibles]
    rubros.sort(key=lambda m: (min(s.orden for s in m.subs_visibles), m.nombre))
    return rubros


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

    try:
        rubros = rubros_nav()
    except Exception:
        rubros = []

    return {
        'tienda_cfg': config,
        'wa_numero': config.whatsapp_numero if config else '5493705262361',
        'tienda_cart_count': tienda_cart.cantidad_total(request.session),
        'rubros': rubros,
    }
