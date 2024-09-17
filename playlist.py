import os

def ejecutar_youtube_script():
    script_path = os.path.join(os.path.dirname(__file__), 'Playlist', 'youtube.py')
    os.chdir(os.path.dirname(script_path))
    os.system(f'python3 {script_path}')

if __name__ == "__main__":
    ejecutar_youtube_script()


