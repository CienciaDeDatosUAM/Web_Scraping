from bs4 import BeautifulSoup  # Para analizar y extraer datos de HTML y XML
from glob import glob  # Para buscar archivos y directorios
import requests  # Para realizar solicitudes HTTP
import youtube_dl  # Para descargar videos de YouTube
import json  # Para trabajar con datos en formato JSON
import os  # Para interactuar con el sistema operativo
from googleapiclient.discovery import build  # Para interactuar con las APIs de Google
from datetime import datetime  # Para trabajar con fechas y horas

class ApiYoutubeVideos:
    def __init__(self, API_KEY):
        self.API_KEY = API_KEY



    def obtener_comentarios(self,video_id, out_dir):
        youtube = build('youtube', 'v3', developerKey=self.API_KEY)
        comments = []
        try:
            response = youtube.commentThreads().list(
                part='snippet,replies',
                videoId=video_id,
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
                
                if 'nextPageToken' in response:
                    response = youtube.commentThreads().list(
                        part='snippet,replies',
                        videoId=video_id,
                        pageToken=response['nextPageToken'],
                        maxResults=100,
                        textFormat='plainText'
                    ).execute()
                else:
                    break
        except HttpError as e:
            print(f"An HTTP error {e.resp.status} occurred: {e.content}")

        info_fechas = self.obtener_info_fechas_video(video_id)
        info_json = {
            "fecha_recoleccion": info_fechas["fecha_recoleccion"],
            "hora_recoleccion": info_fechas["hora_recoleccion"],
            "fecha_publicacion": info_fechas["fecha_publicacion"],
            "hora_publicacion": info_fechas["hora_publicacion"],
            "nombre_canal":info_fechas["nombre_canal"],
            "comentarios": comments
        }

        comentarios_dir = os.path.join(out_dir, "comentarios")
        os.makedirs(comentarios_dir, exist_ok=True)
        json_file_path = os.path.join(comentarios_dir, "test.json")
        with open(json_file_path, 'w', encoding='utf-8') as json_file:
            json.dump(info_json, json_file, ensure_ascii=False, indent=4)

    """
    def obtener_comentarios(self,video_id, out_dir):
        comentarios_dir = os.path.join(out_dir, "comentarios")
        os.makedirs(comentarios_dir, exist_ok=True)

        video_info = requests.get("https://www.googleapis.com/youtube/v3/videos", params={"id": video_id, "part": "snippet", "key": self.API_KEY})

        if video_info.status_code == 200 and video_info.json()["items"]:
            video_title = video_info.json()["items"][0]["snippet"]["title"]
            nombre_archivo = "".join(char for char in video_title if char.isalnum() or char in " -_").rstrip()
        else:
            raise ValueError(f"No se pudo obtener información para el video ID {video_id}")

        json_file_path = os.path.join(comentarios_dir, f"{nombre_archivo}.json")

        params = {
            "key": self.API_KEY,
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

        info_fechas = self.obtener_info_fechas_video(video_id)
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

    """


    def descargar_subtitulos(self,video_id, out_dir):

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

    def limpiar_subtitulos(self,video_id, out_dir):
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

            info_fechas = self.obtener_info_fechas_video(video_id)
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
            
    def obtener_info_fechas_video(self,video_id: str):
        youtube = build('youtube', 'v3', developerKey=self.API_KEY)
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

    def leer_lista_videos_desde_json(self,ruta_archivo, ids_videos):

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

