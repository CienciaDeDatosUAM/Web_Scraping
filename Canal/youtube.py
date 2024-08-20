from bs4 import BeautifulSoup
from glob import glob
import requests
import youtube_dl
import json
import os
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta, timezone
import calendar

API_KEY = None

def leer_token_actual(ruta_json):
    """
    Lee y devuelve el valor del token actual almacenado en el archivo JSON especificado. Si el token no existe, devuelve una cadena vacía.

    Args:
        ruta_json (str): La ruta al archivo JSON de donde leer el token.

    Returns:
        str: El valor del token actual. Devuelve una cadena vacía si el token no está presente.
    """
    with open(ruta_json, 'r') as archivo_json:
        data = json.load(archivo_json)
        return data.get("tokenActual", "")

def guardar_token_actual(ruta_json, token):
    """
    Guarda o actualiza el valor del token actual en el archivo JSON especificado. Si el archivo ya contiene un token, este se reemplaza con el nuevo valor.

    Args:
        ruta_json (str): La ruta al archivo JSON donde se guardará el token.
        token (str): El valor del token a guardar.
    """
    with open(ruta_json, 'r+') as archivo_json:
        data = json.load(archivo_json)
        archivo_json.seek(0) 
        data["tokenActual"] = token
        json.dump(data, archivo_json, indent=4)
        archivo_json.truncate()
        
def verificar_token(ruta_json):
    """
    Verifica si existe un token actual en el archivo JSON especificado. Devuelve verdadero si hay un token, falso si el token está vacío o no existe.

    Args:
        ruta_json (str): La ruta al archivo JSON que contiene el token a verificar.

    Returns:
        bool: Verdadero si existe un token, falso en caso contrario.
    """
    token_actual = leer_token_actual(ruta_json)
    return bool(token_actual)

def buscar_videos_canal(canalID: str, busqueda: str,  fecha_inicio: str, fecha_fin: str, ruta_json: str, position: int, max_results: int = 20):
    """
    Realiza una búsqueda en YouTube dentro de un canal específico utilizando criterios de búsqueda y un rango de fechas. 
    Guarda el token de la página siguiente para continuar la búsqueda en futuras solicitudes. Los resultados se filtran 
    por fecha y solo se incluyen aquellos dentro del rango especificado. La función retorna un diccionario con la información 
    de los videos encontrados y la posición actual para la continuación de la búsqueda.

    Args:
        canalID (str): El ID único del canal de YouTube donde se realiza la búsqueda.
        busqueda (str): Palabras clave de búsqueda.
        fecha_inicio (str): Fecha de inicio del rango de búsqueda en formato ISO.
        fecha_fin (str): Fecha de fin del rango de búsqueda en formato ISO.
        ruta_json (str): Ruta al archivo JSON donde se guarda el token de la página actual de resultados.
        position (int): La posición inicial para el conteo de videos encontrados.
        max_results (int, opcional): Número máximo de resultados por página. Por defecto es 20.

    Raises:
        ValueError: Si la solicitud a la API de YouTube falla, proporcionando detalles del error.
    
    Returns:
        tuple: Diccionario con los videos encontrados y la posición actual para continuar la búsqueda. 
        Cada video en el diccionario incluye la fecha de publicación y el ID del video.

    """
    fecha_inicio_datetime = datetime.fromisoformat(fecha_inicio.rstrip('Z'))
    fecha_fin_datetime = datetime.fromisoformat(fecha_fin.rstrip('Z'))
    info_videos = {}

    token_actual = leer_token_actual(ruta_json)
    params = {
        "key": API_KEY,
        "part": "snippet,id",
        "q": busqueda,
        "maxResults": str(max_results),
        "channelId": canalID,
        "type": "video",
        "order": "date",
        "pageToken": token_actual 
    }

    response = requests.get("https://www.googleapis.com/youtube/v3/search", params=params)
    response_json = response.json()
    items = response_json.get("items", [])
    
    if response.status_code != 200:
        errors = response_json.get("error", {}).get("errors", [])
        if errors:
            for error in errors:
                raise ValueError(f"Error: {error.get('message')} (Reason: {error.get('reason')})")
        return None
    
    for item in items:
        print(f"ID: {item['id']['videoId']}, Fecha: {item['snippet']['publishedAt']} \n")
        publishedAt = datetime.fromisoformat(item["snippet"]["publishedAt"].rstrip('Z'))

        if  fecha_inicio_datetime <= publishedAt <= fecha_fin_datetime:
            videoId = item["id"]["videoId"]
            info_videos[position]= {
                "publishedAt": publishedAt.isoformat(),
                "videoId": videoId
            }
            position = position + 1

    if not items or any(fecha_inicio_datetime > datetime.fromisoformat(item["snippet"]["publishedAt"].rstrip('Z')) for item in items):
        guardar_token_actual(ruta_json, "")
    else:
        nextPageToken = response_json.get("nextPageToken", "")
        guardar_token_actual(ruta_json, nextPageToken)
        
    return info_videos, position 

