from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from core.suplai import sync_suplai, correr_auto


class Command(BaseCommand):
    help = ("Sincroniza stock y precios desde el sistema Suplai "
            "(MySQL remoto). Actualiza productos existentes por numero/sku, "
            "crea los nuevos y pone stock=0 a los inactivos o sin precio. "
            "Los productos locales que no existen en Suplai no se tocan.")

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Aplica los cambios (sin esto es dry-run)')
        parser.add_argument('--auto', action='store_true',
                            help='Modo cron: solo corre si el sync automático '
                                 'está activo y venció el intervalo '
                                 'configurado en el panel')
        parser.add_argument('--solo-stock', action='store_true',
                            help='Actualiza solo stock (no toca precios)')

    def handle(self, *args, **options):
        if options['auto']:
            try:
                r = correr_auto()
            except Exception as e:
                raise CommandError(f'No se pudo sincronizar con Suplai: {e}')
            if r is None:
                self.stdout.write('Sync automático desactivado o no venció '
                                  'el intervalo: nada que hacer.')
                return
        else:
            usuario = User.objects.filter(is_superuser=True).first()
            try:
                r = sync_suplai(aplicar=options['apply'], usuario=usuario,
                                sync_precios=not options['solo_stock'])
            except Exception as e:
                raise CommandError(f'No se pudo sincronizar con Suplai: {e}')

        modo = 'APLICANDO' if r['aplicado'] else 'DRY-RUN'
        self.stdout.write(f'\n{modo}: {r["filas_suplai"]} productos en Suplai\n')
        self.stdout.write(f'  Actualizados: {r["actualizados"]}')
        self.stdout.write(f'  Sin cambios: {r["sin_cambios"]}')
        self.stdout.write(f'  Nuevos: {r["nuevos"]}')
        self.stdout.write(f'  Bajas (stock=0): {len(r["bajas"])}')
        for p in r['bajas'][:20]:
            self.stdout.write(f'      #{p.numero} {p.nombre}')
        self.stdout.write(f'  Sin match en Suplai (sin tocar): {r["sin_match"]}')

        if not r['aplicado']:
            self.stdout.write('\nCambios de stock (primeros 20):')
            for num, nombre, antes, despues in r['preview']:
                self.stdout.write(f'      #{num} {nombre}: {antes} -> {despues}')
            self.stdout.write(self.style.WARNING(
                '\nDry-run: no se escribió nada. '
                'Correr con --apply para aplicar.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nListo: {r["actualizados"]} actualizados, '
                f'{r["nuevos"]} nuevos, {len(r["bajas"])} bajas.'))
