import difflib
import re
from decimal import Decimal

import pandas as pd
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import (CargaArchivo, Category, DetallePedido, MainCategory,
                         Product)


def norm(texto):
    return ' '.join(str(texto).upper().split())


def parse_unidad_x_pack(nombre):
    """Extrae unidades por pack del nombre: '6X750'->6, 'X12'->12, '1X200'->1"""
    m = re.search(r'(\d+)\s*[xX]\s*\d', nombre)
    if m:
        return int(m.group(1))
    m = re.search(r'[xX]\s*(\d+)', nombre)
    if m:
        return int(m.group(1))
    return 0


class Command(BaseCommand):
    help = ("Importa lista de precios desde Excel. Actualiza productos "
            "existentes por Cod./numero conservando sus imágenes, crea los "
            "nuevos y da de baja los que ya no están en la lista.")

    def add_arguments(self, parser):
        parser.add_argument('archivo', help='Ruta al archivo .xlsx de la lista')
        parser.add_argument('--apply', action='store_true',
                            help='Aplica los cambios (sin esto es dry-run)')
        parser.add_argument('--fuzzy', type=float, default=0.88,
                            help='Umbral de similitud de nombre (default 0.88)')

    def handle(self, *args, **options):
        archivo = options['archivo']
        aplicar = options['apply']
        cutoff = options['fuzzy']

        try:
            df = pd.read_excel(archivo)
        except Exception as e:
            raise CommandError(f'No se pudo leer el archivo: {e}')

        columnas = {'Cod.', 'Artículo', 'Disponible', 'Rubro', 'SubRubro',
                    'PRECIO1', 'Desc.Larga'}
        faltantes = columnas - set(df.columns)
        if faltantes:
            raise CommandError(f'Faltan columnas en el Excel: {faltantes}')

        # --- armar plan sin escribir ---
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

        actualizados = []   # (producto, data, tipo_match)
        nuevos = []         # data
        omitidos = []       # (articulo, motivo)
        fuzzy_pares = []    # (nombre_excel, nombre_db)
        tocados = set()     # ids de productos matcheados

        def fuzzy_libre(nombre_norm):
            """Candidato fuzzy solo entre productos aún no matcheados"""
            libres = {norm(p.nombre): p for p in productos_db
                      if p.id not in tocados}
            match = difflib.get_close_matches(nombre_norm, list(libres),
                                              n=1, cutoff=cutoff)
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
                'numero': cod,
                'nombre': articulo,
                'precio': precio,
                'stock': stock,
                'rubro': rubro,
                'subrubro': subrubro,
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

        # --- productos DB que no están en la lista ---
        sobrantes = [p for p in productos_db if p.id not in tocados]
        con_pedidos = set(
            DetallePedido.objects.filter(producto__in=sobrantes)
            .values_list('producto_id', flat=True))
        eliminar = [p for p in sobrantes if p.id not in con_pedidos]
        baja = [p for p in sobrantes if p.id in con_pedidos]

        # --- reporte ---
        self.stdout.write(f'\n{"APLICANDO" if aplicar else "DRY-RUN"}: '
                          f'{len(df)} filas en {archivo}\n')
        self.stdout.write(f'  Actualizados por Cod.: '
                          f'{sum(1 for _,_,t in actualizados if t=="cod")}')
        self.stdout.write(f'  Actualizados por nombre exacto: '
                          f'{sum(1 for _,_,t in actualizados if t=="nombre")}')
        self.stdout.write(f'  Actualizados por nombre similar: '
                          f'{sum(1 for _,_,t in actualizados if t=="fuzzy")}')
        for xl, db in fuzzy_pares:
            self.stdout.write(f'      "{xl}"  <->  "{db}"')
        self.stdout.write(f'  Nuevos (sin imagen): {len(nuevos)}')
        self.stdout.write(f'  Omitidos: {len(omitidos)}')
        for art, motivo in omitidos:
            self.stdout.write(f'      {art} — {motivo}')
        self.stdout.write(f'  Eliminados (fuera de lista, sin pedidos): '
                          f'{len(eliminar)}')
        self.stdout.write(f'  Stock=0 (fuera de lista, con pedidos): '
                          f'{len(baja)}')
        for p in baja:
            self.stdout.write(f'      #{p.numero} {p.nombre}')

        if not aplicar:
            self.stdout.write(self.style.WARNING(
                '\nDry-run: no se escribió nada. Revisar matches fuzzy y '
                'correr con --apply para aplicar.'))
            return

        # --- aplicar ---
        usuario = User.objects.filter(is_superuser=True).first()

        with transaction.atomic():
            carga = CargaArchivo.objects.create(
                usuario=usuario,
                descripcion=f'Importación lista {archivo} '
                            f'({len(df)} filas)')

            def categoria(rubro, subrubro):
                main, _ = MainCategory.objects.get_or_create(nombre=rubro)
                cat, _ = Category.objects.get_or_create(
                    nombre=f'{rubro} - {subrubro}', defaults={'main': main})
                if cat.main_id != main.id:
                    cat.main = main
                    cat.save()
                return cat

            for producto, data, _ in actualizados:
                producto.numero = data['numero']
                producto.nombre = data['nombre']
                producto.precio = data['precio']
                producto.stock = data['stock']
                producto.unidad_x_pack = data['unidad_x_pack']
                producto.categoria = categoria(data['rubro'], data['subrubro'])
                if not producto.descripcion:
                    producto.descripcion = data['descripcion']
                producto.carga = carga
                producto.save()  # nunca toca imagenurl/imagen1/imagen2

            for data in nuevos:
                Product.objects.create(
                    numero=data['numero'], nombre=data['nombre'],
                    precio=data['precio'], stock=data['stock'],
                    unidad_x_pack=data['unidad_x_pack'],
                    categoria=categoria(data['rubro'], data['subrubro']),
                    descripcion=data['descripcion'], carga=carga)

            for p in baja:
                p.stock = 0
                p.save()

            Product.objects.filter(id__in=[p.id for p in eliminar]).delete()

        self.stdout.write(self.style.SUCCESS(
            f'\nListo: {len(actualizados)} actualizados, {len(nuevos)} nuevos, '
            f'{len(eliminar)} eliminados, {len(baja)} con stock=0, '
            f'{len(omitidos)} omitidos.'))
