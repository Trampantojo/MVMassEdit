<h1 align="center">
  <div>MediaVida - Mass Edit Tool</div>
</h1>


## Argumentos

| Corto | Largo | Descripción | Por defecto | Requerido |
|-------|-------|-------------|-------------|-----------|
| -h | --help | Muestra información | | No |
| -u | --user | Usuario | | Sí<sup>1</sup> |
| -t | --token | Hash de sesión | | Sí<sup>2</sup> |
| -m | --message | El nuevo mensaje ha escribir | . | No |
| -f | --file | Edita los posts declarados en el archivo | | No |
| -ra | --requests-amount | Cantidad de peteciones simultaneas | 3 | No |
| -mt | --max-tries | Numero de intentos antes de abortar la edición del mensaje | 3 | No |
| -d | --delay | Tiempo (en segundos) entre que se envían las peticiones | 2 | No |
| | --omit-first | Omite la edición del post principal de un hilo | False | No |

<font size="2">1. El parámetro es obligatorio si no se usa el parámetro ```-f|--file```.
2. El hash de sesión será solicitado por el script si no se especifica como parámetro de entrada ```-t|--token```. Recomiendo dejar que el script solicite el hash de sesion para evitar que se quede almacenado en el historico del terminal.</font>

** Recomiendo no tocar el parametro ```-ra|--requests-amount```. Debido a los mecanismos de la web de mediavida, incrementar la cantidad de peticiones solo hará que el script vaya más lento.


## Instalación

Puedes usar "pip" para instalar todo lo necesario para que el script funcione:

```pip install -r requirements.txt```


## Uso

Para usarse se necesita obtener el hash de sesión del usuario.
Esta cookie usa "HttpOnly" y para obtener el valor se tiene que abrir el panel de 'DevTools' del navegador pulsando CTRL+SHIFT+I e ir a la pestaña "Application" (Chrome) o "Storage" (Firefox), allí ir al apartado "Cookies" y copiar el valor de la cookie que se llama "sess".

- Ejemplo, editar todos los menajes de 'myuser' omitiendo el principal de los hilos:
    
    ```./MVMassEdit.py -u myuser --omit-first```

Tras ejecutarse el script se generarán dos archivos:
- mvmassedit.log - Contendrá un log con todo lo que ha sucedido en la última ejecución
- fails.json - Contendrá todas las url's de los posts que no han podido ser editados


## Hoja de Ruta / Errores conocidos

- Añadir una opción para 'cortar' la lista de posts, esto es menos agresivo que el filtro por fechas y permite una mínima personalización aproximada de lo que se va a editar.
- Añadir una opción para editar solo los mensajes que contengan una o varias palabras clave.