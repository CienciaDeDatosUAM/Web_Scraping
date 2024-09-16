from Video.youtube import ApiYoutubeVideos

def main():
    ruta_archivo_json = './Video/videos.json'
    id_video_deseado = ["All"]
    
    try:
        api_youtube = ApiYoutubeVideos(API_KEY=None)
        API_KEY, videos = api_youtube.leer_lista_videos_desde_json(ruta_archivo_json, id_video_deseado)

        if not API_KEY:
            raise ValueError("API_KEY no puede ser None. Proporciona una clave API válida.")

        api_youtube.API_KEY = API_KEY  # Actualizar la clave API en la instancia de la clase

        for video in videos:
            api_youtube.descargar_subtitulos(video["idVideo"], "./Video/Youtube/subtitulos") #Especificar en donde se quiere guardar
            api_youtube.limpiar_subtitulos(video["idVideo"], "./Video/Youtube/subtitulos")
            api_youtube.obtener_comentarios(video["idVideo"], "./Video/Youtube")

    except ValueError as e:
        print(f"Error de valor: {e}")
    except Exception as e:
        print(f"Se ha producido un error inesperado: {e}")

if __name__ == "__main__":
    main()




