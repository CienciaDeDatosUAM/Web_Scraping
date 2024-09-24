from bs4 import BeautifulSoup
from glob import glob
import requests
import youtube_dl
import json
import os
from googleapiclient.discovery import build
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

def buscar_videos_playlist(playlistID: str, fecha_inicio: str, fecha_fin: str, ruta_json: str, max_results: int = 20):
    fecha_inicio_datetime = datetime.fromisoformat(fecha_inicio.rstrip('Z'))
    fecha_fin_datetime = datetime.fromisoformat(fecha_fin.rstrip('Z'))
    info_videos = {}

    token_actual = leer_token_actual(ruta_json)
    nextPageToken = None

    params = {
        "key": API_KEY,
        "part": "snippet",
        "maxResults": str(max_results),
        "playlistId": playlistID,
        "pageToken": nextPageToken if nextPageToken else token_actual 
    }

    response = requests.get("https://www.googleapis.com/youtube/v3/playlistItems", params=params)
    response_json = response.json()
    items = response_json.get("items", [])

    if response.status_code != 200:
        errors = response_json.get("error", {}).get("errors", [])
        if errors:
            for error in errors:
                raise ValueError(f"Error: {error.get('message')} (Reason: {error.get('reason')})")
        return None


    for item in items:
        print(f"ID: {item['snippet']['resourceId']['videoId']}, Fecha: {item['snippet']['publishedAt']} \n")
        publishedAt = datetime.fromisoformat(item["snippet"]["publishedAt"].rstrip('Z'))
        if  fecha_inicio_datetime <= publishedAt <= fecha_fin_datetime:
            videoId = item["snippet"]["resourceId"]["videoId"]
            position = item["snippet"]["position"]
            info_videos[position] = {
                "publishedAt": publishedAt.isoformat(),
                "videoId": videoId
            }

    if not items or any(fecha_inicio_datetime > datetime.fromisoformat(item["snippet"]["publishedAt"].rstrip('Z')) for item in items):
        guardar_token_actual(ruta_json, "")
    else:
        nextPageToken = response_json.get("nextPageToken", "")
        guardar_token_actual(ruta_json, nextPageToken)

    return info_videos

def obtener_comentarios(video_ids: dict, out_dir: str):
    youtube = build('youtube', 'v3', developerKey=API_KEY)

    for key, value in video_ids.items():
        comments = []  # Reiniciar comentarios para cada video
        fecha_publicacion = datetime.fromisoformat(value["publishedAt"].rstrip('Z'))

        response = youtube.commentThreads().list(
            part='snippet,replies',
            videoId=value["videoId"],
            maxResults=100,
            textFormat='plainText'
        ).execute()

        while response:
            for item in response['items']:
                comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                comments.append(comment)

                # Obtener respuestas a los comentarios
                if 'replies' in item:
                    for reply in item['replies']['comments']:
                        reply_comment = reply['snippet']['textDisplay']
                        comments.append(reply_comment)

            # Manejo de paginación
            if 'nextPageToken' in response:
                response = youtube.commentThreads().list(
                    part='snippet,replies',
                    videoId=value["videoId"],
                    pageToken=response['nextPageToken'],
                    maxResults=100,
                    textFormat='plainText'
                ).execute()
            else:
                break

        # Obtener información adicional del video
        info_fechas = obtener_info_fechas_video(value["videoId"])
        info_json = {
            "fecha_recoleccion": info_fechas["fecha_recoleccion"],
            "hora_recoleccion": info_fechas["hora_recoleccion"],
            "fecha_publicacion": info_fechas["fecha_publicacion"],
            "hora_publicacion": info_fechas["hora_publicacion"],
            "nombre_canal": info_fechas["nombre_canal"],
            "comentarios": comments
        }

        # Crear directorio para comentarios
        fecha_comentarios_dir = os.path.join(out_dir, "comentarios")
        os.makedirs(fecha_comentarios_dir, exist_ok=True)

        # Definir la ruta del archivo JSON
        video_info = requests.get("https://www.googleapis.com/youtube/v3/videos", params={"id": value["videoId"], "part": "snippet", "key": API_KEY})
        video_title = video_info.json()["items"][0]["snippet"]["title"]
        nombre_archivo = "".join(char for char in video_title if char.isalnum() or char in " -_").rstrip()
        #nombre_archivo = "".join(char for char in value["videoId"] if char.isalnum() or char in " -_").rstrip()
        json_file_path = os.path.join(fecha_comentarios_dir, f"{nombre_archivo}.json")

        # Guardar comentarios en un archivo JSON
        with open(json_file_path, 'w', encoding='utf-8') as json_file:
            json.dump(info_json, json_file, ensure_ascii=False, indent=4)

            