def obtener_comentarios(video_ids: list[dict], out_dir: str):
    """
    Recupera y guarda en formato JSON los comentarios de múltiples videos de YouTube, utilizando una lista de diccionarios que contienen 
    los IDs de los videos y sus fechas de publicación. Los archivos se organizan en directorios nombrados según la fecha de publicación 
    de cada video, bajo un directorio principal comentarios. Si la información del video no se puede obtener o si hay un fallo en la 
    solicitud de comentarios, se interrumpe el proceso para ese video y se lanza un ValueError.

    Args:
        video_ids (list[dict]): Lista de diccionarios con el ID de cada video y su fecha de publicación.
        out_dir (str): Directorio base donde se guardarán los archivos de comentarios.

    Raises:
        ValueError: Se lanza si no se puede obtener la información de un video o si hay un error en la solicitud de comentarios, indicando 
        el ID del video y el error específico.
    """
    comentarios_dir = os.path.join(out_dir, "comentarios")
    os.makedirs(comentarios_dir, exist_ok=True)

    for key, value in video_ids.items():
        fecha_publicacion = datetime.fromisoformat(value["publishedAt"].rstrip('Z'))
        fecha_comentarios_dir = construir_ruta_fecha(fecha_publicacion, comentarios_dir)
        os.makedirs(fecha_comentarios_dir, exist_ok=True)

        video_info = requests.get("https://www.googleapis.com/youtube/v3/videos", params={"id": value["videoId"], "part": "snippet", "key": API_KEY})
        if video_info.status_code == 200 and video_info.json()["items"]:
            video_title = video_info.json()["items"][0]["snippet"]["title"]
            nombre_archivo = "".join(char for char in video_title if char.isalnum() or char in " -_").rstrip()
        else:
            raise ValueError(f"No se pudo obtener información para el video ID {value['videoId']}")

        json_file_path = os.path.join(fecha_comentarios_dir, f"{nombre_archivo}.json")

        params = {
            "key": API_KEY,
            "part": "snippet,replies",
            "videoId": value["videoId"],
        }
        response = requests.get("https://youtube.googleapis.com/youtube/v3/commentThreads", params=params)
        comentarios = None
        if response.status_code == 200:
            json_response = response.json()
            items = json_response.get("items", [])
            comentarios = [item["snippet"]["topLevelComment"]["snippet"]["textOriginal"] for item in items] if items else None
        else:
            raise ValueError(f"Error en la solicitud a la API: {response.status_code}")

        info_fechas = obtener_info_fechas_video(value["videoId"])
        info_json = {
            "fecha_recoleccion": info_fechas["fecha_recoleccion"],
            
            "hora_recoleccion": info_fechas["hora_recoleccion"],
            "fecha_publicacion": info_fechas["fecha_publicacion"],
            "hora_publicacion": info_fechas["hora_publicacion"],
            "nombre_canal":info_fechas["nombre_canal"],
            "comentarios": comentarios
        }

        with open(json_file_path, 'w', encoding='utf-8') as json_file:
            json.dump(info_json, json_file, ensure_ascii=False, indent=4)
            
            

