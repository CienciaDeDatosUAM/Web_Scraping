from bs4 import BeautifulSoup
from glob import glob
import requests
import youtube_dl
import json
import os
from googleapiclient.discovery import build
from datetime import datetime

API_KEY = None

def obtener_comentarios(video_id, out_dir):
    """
    Recupera los comentarios de un video de YouTube y los guarda en formato JSON en el directorio especificado, organizándolos 
    bajo un subdirectorio comentarios. El nombre del archivo JSON se deriva del título del video, limpiado para asegurar compatibilidad 
    de nombres de archivo. Si no puede obtenerse la información del video o falla la solicitud de comentarios, se lanza un ValueError 
    con detalles del problema.

    Args:
        video_id (str): El ID único del video de YouTube cuyos comentarios se quieren obtener.
        out_dir (str): Ruta base para los archivos de salida.

    Raises:
        ValueError: Indica fallos al obtener la información del video con el ID proporcionado o errores en la solicitud a la API de 
        YouTube para obtener los comentarios de un video.
    """
    comentarios_dir = os.path.join(out_dir, "comentarios")
    os.makedirs(comentarios_dir, exist_ok=True)

    video_info = requests.get("https://www.googleapis.com/youtube/v3/videos", params={"id": video_id, "part": "snippet", "key": API_KEY})

    if video_info.status_code == 200 and video_info.json()["items"]:
        video_title = video_info.json()["items"][0]["snippet"]["title"]
        nombre_archivo = "".join(char for char in video_title if char.isalnum() or char in " -_").rstrip()
    else:
        raise ValueError(f"No se pudo obtener información para el video ID {video_id}")

    json_file_path = os.path.join(comentarios_dir, f"{nombre_archivo}.json")

    params = {
        "key": API_KEY,
        "part": "snippet,replies",
        "videoId": video_id,
    }
    response = requests.get("https://youtube.googleapis.com/youtube/v3/commentThreads", params=params)
    comentarios = None
    if response.status_code == 200:
        json_response = response.json()
        items = json_response.get("items", [])
        comentarios = [item["snippet"]["topLevelComment"]["snippet"]["textOriginal"] for item in items] if items else None
    else:
        raise ValueError(f"Error en la solicitud a la API: {response.status_code}")

    info_fechas = obtener_info_fechas_video(video_id)
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


def descargar_subtitulos(video_id, out_dir):
    """
    Descarga subtítulos automáticos en español de un video de YouTube, almacenándolos en el directorio proporcionado 
    bajo un subdirectorio raw. Crea el directorio si no existe. Actualiza las opciones de descarga para incluir solo 
    subtítulos automáticos en formato TTML y lenguaje español, sin descargar el video. Genera un error si la descarga falla.

    Args:
        ID del video (str): Identificador único de YouTube para el video objetivo.
        Directorio proporcionado (str): Ruta base para almacenar los subtítulos descargados.

    Raises:
        ValueError: Se lanza si la descarga de subtítulos falla, proporcionando el ID del video y detalles del error.
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

        opciones["outtmpl"] = os.path.join(raw_output, "%(title)s_ID:%(id)s.%(ext)s")
        ydl.params.update(opciones)
        try:
            ydl.download([video_id])
        except Exception as e:
            raise ValueError(f"No se pudo descargar el video {video_id}: {e}")


def limpiar_subtitulos(video_id, out_dir):
    """
    Encuentra y procesa el subtítulo con extensión `es.ttml` del ID especificado dentro del directorio 
    proporcionado, extrayendo el texto limpio y los metadatos relevantes. El resultado se almacena en un 
    archivo JSON dentro de un subdirectorio clean del directorio proporcionado. Genera un error ValueError 
    si no encuentra exactamente un archivo correspondiente o si ocurre un error durante el procesamiento.

    Args:
        video_id (str): Identificador del video.
        out_dir (str): Directorio proporcionado para los archivos de entrada y salida.
    
    Raises:
        ValueError: Se produce por archivo no encontrado o error en el procesamiento.
    """
    raw_output = os.path.join(out_dir, "raw")
    clean_output = os.path.join(out_dir, "clean")

    archivos_subtitulos = glob(os.path.join(raw_output, f"*{video_id}.es.ttml"))

    if len(archivos_subtitulos) == 1:
        archivo_subtitulos = archivos_subtitulos[0]
    else:
        raise ValueError(f"Error: Se esperaba encontrar un solo archivo para el video_id {video_id}, pero se encontraron {len(archivos_subtitulos)} archivos.")

    os.makedirs(clean_output, exist_ok=True)

    try:
        with open(archivo_subtitulos, "r") as input_f:
            soup = BeautifulSoup(input_f, "xml")
            subtitulos_limpios = soup.text.strip()

        nombre_archivo = os.path.splitext(os.path.basename(archivo_subtitulos))[0]

        info_fechas = obtener_info_fechas_video(video_id)
        info_json = {
            "fecha_recoleccion": info_fechas["fecha_recoleccion"],
            "hora_recoleccion": info_fechas["hora_recoleccion"],
            "fecha_publicacion": info_fechas["fecha_publicacion"],
            "hora_publicacion": info_fechas["hora_publicacion"],
            "nombre_canal": info_fechas["nombre_canal"],
            "subtitulos": subtitulos_limpios
        }

        json_file_path = os.path.join(clean_output, f"{nombre_archivo}.json")
        with open(json_file_path, 'w', encoding='utf-8') as json_file:
            json.dump(info_json, json_file, ensure_ascii=False, indent=4)

    except Exception as e:    
        raise ValueError(f"Ocurrió un error al procesar el archivo: {e}")
        
def obtener_info_fechas_video(video_id: str):
    """
    Obtiene la fecha de publicación y el nombre del canal de un video de YouTube por su ID. 
    Registra también la fecha y hora de la consulta. Si no se encuentra el video, retorna None. 
    Si hay un error en el procesamiento de la fecha, lanza ValueError.

    Args:
        video_id (str): El ID del video de YouTube.

    Returns:
        dict | None: Diccionario con fecha y hora de publicación y recolección, y nombre del canal, o None si el video no existe.

    Raises:
        ValueError: Si hay un problema al procesar la fecha de publicación.
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

def leer_lista_videos_desde_json(ruta_archivo, ids_videos):
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

        videos = data.get('campos', [])
        llave = data['llave']
        
        if not llave:
            raise ValueError("La llave proporcionada en el archivo JSON está ausente o es inválida.")

        if "All" in ids_videos:
            if len(ids_videos) == 1:
                return llave, videos
            else:
                raise ValueError("No se puede mezclar 'All' con otros IDs de videos.")
        elif isinstance(ids_videos, str):
            ids_videos = [ids_videos]

        videos_filtrados = [video for video in videos if video["idVideo"] in ids_videos]

        return llave, videos_filtrados


def main():
    global API_KEY
    ruta_archivo_json = './videos.json'
    id_video_deseado = ["All"]
    
    try:
        API_KEY, videos = leer_lista_videos_desde_json(ruta_archivo_json, id_video_deseado)

        for video in videos:

            descargar_subtitulos(video["idVideo"], "./Youtube/subtitulos")
            limpiar_subtitulos(video["idVideo"], "./Youtube/subtitulos")
            obtener_comentarios(video["idVideo"], "./Youtube")

    except ValueError as e:
        print(e)

    

if __name__ == "__main__":
    main()