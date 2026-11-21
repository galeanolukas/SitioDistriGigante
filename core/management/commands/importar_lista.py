from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from core.importer import importar_lista_precios


class Command(BaseCommand):
    help = ("Importa lista de precios desde Excel. Actualiza productos "
            "existentes por Cod./numero conservando sus imágenes, crea los "
            "nuevos y da de baja los que ya no están en la lista.")

    def add_arguments(self, parser):
        parser.add_argument('archivo', help='Ruta al archivo .xlsx de la lista')
        parser.add_argument('--apply', action='store_true',
                            help='Aplica los cambios (sin esto es dry-run)')
        parser.add_argument('--fuzzy', type=float, default=0.95,
                            help='Umbral de similitud de nombre (default 0.95)')

    def handle(self, *args, **options):
        usuario = User.objects.filter(is_superuser=True).first()
        try:
            r = importar_lista_precios(options['archivo'],
                                       fuzzy=options['fuzzy'],
                                       aplicar=options['apply'],
                                       usuario=usuario)
        except ValueError as e:
            raise CommandError(str(e))
        except Exception as e:
            raise CommandError(f'No se pudo leer el archivo: {e}')

        modo = 'APLICANDO' if r['aplicado'] else 'DRY-RUN'
        self.stdout.write(f'\n{modo}: {r["filas"]} filas en '
                          f'{options["archivo"]}\n')
        self.stdout.write(f'  Actualizados por Cod.: {r["por_cod"]}')
        self.stdout.write(f'  Actualizados por nombre exacto: {r["por_nombre"]}')
        self.stdout.write(f'  Actualizados por nombre similar: {r["por_fuzzy"]}')
        for xl, db in r['fuzzy_pares']:
            self.stdout.write(f'      "{xl}"  <->  "{db}"')
        self.stdout.write(f'  Nuevos (sin imagen): {r["nuevos"]}')
        self.stdout.write(f'  Omitidos: {len(r["omitidos"])}')
        for art, motivo in r['omitidos']:
            self.stdout.write(f'      {art} — {motivo}')
        self.stdout.write(f'  Eliminados (fuera de lista, sin pedidos): '
                          f'{r["eliminados"]}')
        self.stdout.write(f'  Stock=0 (fuera de lista, con pedidos): '
                          f'{len(r["stock_cero"])}')
        for p in r['stock_cero']:
            self.stdout.write(f'      #{p.numero} {p.nombre}')

        if not r['aplicado']:
            self.stdout.write(self.style.WARNING(
                '\nDry-run: no se escribió nada. Revisar matches fuzzy y '
                'correr con --apply para aplicar.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nListo: {r["por_cod"] + r["por_nombre"] + r["por_fuzzy"]} '
                f'actualizados, {r["nuevos"]} nuevos, {r["eliminados"]} '
                f'eliminados, {len(r["stock_cero"])} con stock=0, '
                f'{len(r["omitidos"])} omitidos.'))