def descargar_subtitulos(video_ids: list[dict], out_dir: str):
    """
    Descarga subtítulos automáticos en español para una lista de videos de YouTube, almacenando los archivos en un 
    directorio organizado por la fecha de publicación de cada video. Crea los directorios necesarios si no existen y 
    configura las opciones para obtener solo subtítulos en formato TTML y en español, sin descargar los videos. 
    Lanza un ValueError si ocurre un error durante la descarga de algún subtítulo.

    Args:
        video_ids (list[dict]): Lista de diccionarios, cada uno conteniendo el ID del video y su fecha de publicación.
        out_dir (str): Ruta base para los directorios de salida, donde se guardarán los subtítulos.

    Raises:
        ValueError: Informa fallos en la descarga de subtítulos, indicando el video específico y el error ocurrido.
    """
    raw_output = os.path.join(out_dir, "raw")
    if not os.path.exists(raw_output):
        os.makedirs(raw_output)

    opciones = {
        "writeautomaticsub": True,
        "skip_download": True,
        "subtitlesformat": "ttml",
        "subtitleslangs": ["es"],
        "logtostderr": True,
    }

    with youtube_dl.YoutubeDL(opciones) as ydl:
        for key, value in video_ids.items():
            fecha_publicacion = datetime.fromisoformat(value["publishedAt"].rstrip('Z'))
            fecha_dir = construir_ruta_fecha(fecha_publicacion, raw_output)
            if not os.path.exists(fecha_dir):
                os.makedirs(fecha_dir)

            opciones["outtmpl"] = os.path.join(fecha_dir, "%(title)s_ID:%(id)s.%(ext)s")
            ydl.params.update(opciones)

            try:
                ydl.download([value["videoId"]])
            except Exception as e:
                raise ValueError(f"No se pudo descargar el video {value}: {e}")


def limpiar_subtitulos(video_ids: list[dict], out_dir: str):
    """
    Itera sobre la lista de IDs para procesar y limpiar subtítulos basándose en sus fechas de publicación, 
    guardando los resultados en formato JSON dentro de directorios organizados por fecha en el directorio 
    proporcionado. Cada subtítulo limpio se almacena junto con metadatos del video correspondiente. Si falla 
    al obtener información del video o al procesar subtítulos, lanza ValueError.

    Args:
        video_ids (list[dict]): Información de los videos, incluidos IDs y fechas de publicación.
        out_dir (str): Ruta base para directorios de entrada y salida.
    
    Raises:
        ValueError: Por problemas al obtener información de videos o al procesar subtítulos.
    """
    raw_output = os.path.join(out_dir, "raw")

    for key, value in video_ids.items():
        fecha_publicacion = datetime.fromisoformat(value["publishedAt"].rstrip('Z'))
        fecha_dir = construir_ruta_fecha(fecha_publicacion, raw_output)
        clean_fecha_dir = construir_ruta_fecha(fecha_publicacion, os.path.join(out_dir, "clean"))
        os.makedirs(clean_fecha_dir, exist_ok=True)

        archivos_subtitulos = glob(os.path.join(fecha_dir, "*.ttml"))

        for archivo_subtitulos in archivos_subtitulos:
            with open(archivo_subtitulos, "r") as input_f:
                soup = BeautifulSoup(input_f, "xml")
                subtitulos_limpios = soup.text.strip()

            nombre_archivo = os.path.splitext(os.path.basename(archivo_subtitulos))[0]
            video_id = nombre_archivo.split("_ID:")[-1].split('.es')[0]

            info_fechas = obtener_info_fechas_video(video_id)
            if info_fechas:
                info_json = {
                    "fecha_recoleccion": info_fechas["fecha_recoleccion"],
                    "hora_recoleccion": info_fechas["hora_recoleccion"],
                    "fecha_publicacion": info_fechas["fecha_publicacion"],
                    "hora_publicacion": info_fechas["hora_publicacion"],
                    "nombre_canal": info_fechas["nombre_canal"],
                    "subtitulos": subtitulos_limpios
                }

                json_file_path = os.path.join(clean_fecha_dir, f"{nombre_archivo}.json")
                with open(json_file_path, 'w', encoding='utf-8') as json_file:
                    json.dump(info_json, json_file, ensure_ascii=False, indent=4)
            else:
                raise ValueError(f"No se pudo obtener la información para el video {video_id}.")


        
