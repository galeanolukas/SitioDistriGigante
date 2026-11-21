"""Importación de listas de precios desde Excel.

Lógica compartida entre el comando `importar_lista` y la vista del panel
`cargar_lista`. `importar_lista_precios()` devuelve un dict con el reporte;
con `aplicar=False` solo calcula el plan (dry-run).
"""
import difflib
import re
from decimal import Decimal

import pandas as pd
from django.db import transaction

from .models import (CargaArchivo, Category, DetallePedido, MainCategory,
                     Product)

COLUMNAS_REQUERIDAS = {'Cod.', 'Artículo', 'Disponible', 'Rubro', 'SubRubro',
                       'PRECIO1', 'Desc.Larga'}


def norm(texto):
    return ' '.join(str(texto).upper().split())


def parse_unidad_x_pack(nombre):
    """Extrae unidades por pack del nombre: '6X750'->6, 'X12'->12"""
    m = re.search(r'(\d+)\s*[xX]\s*\d', nombre)
    if m:
        return int(m.group(1))
    m = re.search(r'[xX]\s*(\d+)', nombre)
    if m:
        return int(m.group(1))
    return 0


def _categoria(rubro, subrubro):
    main, _ = MainCategory.objects.get_or_create(nombre=rubro)
    cat, _ = Category.objects.get_or_create(
        nombre=f'{rubro} - {subrubro}', defaults={'main': main})
    if cat.main_id != main.id:
        cat.main = main
        cat.save()
    return cat


def importar_lista_precios(archivo, fuzzy=0.95, aplicar=False, usuario=None):
    """Importa una lista de precios Excel.

    archivo: ruta o file-like soportado por pandas.read_excel.
    Devuelve dict con el reporte; lanza ValueError si el archivo es inválido.
    """
    df = pd.read_excel(archivo)
    faltantes = COLUMNAS_REQUERIDAS - set(df.columns)
    if faltantes:
        raise ValueError(f'Faltan columnas en el Excel: {sorted(faltantes)}')

    productos_db = list(Product.objects.select_related('categoria').all())
    # numeros duplicados: preferir el producto que tiene imagen
    por_numero = {}
    for p in productos_db:
        prev = por_numero.get(p.numero)
        if prev is None or (p.imagenurl and not prev.imagenurl):
            por_numero[p.numero] = p
    por_nombre = {}
    for p in productos_db:
        prev = por_nombre.get(norm(p.nombre))
        if prev is None or (p.imagenurl and not prev.imagenurl):
            por_nombre[norm(p.nombre)] = p

    actualizados = []
    nuevos = []
    omitidos = []
    fuzzy_pares = []
    tocados = set()

    def fuzzy_libre(nombre_norm):
        libres = {norm(p.nombre): p for p in productos_db
                  if p.id not in tocados}
        match = difflib.get_close_matches(nombre_norm, list(libres),
                                          n=1, cutoff=fuzzy)
        return libres[match[0]] if match else None

    for _, row in df.iterrows():
        articulo = str(row['Artículo']).strip()
        cod = str(int(row['Cod.']))
        precio = Decimal(str(row['PRECIO1'])).quantize(Decimal('0.01'))
        stock = max(int(row['Disponible']), 0)
        rubro = str(row['Rubro']).strip().upper().replace('/', '-')
        subrubro = (str(row['SubRubro']).strip().upper().replace('/', '-')
                    if pd.notna(row['SubRubro']) else 'GENERAL')
        desc = (str(row['Desc.Larga']).strip()
                if pd.notna(row['Desc.Larga']) else articulo)

        if precio <= 0:
            omitidos.append((articulo, 'precio 0 (caja/no vendible)'))
            continue

        data = {
            'numero': cod, 'nombre': articulo, 'precio': precio,
            'stock': stock, 'rubro': rubro, 'subrubro': subrubro,
            'descripcion': desc,
            'unidad_x_pack': parse_unidad_x_pack(articulo),
        }

        producto, tipo = por_numero.get(cod), 'cod'
        if not producto or producto.id in tocados:
            producto = None
        if not producto:
            candidato = por_nombre.get(norm(articulo))
            if candidato and candidato.id not in tocados:
                producto, tipo = candidato, 'nombre'
        if not producto:
            producto = fuzzy_libre(norm(articulo))
            if producto:
                tipo = 'fuzzy'
                fuzzy_pares.append((articulo, producto.nombre))

        if producto:
            tocados.add(producto.id)
            actualizados.append((producto, data, tipo))
        else:
            nuevos.append(data)

    sobrantes = [p for p in productos_db if p.id not in tocados]
    con_pedidos = set(
        DetallePedido.objects.filter(producto__in=sobrantes)
        .values_list('producto_id', flat=True))
    eliminar = [p for p in sobrantes if p.id not in con_pedidos]
    baja = [p for p in sobrantes if p.id in con_pedidos]

    reporte = {
        'filas': len(df),
        'por_cod': sum(1 for _, _, t in actualizados if t == 'cod'),
        'por_nombre': sum(1 for _, _, t in actualizados if t == 'nombre'),
        'por_fuzzy': sum(1 for _, _, t in actualizados if t == 'fuzzy'),
        'fuzzy_pares': fuzzy_pares,
        'nuevos': len(nuevos),
        'omitidos': omitidos,
        'eliminados': len(eliminar),
        'stock_cero': [p for p in baja],
        'aplicado': aplicar,
    }

    if not aplicar:
        return reporte

    with transaction.atomic():
        carga = CargaArchivo.objects.create(
            usuario=usuario,
            descripcion=f'Importación lista ({len(df)} filas)')

        for producto, data, _ in actualizados:
            producto.numero = data['numero']
            producto.nombre = data['nombre']
            producto.precio = data['precio']
            producto.stock = data['stock']
            producto.unidad_x_pack = data['unidad_x_pack']
            producto.categoria = _categoria(data['rubro'], data['subrubro'])
            if not producto.descripcion:
                producto.descripcion = data['descripcion']
            producto.carga = carga
            producto.save()

        for data in nuevos:
            Product.objects.create(
                numero=data['numero'], nombre=data['nombre'],
                precio=data['precio'], stock=data['stock'],
                unidad_x_pack=data['unidad_x_pack'],
                categoria=_categoria(data['rubro'], data['subrubro']),
                descripcion=data['descripcion'], carga=carga)

        for p in baja:
            p.stock = 0
            p.save()

        Product.objects.filter(id__in=[p.id for p in eliminar]).delete()

    return reporte
