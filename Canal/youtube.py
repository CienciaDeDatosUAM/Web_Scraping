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

    with open(ruta_json, 'r') as archivo_json:
        data = json.load(archivo_json)
        return data.get("tokenActual", "")

def guardar_token_actual(ruta_json, token):

    with open(ruta_json, 'r+') as archivo_json:
        data = json.load(archivo_json)
        archivo_json.seek(0) 
        data["tokenActual"] = token
        json.dump(data, archivo_json, indent=4)
        archivo_json.truncate()
        
def verificar_token(ruta_json):

    token_actual = leer_token_actual(ruta_json)
    return bool(token_actual)

def buscar_videos_canal(canalID: str, busqueda: str,  fecha_inicio: str, fecha_fin: str, ruta_json: str, position: int, max_results: int = 20):
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
    año = fecha_publicacion.strftime('%Y')
    mes_nombre = calendar.month_name[int(fecha_publicacion.strftime('%m'))]
    ruta_año_mes = os.path.join(base_dir, año, mes_nombre)
    ruta_fecha_completa = os.path.join(ruta_año_mes, fecha_publicacion.strftime('%Y-%m-%d'))
    return ruta_fecha_completa

def validar_y_ajustar_fechas(fecha_inicio_str, fecha_fin_str):
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