def obtener_info_fechas_video(video_id: str):
    """
    Obtiene la fecha de publicación y el nombre del canal de un video de YouTube por su ID. 
    Registra también la fecha y hora de la consulta. Si no se encuentra el video, retorna None. 
    Si hay un error en el procesamiento de la fecha, lanza ValueError.

    Args:
        video_id (str): El ID del video de YouTube.

    Raises:
        ValueError: Si hay un problema al procesar la fecha de publicación.
    
    Returns:
        dict | None: Diccionario con fecha y hora de publicación y recolección, y nombre del canal, o None si el video no existe.
    """
    youtube = build('youtube', 'v3', developerKey=API_KEY)
    response = youtube.videos().list(
        part='snippet',
        id=video_id
    ).execute()

    if response['items']:
        snippet = response['items'][0]['snippet']
        fecha_publicacion = snippet['publishedAt']
        nombre_canal = snippet['channelTitle']

        try:
            fecha, hora = fecha_publicacion.split('T')
            hora = hora.rstrip('Z')
        except Exception as e:
            raise ValueError(f"Error al procesar la fecha_publicacion {fecha_publicacion}")
    else:
        return None
            
    fecha_actual = datetime.now().strftime("%Y-%m-%d")
    hora_actual = datetime.now().strftime("%H:%M:%S")

    info_json = {
        "fecha_recoleccion": fecha_actual,
        "hora_recoleccion": hora_actual,
        "fecha_publicacion": fecha,
        "hora_publicacion": hora,
        "nombre_canal": nombre_canal
    } 
    
    return info_json
 

def crear_ruta_canal(channel_id: str):
    """
    Crea un directorio basado en el título de un canal de YouTube, utilizando el ID del canal para consultar la API de YouTube y obtener el título. 
    Luego, estructura y crea un directorio con el nombre del canal, donde se puede almacenar información relevante acerca del canal. 
    Si la solicitud a la API falla o si la respuesta no contiene los datos esperados del canal, se lanza un ValueError indicando el problema específico.

    Args:
        channel_id (str): El ID único del canal de YouTube del cual obtener la información.

    Raises:
        ValueError: Se lanza si la solicitud a la API de YouTube falla, indicando el código de estado de la respuesta, 
                    o si la respuesta no contiene datos del canal, indicando que no se encontraron datos.

    Returns:
        str: La ruta del directorio creado para almacenar información del canal.
    """    
    youtube = build('youtube', 'v3', developerKey=API_KEY)
    try:
        response = youtube.channels().list(
            part='snippet,contentDetails,statistics',
            id=channel_id
        ).execute()
        
    except HttpError as e:
        raise ValueError(f"Error en la solicitud a la API de YouTube: {e.resp.status}, {e.content}")

    if response['items']:
        channel_info = response['items'][0]
        nombre_canal = channel_info['snippet']['title']
        nombre_canal = "".join(char for char in nombre_canal if char.isalnum() or char in " -_").rstrip()
        canal_dir = os.path.join("./YouTube", nombre_canal)
        os.makedirs(canal_dir, exist_ok=True)
            
        return canal_dir
    else:
        raise ValueError("No se encontraron datos para la lista de reproducción proporcionada.")

