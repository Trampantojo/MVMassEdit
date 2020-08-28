<h1 align="center">
  <div>MediaVida - Mass Edit Tool</div>
</h1>


## Argumentos

| Corto | Largo | Descripción | Por defecto | Requerido |
|-------|-------|-------------|-------------|-----------|
| -h | --help | Muestra información | | No |
| -u | --user | Usuario | | Sí |
| -t | --token | Hash de sesión | | Sí** |
| -m | --message | El nuevo mensaje ha escribir | . | No |
| -d | --delay | Tiempo (en segundos) entre que se envían las peticiones | 2 | No |
|    | --omit-first | Omite la edición del post principal de un hilo | False | No |

** El hash de sesión será solicitado por el script si no se especifica como parámetro de entrada (-t|--token).
** Se recomienda dejar que el script solicite el hash de sesion para evitar que se quede almacenado en el historico del terminal.

## Instalación

Puedes usar "pip" para instalar todo lo necesario para que el script funcione:
```pip install -r requirements.txt```

## Uso

Para usarse se necesita obtener el hash de sesión del usuario.
Esta cookie usa "HttpOnly" y para obtener el valor se tiene que abrir el panel de 'DevTools' pulsado CTRL+SHIFT+I e ir a la pestaña "Application" (Chrome) o "Storage" (Firefox), allí ir al apartado "Cookies" y copiar el valor de la cookie que se llama "sess".

- Ejemplo, editar todos los menajes de 'myuser' omitiendo el principal de los hilos:
    ```./MVMassEdit.py -u myuser --omit-first```

## Roadmap

- Mejorar el uso de multi-requests para tener en cuenta las ventanas de tiempo.
- Ver el motivo por el cual no edita algunos mensajes correctamente. Todo apunta a que es por la protección anti-flood que usa mediavida.