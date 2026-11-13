from django.db import migrations


def crear_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for nombre in ('mostrador', 'deposito', 'caja'):
        Group.objects.get_or_create(name=nombre)


def borrar_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=('mostrador', 'deposito', 'caja')).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_alter_pedido_estado_alter_perfil_tipo_usuario_and_more'),
    ]

    operations = [
        migrations.RunPython(crear_grupos, borrar_grupos),
    ]
