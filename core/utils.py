import requests, lxml, re, json, base64
import os
from os.path import basename, join
import pandas as pd
import json
import pathlib
from bs4 import BeautifulSoup as bs
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import ast
import re
import random
import string
from mercadopago import SDK
from django.db import transaction

def borrar_todos_los_registros(modelo, batch_size=5000):
    """
    Elimina todos los registros de una tabla en lotes de batch_size.

    :param modelo: Modelo de Django cuyos registros serán eliminados.
    :param batch_size: Número de registros a eliminar por iteración.
    """
    while True:
        # Obtener IDs en lotes
        ids = list(modelo.objects.values_list('id', flat=True)[:batch_size])

        if not ids:
            break  # Si no hay más registros, detener el proceso

        with transaction.atomic():
            modelo.objects.filter(id__in=ids).delete()

        print(f"Eliminados {len(ids)} registros...")

    print("Todos los registros han sido eliminados.")

# Api checkout de mercado pago - MEJORADA
class MPCheckOut(SDK):
    def __init__(self, cuenta=None):
        if not cuenta or not hasattr(cuenta, 'access_token'):
            raise ValueError("Se requiere una cuenta válida de MercadoPago")
        SDK.__init__(self, cuenta.access_token)
        self.cuenta = cuenta
        self.preferencias = {}
        self.boton_js = '''
            // Agrega credenciales de SDK
            const mp = new MercadoPago("%s", {
                locale: "es-AR"
            });

            // Crea y configura el botón
            const button = mp.checkout({
                preference: {
                    id: "%s"
                },
                render: {
                    container: "#boton_mp",
                    label: "%s",
                    type: "pay",
                }
            });'''

    def config(self, titulo='Pago', monto=0, unidad=1, ID='service', external_reference=None):
        """Configura los items del pago con validaciones mejoradas"""
        # Validar monto
        if monto <= 0:
            raise ValueError("El monto debe ser mayor a 0")
        
        # Validar título
        if not titulo or len(titulo.strip()) == 0:
            raise ValueError("El título no puede estar vacío")
        
        # Limpiar y validar título
        titulo = titulo.strip()[:85]  # Límite de MercadoPago
        
        # Guardar external_reference si se proporciona
        if external_reference:
            self.preferencias['external_reference'] = external_reference
        
        if 'items' in self.preferencias.keys():
            self.preferencias['items'].append({
                'id': str(ID),
                'title': titulo,
                'quantity': int(unidad),
                'unit_price': float(monto),
                'currency_id': 'ARS'
            })
        else:
            self.preferencias['items'] = [{
                'id': str(ID),
                'title': titulo,
                'quantity': int(unidad),
                'unit_price': float(monto),
                'currency_id': 'ARS'
            }]

    def respuestas_urls(self, exito, fallo, pendiente, notification_url=None):
        """Configura las URLs de respuesta para MercadoPago"""
        # Configurar back_urls primero
        self.preferencias['back_urls'] = {
            'success': exito,
            'failure': fallo,
            'pending': pendiente
        }
        
        # NO configurar auto_return para evitar el error
        # MercadoPago lo manejará automáticamente
        # self.preferencias['auto_return'] = 'approved'
        
        # Configurar notification_url si se proporciona
        if notification_url:
            self.preferencias['notification_url'] = notification_url
        else:
            # Dejar notification_url vacío por defecto
            self.preferencias['notification_url'] = ''

    def boton(self, label='REALIZAR PAGO'):
        """Crea el botón de pago con manejo de errores mejorado y logging"""
        try:
            # Validaciones iniciales
            if not hasattr(self, 'cuenta') or not self.cuenta:
                return "Error: No hay cuenta de MercadoPago configurada"
            
            # Verificar que hay items configurados
            if 'items' not in self.preferencias or not self.preferencias['items']:
                return "Error: No hay items configurados para el pago"

            # Verificar que el monto no sea 0
            total = sum(item['unit_price'] * item['quantity'] for item in self.preferencias['items'])
            if total <= 0:
                return "Error: El monto total debe ser mayor a 0"

            # Validar que todos los campos requeridos estén presentes
            for item in self.preferencias['items']:
                if not all(key in item for key in ['id', 'title', 'quantity', 'unit_price']):
                    return "Error: Faltan campos requeridos en los items"

            # Crear preferencia limpia SIN auto_return
            preference_data = {
                'items': self.preferencias['items'],
                'back_urls': self.preferencias.get('back_urls', {}),
            }
            
            # FORZAR eliminación de auto_return si existe
            if 'auto_return' in preference_data:
                del preference_data['auto_return']
            
            # Eliminar cualquier otro campo problemático
            if 'notification_url' in preference_data and not preference_data['notification_url']:
                del preference_data['notification_url']

            # Crear la preferencia
            preference_response = self.preference().create(preference_data)

            if 'response' not in preference_response:
                print(f"Error en respuesta MP: {preference_response}")
                return "Error: Respuesta inválida de MercadoPago"

            self.api = preference_response['response']
            print(f"Respuesta exitosa MP: {self.api}")

            # Verificar que la preferencia se creó correctamente
            if 'id' not in self.api:
                print("Error: No se pudo obtener el ID de la preferencia")
                if 'message' in self.api:
                    return f"Error de MercadoPago: {self.api['message']}"
                return "Error al crear la preferencia de pago"

            # Validar que la cuenta tenga public_key
            if not hasattr(self.cuenta, 'public_key') or not self.cuenta.public_key:
                return "Error: La cuenta no tiene public_key configurada"

            # Retornar el JavaScript del botón
            return self.boton_js % (
                self.cuenta.public_key,
                self.api['id'],
                label
            )

        except ValueError as ve:
            print(f"Error de validación: {str(ve)}")
            return f"Error de validación: {str(ve)}"
        except Exception as e:
            print(f"Error al crear el botón de pago: {str(e)}")
            import traceback
            traceback.print_exc()
            return f"Error: {str(e)}"

    # Método alternativo más simple
    def boton_simple(self, label='REALIZAR PAGO'):
        """Versión simplificada que evita problemas con auto_return"""
        try:
            # Verificar items
            if 'items' not in self.preferencias or not self.preferencias['items']:
                return "Error: No hay items configurados para el pago"

            # Crear preferencia sin auto_return
            preference_data = self.preferencias.copy()
            if 'auto_return' in preference_data:
                del preference_data['auto_return']

            preference_response = self.preference().create(preference_data)

            if 'response' in preference_response and 'id' in preference_response['response']:
                self.api = preference_response['response']
                return self.boton_js % (
                    self.cuenta.public_key,
                    self.api['id'],
                    label
                )
            else:
                return "Error al crear la preferencia"

        except Exception as e:
            return f"Error: {str(e)}"