def construir_ruta_fecha(fecha_publicacion, base_dir):
    """
    Construye una ruta de directorio a partir de una fecha de publicación y un directorio base, organizando la estructura por año y mes.

    Args:
        fecha_publicacion (datetime): La fecha de publicación del contenido.
        base_dir (str): El directorio base para construir la ruta.

    Returns:
        str: La ruta completa construida con la fecha de publicación.
    """
    año = fecha_publicacion.strftime('%Y')
    mes_nombre = calendar.month_name[int(fecha_publicacion.strftime('%m'))]
    ruta_año_mes = os.path.join(base_dir, año, mes_nombre)
    ruta_fecha_completa = os.path.join(ruta_año_mes, fecha_publicacion.strftime('%Y-%m-%d'))
    return ruta_fecha_completa

def validar_y_ajustar_fechas(fecha_inicio_str, fecha_fin_str):
    """
    Valida y ajusta las fechas de inicio y fin para asegurar que la diferencia entre ellas no sea mayor de 7 días. Si la 
    fecha de inicio es posterior a la fecha de fin, devuelve `None` para ambas fechas.

    Args:
        fecha_inicio_str (str): Fecha de inicio en formato ISO.
        fecha_fin_str (str): Fecha de fin en formato ISO.

    Returns:
        tuple: Fechas ajustadas en formato ISO o `None` para ambas si la fecha de inicio es posterior a la fecha de fin.
    """
    fecha_inicio = datetime.fromisoformat(fecha_inicio_str.rstrip('Z'))
    fecha_fin = datetime.fromisoformat(fecha_fin_str.rstrip('Z'))

    diferencia = fecha_fin - fecha_inicio

    if diferencia < timedelta(days=0):
        return None, None

    if diferencia > timedelta(days=7):
        fecha_fin_ajustada = fecha_inicio + timedelta(days=7)
        fecha_fin_ajustada_str = fecha_fin_ajustada.isoformat() + 'Z'
        return fecha_inicio_str, fecha_fin_ajustada_str
    else:
        return fecha_inicio_str, fecha_fin_str
    
def obtener_fechas(fecha_inicio_str, fecha_fin_str, fecha_unica_str):
    """
    Determina y ajusta las fechas de inicio y fin basándose en los parámetros proporcionados. Gestiona casos para un 
    rango de fechas, una fecha única, o fechas predeterminadas basadas en la fecha actual.

    Args:
        fecha_inicio_str (str): Fecha de inicio en formato ISO.
        fecha_fin_str (str): Fecha de fin en formato ISO.
        fecha_unica_str (str): Una única fecha en formato ISO.

    Returns:
        tuple: Las fechas de inicio y fin ajustadas según la lógica de validación y ajuste en formato ISO.
    """
    global fechaInicio, fechaFin

    if fecha_inicio_str is not None and fecha_fin_str is not None and fecha_unica_str is None:
        fechaInicio, fechaFin = validar_y_ajustar_fechas(fecha_inicio_str, fecha_fin_str)
    else:
        if fecha_inicio_str is None and fecha_fin_str is None and fecha_unica_str is not None:
            fechaInicio = fecha_unica_str
            fecha = datetime.fromisoformat(fechaInicio.rstrip('Z'))
            fecha = fecha.replace(hour=23, minute=59, second=59)
            fechaFin = fecha.isoformat() + 'Z'
        else:
            if fecha_inicio_str is None and fecha_fin_str is None and fecha_unica_str is None:
                fecha = datetime.now() - timedelta(days=1)
                fecha = fecha.replace(hour=0, minute=0, second=0)
                fecha = fecha.replace(tzinfo=timezone.utc)
                fechaInicio = fecha.isoformat(timespec='seconds').replace('+00:00', '') + 'Z'
                fecha = fecha.replace(hour=23, minute=59, second=59)
                fecha = fecha.replace(tzinfo=timezone.utc)
                fechaFin = fecha.isoformat(timespec='seconds').replace('+00:00', '') + 'Z'
            else:
                fechaInicio = None
                fechaFin = None

    return fechaInicio, fechaFin