"""""""""
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
            continue

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
"""""                       
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

def crear_ruta_playlist(playlistID: str):
    params = {
        "key": API_KEY,
        "part": "snippet",
        "id": playlistID
    }

    response = requests.get(
        "https://www.googleapis.com/youtube/v3/playlists", params=params
    )
    
    if response.status_code != 200:
        raise ValueError(f"Error en la solicitud a la API de YouTube: código de estado {response.status_code}")

    data = response.json()

    if 'items' in data and data['items']:
        channel_info = data['items'][0]['snippet']
        nombre_canal = channel_info['channelTitle']
        nombre_playlist = channel_info['title']
        
        nombre_canal = "".join(char for char in nombre_canal if char.isalnum() or char in " -_").rstrip()

        canal_dir = os.path.join("./Youtube", nombre_canal, nombre_playlist)
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

def leer_playlists_desde_json(ruta_archivo, ids_playlist):
    with open(ruta_archivo, 'r', encoding='utf-8') as archivo:
        data = json.load(archivo)

        playlists = data.get('campos', [])
        llave = data['llave']
        
        if not llave:
            raise ValueError("La llave proporcionada en el archivo JSON está ausente o es inválida.")

        if "All" in ids_playlist:
            if len(ids_playlist) == 1:
                return llave, playlists
            else:
                raise ValueError("No se puede mezclar 'All' con otros IDs de playlists.")
        elif isinstance(ids_playlist, str):
            ids_playlist = [ids_playlist]

        playlists_filtradas = [playlist for playlist in playlists if playlist["idPlaylist"] in ids_playlist]
        return llave, playlists_filtradas

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
            fecha = datetime.fromisoformat(fecha_unica_str.rstrip('Z'))
            fechaInicio = fecha.replace(hour=0, minute=0, second=0)
            fechaInicio = fechaInicio.isoformat() + 'Z'
            fechaFin = fecha.replace(hour=23, minute=59, second=59)
            fechaFin = fechaFin.isoformat() + 'Z'
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

def main():
    global fechaInicio, fechaFin, API_KEY
    ruta_archivo_json = './playlists.json'
    id_playlist_deseada = ["All"]
    
    try:
        API_KEY, playlists = leer_playlists_desde_json(ruta_archivo_json, id_playlist_deseada)
        for playlist in playlists:
            print(f"Playlist: {playlist['nombrePlaylist']}\n")
            ruta_json = './token.json'

            fechaInicio, fechaFin = obtener_fechas(playlist["fechaInicio"], playlist["fechaFin"], playlist["fechaUnica"])

            if fechaInicio is None and fechaFin is None:
                print(f"La playlist {playlist['nombrePlaylist']} no tiene fechas válidas. \n")
                continue

            print(f"Fecha de inicio: {fechaInicio}, Fecha de fin: {fechaFin} \n")

            video_ids = buscar_videos_playlist(playlist["idPlaylist"], fechaInicio, fechaFin, ruta_json)
            print(f"Videos que pasaron: {video_ids} \n")
            ruta_carpeta = crear_ruta_playlist(playlist["idPlaylist"])
            descargar_subtitulos(video_ids, f"{ruta_carpeta}/subtitulos")
            limpiar_subtitulos(video_ids, f"{ruta_carpeta}/subtitulos")
            obtener_comentarios(video_ids, ruta_carpeta)

            while verificar_token(ruta_json):
                video_ids = buscar_videos_playlist(playlist["idPlaylist"],  fechaInicio, fechaFin, ruta_json)
                print(f"Videos que pasaron: {video_ids} \n")
                ruta_carpeta = crear_ruta_playlist(playlist["idPlaylist"])
                descargar_subtitulos(video_ids, f"{ruta_carpeta}/subtitulos")
                limpiar_subtitulos(video_ids, f"{ruta_carpeta}/subtitulos")
                obtener_comentarios(video_ids, ruta_carpeta)

    except ValueError as e:
        print(e)

if __name__ == "__main__":
    main()