# Cuenta de prueba
class CuentaMpTest:
    def __init__(self):
        self.public_key = "TEST-d989b44c-b8fd-400e-81fb-39e10794b25b"
        self.access_token = "TEST-7867507306076979-091418-7e221cf9b9d21514d56b55c7143e0ecd-33669542"

def Key(digit=4):
    keylist = [random.choice(base_str()) for i in range(digit)]
    return ("".join(keylist))

def base_str():
    return (string.ascii_letters+string.digits)

class SIE():
    def __init__(self, sch_engine="google"):
        if sch_engine == "google":
            self.params = {"q":"none", 'tbm':'isch', "hl":"es-419", "ijn":1, "dpr":1}
            self.engine = "https://www.google.com/search"
            self.clase = {"class":"rg_i Q4LuWd"}
            self.tag = 'img'
        else:
            self.params = {"hps":1, "q":"none", "atb":"v374-1", "iax":"images", "iar":"images", "ia":"images"}
            self.engine = "https://duckduckgo.com/?"
            self.clase = {"class":"tile--img"}
            self.tag = 'span'

        self.user_agent_list = [
          'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15',
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0',
          'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
          'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:77.0) Gecko/20100101 Firefox/77.0',
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
        ]

        self.result = []
        self.total_links = 0
        self.soup = None
        self.index = 0

    def get_vdq(self, q):
        res = requests.post(self.engine, data={'q':q})
        if self.engine == "https://duckduckgo.com/":
            res = requests.post(self.engine, data={'q':q})
            searchObj = re.search(r'vqd=([\d-]+)\&', res.text, re.M|re.I)
            if not searchObj:
                print("Parser Not encontrado!!")
                return -1
            else:
                print(searchObj)

            self.params['vqd'] = searchObj.group(1)

            res.close()
        else:
            pass

    def get(self, q=None, result=None):
        self.headers = {'User-Agent': random.choice(self.user_agent_list)}
        if q:
            self.params["q"] = q

        response = requests.get(self.engine,
                                params=self.params, headers=self.headers, timeout=3)

        if response.status_code == 200:
            soup = bs(response.text, 'lxml')
            response.close()

            for raw_img in soup.find_all(self.tag, self.clase, limit=10):
                print(raw_img)
                img_src = raw_img.get('src')
                alt = raw_img.get('alt')
                iid = raw_img.get('data-iid')
                ih = raw_img.get('height')
                iw = raw_img.get('width')

                if img_src and img_src.startswith("data:image/"):
                    patron = re.compile(q, re.IGNORECASE)
                    match = re.search(patron, alt)
                    img_src = self.get_images_data(soup, iid)

                    if match:
                        if ih <= 173 and iw <= 173:
                            self.result.append(0, img_src)
                        else:
                            self.result.append(1, img_src)
                    else:
                        self.result.append(img_src)

                    self.index += 1

            if result:
                return self.result[result]
            else:
                return random.choice(self.result)

            self.index = 0
            self.result = []

        else:
            self.result = []
            return None

    def get_images_data(self, soup, id):
        n = 0
        # funcion que extrae los datos de la imagenes en los js
        for js in soup.select('script'):
            nonce = js.attrs["nonce"]
            data = re.findall(r"_setImgSrc(([^<]+));", js.text)
            if len(data) != 0:
                img_tuple = data[0][0]
                n += 1
                if n > 1:
                    if id == eval(img_tuple)[0]:
                        img_data = eval(img_tuple)[1].split('\\')
                        return ''.join(img_data)

    def get_url_img(self, query, num_images=10):
        chrome_options = Options()
        chrome_options.add_argument('--headless')

        # Especifica la ruta al controlador de Chrome
        driver_path = 'core/static/lib/chromedriver_linux64/chromedriver'

        from selenium.webdriver.chrome.service import Service

        service = Service(executable_path=driver_path)
        options = webdriver.ChromeOptions()
        driver = webdriver.Chrome(service=service, options=chrome_options)

        try:
            driver.get(f'https://www.google.com/search?q={query}&tbm=isch')

            for _ in range(num_images // 50):
                driver.execute_script("window.scrollBy(0,10000)")

            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "img.Q4LuWd")))

            img_elements = driver.find_elements(By.CSS_SELECTOR, "img.Q4LuWd")

            for i, img_element in enumerate(img_elements[:num_images]):
                try:
                    img_element.click()
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'img.sFlh5c.pT0Scc.iPVvYb')))
                    img_url = driver.find_element(By.CSS_SELECTOR, 'img.sFlh5c.pT0Scc.iPVvYb')
                    print(img_url)
                except:
                    print("Not FOUND!!")

        except Exception as e:
            print(f"Error al obtener las URL de las imágenes: {e}")
            return None

        driver.quit()

class LoadExcel():
    def __init__(self, file_path=None):
        if pathlib.Path(file_path).suffix == ".csv":
            self.file_data = pd.read_csv(file_path, decimal=",",thousands='.')
        else:
            self.file_data = pd.read_excel(file_path, decimal=",", thousands='.')

        self.columns = []
        self.sheets = self.file_data.keys()
        pd.options.display.float_format = '{:.2f}'.format
        print(self.sheets)

    def get_title(self):
        return list(self.file_data.columns.values)

    def get_size(self):
        return self.file_data.size

    def get_data(self, col_name=None):
        print(self.file_data[col_name])
        return self.file_data[col_name]