def leer_canales_desde_json(ruta_archivo, ids_canal):
    """
    Carga y filtra datos de videos desde un archivo JSON según IDs específicos. Retorna todos los videos si se especifica 'All'; 
    en caso contrario, aplica el filtro por los IDs dados. No admite la combinación de 'All' con otros IDs. Requiere que el JSON 
    contenga una 'llave' global y una lista de videos bajo 'campos'.

    Args:
        ruta_archivo (str): Ruta al archivo JSON.
        ids_videos (list[str] | str): IDs de videos a filtrar o "All" para todos.

    Raises:
        ValueError: Si "All" se combina con otros IDs o si la 'llave' en el archivo JSON está ausente o es inválida.

    Returns:
        tuple: (llave, videos_filtrados) donde `llave` es una cadena y `videos_filtrados` es una lista de diccionarios.
    """
    with open(ruta_archivo, 'r', encoding='utf-8') as archivo:
        data = json.load(archivo)

        canales = data.get('campos', [])
        llave = data['llave']
        
        if not llave:
            raise ValueError("La llave proporcionada en el archivo JSON está ausente o es inválida.")
        
        if "All" in ids_canal:
            if len(ids_canal) == 1:
                return llave, canales
            else:
                raise ValueError("No se puede mezclar 'All' con otros IDs de canales.")
        elif isinstance(ids_canal, str):
            ids_canal = [ids_canal]

        canales_filtradas = [canal for canal in canales if canal["idCanal"] in ids_canal]

        return llave, canales_filtradas

def main():
    global fechaInicio, fechaFin, API_KEY
    ruta_archivo_json = './canales.json'
    id_canal_deseada = ["All"]
    
    try:
        API_KEY, canales = leer_canales_desde_json(ruta_archivo_json, id_canal_deseada)

        for canal in canales:
            print(f"Playlist: {canal['nombreCanal']}\n")
            ruta_json = './token.json'

            fechaInicio, fechaFin = obtener_fechas(canal["fechaInicio"], canal["fechaFin"], canal["fechaUnica"])

            if fechaInicio is None and fechaFin is None:
                print(f"La playlist {canal['nombrePlaylist']} no tiene fechas válidas. \n")
                continue

            print(f"Fecha de inicio: {fechaInicio}, Fecha de fin: {fechaFin} \n")

            video_ids, posicion = buscar_videos_canal(canal["idCanal"], canal["busqueda"],fechaInicio, fechaFin, ruta_json, 0)
            print(f"Videos que pasaron: {video_ids} \n")
            ruta_carpeta = crear_ruta_canal(canal["idCanal"])
            descargar_subtitulos(video_ids, f"{ruta_carpeta}/subtitulos")
            limpiar_subtitulos(video_ids, f"{ruta_carpeta}/subtitulos")
            obtener_comentarios(video_ids, ruta_carpeta)

            while verificar_token(ruta_json):
                video_ids, posicion = buscar_videos_canal(canal["idCanal"],canal["busqueda"],fechaInicio, fechaFin, ruta_json, posicion)
                print(f"Videos que pasaron: {video_ids} \n")
                ruta_carpeta = crear_ruta_canal(canal["idCanal"])
                descargar_subtitulos(video_ids, f"{ruta_carpeta}/subtitulos")
                limpiar_subtitulos(video_ids, f"{ruta_carpeta}/subtitulos")
                obtener_comentarios(video_ids, ruta_carpeta)
    except ValueError as e:
        print(e)

    

if __name__ == "__main__":
    main()