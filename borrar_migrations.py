# borrar_migraciones.py
import os
import shutil

def borrar_migraciones(proyecto_path):
    for root, dirs, files in os.walk(proyecto_path):
        if 'migrations' in dirs:
            migrations_path = os.path.join(root, 'migrations')
            print(f"Procesando: {migrations_path}")
            for filename in os.listdir(migrations_path):
                if filename != '__init__.py' and filename.endswith('.py'):
                    file_path = os.path.join(migrations_path, filename)
                    os.remove(file_path)
                    print(f"Eliminado: {file_path}")

if __name__ == "__main__":
    proyecto_path = os.path.dirname(os.path.abspath(__file__))  # Ruta del proyecto
    borrar_migraciones(proyecto_path)
