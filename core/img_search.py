import requests
from bs4 import BeautifulSoup
import urllib.parse
import base64

def obtener_imagenes_google(query, max_results=5, filtro_clase="YQ4gaf"):
    """
    Busca imágenes en Google y devuelve su contenido en base64, filtrando por clase CSS
    
    Args:
        query (str): Término de búsqueda
        max_results (int): Número máximo de resultados
        filtro_clase (str): Clase CSS para filtrar imágenes específicas
        
    Returns:
        list: Lista de diccionarios con los datos de cada imagen
    """
    # Codificar la consulta para URL
    query_encoded = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/search?q={query_encoded}&tbm=isch"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        # Obtener resultados de búsqueda
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        resultados = []
        # Buscar imágenes con la clase específica
        for img in soup.find_all('img', class_=filtro_clase)[:max_results]:
            img_url = img.get('src')
            
            # Si no tiene src o ya es base64, saltar
            if not img_url or img_url.startswith('data:'):
                continue
                
            try:
                # Descargar la imagen
                img_response = requests.get(img_url, headers=headers, timeout=10)
                img_response.raise_for_status()
                
                # Convertir a base64
                img_base64 = base64.b64encode(img_response.content).decode('utf-8')
                
                resultados.append({
                    'url': img_url,
                    'base64': img_base64,
                    'mime_type': img_response.headers.get('Content-Type', 'image/jpeg'),
                    'size_bytes': len(img_response.content),
                    'clase': filtro_clase,
                    'alt': img.get('alt', '')
                })
                
            except Exception as img_error:
                print(f"Error al procesar imagen {img_url}: {img_error}")
                continue
                
        return resultados
    
    except Exception as e:
        print(f"Error en la búsqueda: {e}")
        return []

# Ejemplo de uso
if __name__ == "__main__":
    query = input("Ingrese su búsqueda de imágenes: ")
    max_results = int(input("Número máximo de resultados (1-5 recomendado): ") or 3)
    
    print("\nOpciones de filtrado:")
    print("1. Todas las imágenes (sin filtro)")
    print("2. Solo imágenes principales (clase YQ4gaf)")
    opcion = input("Seleccione (1/2): ")
    
    filtro_clase = "YQ4gaf" if opcion == "2" else None
    
    imagenes = obtener_imagenes_google(query, max_results, filtro_clase)
    
    print(f"\nResultados para '{query}':")
    for i, img in enumerate(imagenes, 1):
        print(f"\nImagen #{i}:")
        print(f"URL: {img['url']}")
        print(f"Clase: {img.get('clase', 'N/A')}")
        print(f"Texto alternativo: {img['alt']}")
        print(f"Tipo: {img['mime_type']}")
        print(f"Tamaño: {img['size_bytes']} bytes")
        print(f"Base64 (primeros 100 chars): {img['base64'][:100]}...")
        
        # Guardar en archivo
        extension = img['mime_type'].split('/')[-1].split(';')[0]
        filename = f"imagen_{i}.{extension if extension in ['jpeg','png','gif'] else 'jpg'}"
        with open(filename, 'wb') as f:
            f.write(base64.b64decode(img['base64']))
        print(f"Imagen guardada como {filename}")
