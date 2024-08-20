# Alan David Ramírez Navarrete

## Contacto
- **Teléfono**: (+52) 5626265223
- **Correo Electrónico**: soft.dev.alan@gmail.com
- **FaceBook**: https://www.facebook.com/P00LLoo?mibextid=ZbWKwL
- **GitHub**: https://github.com/EssPollo
- **Youtube**:https://www.youtube.com/@AlanPolloNavarrete

## Acerca de mí
Hola que tal ! Bienvenido a mi REDMI. Conocido en el bajo mundo como "pollo" , Ingeniero de Software,Univesidad Autonoma de la Ciudad de México. Amante del GYM pero tambien de la comida grasosa.
Si tienes alguna duda porfavor de contactarme a mis redes sociales o mi correo. Juntos podemos ser mejores ingenieros!
## Proyecto:  Extracción de Datos de YouTube
Proporcionar una guía detallada sobre cómo llevar a cabo la extracción de datos de YouTube utilizando su API.
El objetivo es recopilar información relevante de videos, canales y listas de reproducción para análisis y aplicaciones diversas.

### Tecnologías utilizadas
- **Python**
- **YouTube Data API**
- **Pandas**
- **BeautifulSoup**
- **json**
- **lxml**
- **beautifulsoup4**
- **requests**

## Ejecución del Proyecto

### Requisitos Previos:
Antes de ejecutar el proyecto, es necesario instalar **Docker**. Docker permite crear contenedores que empaquetan el software de manera que pueda ejecutarse de manera consistente en cualquier máquina. Puedes descargarlo e instalarlo desde el [sitio web oficial de Docker](https://www.docker.com/products/docker-desktop).

### Pasos para Ejecutar el Proyecto:
1. **Abrir la Terminal**:
   - Abre una terminal o línea de comandos en tu computadora.
  
2. **Navegar al Directorio del Proyecto**:
   - Utiliza el comando `cd` para cambiar al directorio donde se encuentra tu proyecto. Debes estar en el mismo directorio que el archivo `docker-compose.yml`.
   - Ejemplo: Si tu proyecto está en el escritorio, podrías escribir:
     ```bash
     cd Desktop/miProyecto
     ```

3. **Iniciar Docker Compose**:
   - Ejecuta el siguiente comando para construir e iniciar los servicios definidos en tu archivo `docker-compose.yml`:
     ```bash
     docker-compose up
     ```
   - Este comando descargará las imágenes necesarias y creará contenedores basados en las instrucciones del archivo `docker-compose.yml`.

4. **Acceder a un Contenedor mediante VSCode**:
   - Una vez que los contenedores estén en funcionamiento, abre Visual Studio Code (VSCode).
   - Utiliza la funcionalidad **Attach Shell** en VSCode para conectarte al contenedor que está ejecutando tu aplicación.
   - Dirígete a la vista de Docker en VSCode, encuentra tu contenedor activo, haz clic derecho sobre él y selecciona "Attach Shell".

5. **Navegar Dentro del Contenedor**:
   - Dentro de la terminal de VSCode, utiliza el comando `cd` para moverte a la carpeta que contenga el script que deseas ejecutar. Esto podría ser una de las siguientes: `Canal`, `Playlist`, o `Video`.
   - Ejemplo:
     ```bash
     cd Video
     ```

6. **Ejecutar el Script**:
   - Una vez en la carpeta correcta, ejecuta el archivo `youtube.py` con el siguiente comando:
     ```bash
     python3 youtube.py
     ```
   - Este comando iniciará la ejecución del script, y deberías comenzar a ver resultados en la terminal.

### Finalización de la Ejecución:
- Si necesitas detener la ejecución de los contenedores, puedes hacerlo volviendo a tu terminal inicial donde ejecutaste `docker-compose up` y presionando `Ctrl+C` (en Windows/Linux) o `Cmd+C` (en macOS).
- Para cerrar completamente todos los servicios, utiliza:
  ```bash
  docker-compose down


## Contacto para el proyecto
Si estás interesado en cómo se realizó este proyecto paso a paso por favor contacta al:

**Dr. José Luis Quiroz Fabian**
- **Número de cubículo**: T-169
- **Ubicación**: Edificio T de CBI, Universidad Autónoma Metropolitana Unidad Iztapalapa
- **Telefono**: 58 04 46 00 ext. 1169
