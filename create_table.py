# En la consola de Django, ejecuta:
from django.db import connection
from django.db.utils import OperationalError

def add_nombre_column():
    try:
        with connection.cursor() as cursor:
            # Verificar si la columna ya existe
            cursor.execute("PRAGMA table_info(core_perfil)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'nombre' not in columns:
                # Agregar la columna nombre
                cursor.execute("ALTER TABLE core_perfil ADD COLUMN nombre VARCHAR(200) NULL")
                print("✅ Columna 'nombre' agregada exitosamente")

                # Poblar la columna con datos existentes
                from django.contrib.auth.models import User
                from core.models import Perfil

                for perfil in Perfil.objects.all():
                    if perfil.user.first_name and perfil.user.last_name:
                        perfil.nombre = f"{perfil.user.first_name} {perfil.user.last_name}"
                    elif perfil.user.first_name:
                        perfil.nombre = perfil.user.first_name
                    else:
                        perfil.nombre = perfil.user.username
                    perfil.save()

                print("✅ Datos poblados en la columna 'nombre'")
            else:
                print("⚠️ La columna 'nombre' ya existe")

    except OperationalError as e:
        print(f"❌ Error: {e}")

# Ejecutar la función
add_nombre_column()
