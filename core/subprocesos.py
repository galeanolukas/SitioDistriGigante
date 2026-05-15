import threading
from .models import *
from django.contrib import messages
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.apps import apps
import math
import pandas as pd
import numpy as np

def is_nan(valor):
    return pd.isna(valor) or (isinstance(valor, float) and math.isnan(valor)) or valor is None

class CargarPoductosAuto:
    def __init__(self, request, total=None, data=None, atributos=None, name="Productos"):
        self.tipo = name
        self.total = total
        self.data = data
        self.atributos = atributos
        self.defaults_update = {}
        self.n_creados = 0
        self.n_actualizados = 0
        self.error = None
        self.request = request


    def cargar_datos(self):
        print(f"CARGANDO DATOS DE {self.tipo.upper()}.................")

        try:
            self.msj = f"Cargando {self.total} Datos de {self.tipo}..."
            print(self.msj)
            print(self.atributos)
            print(self.data)

            nuevos_productos = []
            productos_actualizar = []

            # Crear nuevo registro de carga
            carga_actual = CargaArchivo.objects.create(
                usuario=self.request.user,
                descripcion=f"Carga masiva desde archivo ({self.total} filas)"
            )

            for i in range(self.total):
                try:
                    default_data = {}

                    for key in self.atributos:
                        valor_columna = self.data.get(key)
                        valor = valor_columna.iloc[i] if valor_columna is not None else None

                        if isinstance(valor, str):
                            valor = valor.strip()

                            if key == "nombre" or key == "subcategoria":
                                valor = valor.replace("/", "-")

                        # Normalización
                        if key == "numero":
                            try:
                                valor = int(float(valor))  # Asegura que 295.0 → 295
                            except:
                                valor = None

                        if key in ["precio", "precio_m"]:
                            try:
                                if isinstance(valor, str):
                                    valor = valor.replace("$", "").replace(",", "").strip()
                                valor = Decimal(str(valor))
                            except (InvalidOperation, ValueError):
                                valor = Decimal("0.00")

                        if key == "unidad_x_pack":
                            try:
                                valor = int(valor) if valor else 0
                            except:
                                valor = 0

                        # Detectar valores NaN
                        if isinstance(valor, (np.int64, np.float64, float)):
                            valor = float(valor)
                        if valor == "nan" or (isinstance(valor, float) and np.isnan(valor)):
                            valor = None

                        default_data[key] = valor

                    # Manejo de categoría y subcategoría
                    if default_data.get("categoria"):
                        if str(default_data["categoria"]).lower() == "nan":
                            default_data["categoria"] = "SIN CATEGORIA"

                        categ, _ = MainCategory.objects.update_or_create(nombre=default_data["categoria"])
                        subcateg_nombre = default_data.get("subcategoria") or "GENERAL"
                        
                        # Crear subcategoría única combinando categoría y subcategoría
                        subcateg_unique_name = f"{default_data['categoria']} - {subcateg_nombre}"
                        subcateg, _ = Category.objects.get_or_create(nombre=subcateg_unique_name)
                        subcateg.main = categ
                        subcateg.save()

                        default_data["categoria"] = subcateg

                    # 💡 IMPORTANTE: eliminar campo subcategoria antes de crear producto
                    default_data.pop("subcategoria", None)

                    # Agregar registro de carga
                    default_data["carga"] = carga_actual

                    # Verificar si ya existe (por número y nombre)
                    producto_existente = Product.objects.filter(numero=default_data["numero"], nombre=default_data["nombre"]).first()

                    if producto_existente:
                        for key, val in default_data.items():
                            setattr(producto_existente, key, val)
                        productos_actualizar.append(producto_existente)
                        self.n_actualizados += 1
                    else:
                        nuevos_productos.append(Product(**default_data))
                        self.n_creados += 1

                    print(f"Fila {i+1} procesada correctamente.")

                except Exception as e:
                    print(f"Error en la fila {i+1}: {e}")
                    continue  # Salta fila y sigue

            # Bulk insert y update
            if nuevos_productos:
                Product.objects.bulk_create(nuevos_productos, batch_size=100)

            if productos_actualizar:
                campos_actualizar = list(default_data.keys())
                Product.objects.bulk_update(productos_actualizar, campos_actualizar, batch_size=100)

            print(f"{self.n_creados} Productos nuevos creados...")
            print(f"{self.n_actualizados} Productos actualizados...")

            return True

        except Exception as e:
            self.error = f"No se inició la carga: {e}"
            messages.error(self.request, self.error)
            print(self.error)
            return False

class CargarImagenes(threading.Thread):
    def __init__(self, request=None, productos=None, engine="google", num_result=0):
        threading.Thread.__init__(self)
        self.productos = productos
        self.request = request
        self.result = num_result
        self.sch_engine = engine

    def run(self):
        try:
            print("Buscando imaganes de productos!!!")
            for producto in self.productos:
                data = "{a} {b}".format(a=producto.nombre, b=producto.marca)
                producto.buscar_imagen(data, self.sch_engine, self.result)
                producto.save()

        except Exception as e:
            print("No se inicia la busqueda de imagenes!!: {}".format(e))
