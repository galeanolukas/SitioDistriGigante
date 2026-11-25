"""Sincronización de stock y precios con el sistema Suplai (MySQL remoto).

La base remota (`srv561.hstgr.io`) es el sistema que maneja el stock real
de los productos. `sync_suplai()` trae `SUPLAI_PRODUCTOS` y actualiza los
`Product` locales matcheando `sku` contra `numero`, con la misma semántica
que `importer.importar_lista_precios` (antes la lista venía por Excel).

Con `aplicar=False` solo calcula el plan (dry-run).
"""
import json
import threading
from datetime import timedelta
from decimal import Decimal

import pymysql
from decouple import config
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .importer import _categoria
from .models import CargaArchivo, ConfiguracionTienda, Product


def conectar():
    return pymysql.connect(
        host=config('SUPLAI_DB_HOST', default='srv561.hstgr.io'),
        user=config('SUPLAI_DB_USER', default=''),
        password=config('SUPLAI_DB_PASSWORD', default=''),
        database=config('SUPLAI_DB_NAME', default=''),
        port=config('SUPLAI_DB_PORT', default=3306, cast=int),
        connect_timeout=15,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor)


def fetch_productos():
    """Devuelve las filas de SUPLAI_PRODUCTOS como lista de dicts."""
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sku, nombre, nombre_largo, marca, categoria,
                       subcategoria, stock_disponible, precio1,
                       unidades_por_bulto, activo
                FROM SUPLAI_PRODUCTOS
                """)
            return cur.fetchall()
    finally:
        conn.close()


def _guardar_reporte(reporte):
    """Guarda en ConfiguracionTienda el resumen del último sync."""
    try:
        resumen = {k: v for k, v in reporte.items()
                   if k in ('filas_suplai', 'actualizados', 'sin_cambios',
                            'nuevos', 'sin_match', 'aplicado', 'error')}
        resumen['bajas'] = len(reporte.get('bajas', []))
        cfg = ConfiguracionTienda.get()
        cfg.suplai_ultimo_sync = timezone.now()
        cfg.suplai_ultimo_reporte = json.dumps(resumen)
        cfg.save(update_fields=['suplai_ultimo_sync', 'suplai_ultimo_reporte'])
    except Exception:
        pass


def sync_suplai(aplicar=False, usuario=None, sync_precios=True):
    """Sincroniza Product con SUPLAI_PRODUCTOS.

    - sku presente y activo con precio > 0: actualiza (o crea) el producto
    - sku presente pero inactivo o precio <= 0: stock=0 (baja)
    - productos locales que no figuran en Suplai: no se tocan
    - sync_precios=False actualiza solo stock (conserva el precio local)
    """
    filas = fetch_productos()

    productos_db = list(Product.objects.select_related('categoria').all())
    # numeros duplicados: preferir el producto que tiene imagen
    por_numero = {}
    for p in productos_db:
        prev = por_numero.get(p.numero)
        if prev is None or (p.imagenurl and not prev.imagenurl):
            por_numero[p.numero] = p

    actualizados = []
    nuevos = []
    bajas = []
    sin_cambios = 0
    tocados = set()

    for row in filas:
        sku = str(row['sku']).strip()
        stock = max(int(row['stock_disponible'] or 0), 0)
        precio = Decimal(str(row['precio1'] or 0)).quantize(Decimal('0.01'))
        producto = por_numero.get(sku)

        if not row['activo'] or precio <= 0:
            if producto and producto.id not in tocados:
                tocados.add(producto.id)
                if producto.stock != 0:
                    bajas.append(producto)
            continue

        data = {
            'numero': sku,
            'nombre': (row['nombre'] or '').strip(),
            'precio': precio,
            'stock': stock,
            'marca': (row['marca'] or '').strip(),
            'rubro': (row['categoria'] or 'GENERAL').strip().upper()
                     .replace('/', '-'),
            'subrubro': (row['subcategoria'] or 'GENERAL').strip().upper()
                        .replace('/', '-'),
            'descripcion': (row['nombre_largo'] or row['nombre'] or '').strip(),
            'unidad_x_pack': int(row['unidades_por_bulto'] or 0),
        }

        if producto and producto.id not in tocados:
            tocados.add(producto.id)
            data['categoria_obj'] = _categoria(data['rubro'], data['subrubro'])
            if (producto.nombre != data['nombre'] or
                    (sync_precios and producto.precio != data['precio']) or
                    producto.stock != data['stock'] or
                    producto.marca != data['marca'] or
                    producto.unidad_x_pack != data['unidad_x_pack'] or
                    producto.categoria_id != data['categoria_obj'].id):
                actualizados.append((producto, data))
            else:
                sin_cambios += 1
        elif not producto:
            nuevos.append(data)

    sin_match = [p for p in productos_db if p.id not in tocados]

    reporte = {
        'filas_suplai': len(filas),
        'actualizados': len(actualizados),
        'sin_cambios': sin_cambios,
        'nuevos': len(nuevos),
        'bajas': [p for p in bajas],
        'sin_match': len(sin_match),
        'aplicado': aplicar,
    }

    if not aplicar:
        reporte['preview'] = [
            (p.numero, p.nombre, p.stock, d['stock'])
            for p, d in actualizados[:20]]
        return reporte

    with transaction.atomic():
        carga = CargaArchivo.objects.create(
            usuario=usuario,
            descripcion=f'Sync Suplai ({len(filas)} filas)')

        for producto, data in actualizados:
            producto.numero = data['numero']
            producto.nombre = data['nombre']
            if sync_precios:
                producto.precio = data['precio']
            producto.stock = data['stock']
            producto.marca = data['marca']
            producto.unidad_x_pack = data['unidad_x_pack']
            producto.categoria = data['categoria_obj']
            if not producto.descripcion:
                producto.descripcion = data['descripcion']
            producto.carga = carga
            producto.save()

        for data in nuevos:
            Product.objects.create(
                numero=data['numero'], nombre=data['nombre'],
                precio=data['precio'], stock=data['stock'],
                marca=data['marca'], unidad_x_pack=data['unidad_x_pack'],
                categoria=_categoria(data['rubro'], data['subrubro']),
                descripcion=data['descripcion'], carga=carga)

        for p in bajas:
            p.stock = 0
            p.save()

        if not actualizados and not nuevos and not bajas:
            carga.delete()

    _guardar_reporte(reporte)
    return reporte


def sync_debido():
    """True si el sync automático está activo y ya venció el intervalo."""
    cfg = ConfiguracionTienda.get()
    if not cfg.suplai_sync_activo:
        return False
    if not cfg.suplai_ultimo_sync:
        return True
    limite = timezone.now() - timedelta(minutes=cfg.suplai_sync_intervalo)
    return cfg.suplai_ultimo_sync < limite


def correr_auto():
    """Sync para cron/tarea programada: corre solo si está activo y venció
    el intervalo configurado. Devuelve el reporte o None si no correspondía."""
    cfg = ConfiguracionTienda.get()
    if not cfg.suplai_sync_activo:
        return None
    limite = timezone.now() - timedelta(minutes=cfg.suplai_sync_intervalo)
    # claim atómico: solo un proceso corre el sync a la vez
    claimed = ConfiguracionTienda.objects.filter(pk=1).filter(
        Q(suplai_ultimo_sync__isnull=True) |
        Q(suplai_ultimo_sync__lt=limite)
    ).update(suplai_ultimo_sync=timezone.now())
    if not claimed:
        return None
    try:
        return sync_suplai(aplicar=True, sync_precios=cfg.suplai_sync_precios)
    except Exception as e:
        _guardar_reporte({'error': str(e), 'aplicado': False})
        raise


def quizas_sincronizar():
    """Scheduler perezoso llamado desde el context processor: si el sync
    está activo y venció el intervalo, lo dispara en un thread en segundo
    plano (no bloquea la request)."""
    try:
        if not sync_debido():
            return
        hilo = threading.Thread(target=_sync_en_bg, daemon=True)
        hilo.start()
    except Exception:
        pass


def _sync_en_bg():
    from django import db
    try:
        correr_auto()
    except Exception as e:
        print(f'Sync Suplai automático falló: {e}')
    finally:
        db.close_old_connections()


def aplicar_items(items):
    """Actualización directa de stock desde el webhook de Suplai.

    items: lista de dicts {'sku': str, 'stock': int, 'precio': optional}.
    Devuelve (actualizados, no_encontrados).
    """
    skus = {str(i.get('sku', '')).strip() for i in items}
    por_numero = {p.numero: p for p in Product.objects.filter(numero__in=skus)}
    actualizados = []
    no_encontrados = sorted(skus - set(por_numero))

    with transaction.atomic():
        for i in items:
            sku = str(i.get('sku', '')).strip()
            producto = por_numero.get(sku)
            if not producto:
                continue
            producto.stock = max(int(i.get('stock') or 0), 0)
            if i.get('precio') is not None:
                precio = Decimal(str(i['precio'])).quantize(Decimal('0.01'))
                if precio > 0:
                    producto.precio = precio
            producto.save()
            actualizados.append(sku)

    return actualizados, no_encontrados
