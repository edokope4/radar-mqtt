# Radar MQTT — estado del desarrollo

Documento para retomar el trabajo. Actualizado el 15 de octubre de 2026.

Cliente de Windows, versión 1.0.0, para escuchar varios brokers MQTT y publicar mensajes. La interfaz es Tkinter y la conexión usa Eclipse Paho (`paho-mqtt`).

Repositorio: https://github.com/edokope4/radar-mqtt

La app Android que publica el pedido está en `C:\develop\cafetera`. El servicio que avisa cuando el café está listo está en `C:\develop\cafetera-under-backend`.

## Qué hace

No se conecta al abrirse. Hay que pulsar **Comenzar a escuchar**, el botón fijo al pie de la ventana.

La ventana es un `ttk.Notebook` con cinco pestañas: **Brokers**, **Escuchar**, **Publicar**, **Mensajes Recibidos** y **Archivo**. El menú **Ver** abre esas pestañas, cambia el tema y muestra **Acerca de...** (nombre, versión `radar_mqtt.__version__`, autor DeContrabando.cl y el enlace de GitHub).

- Brokers guardados: nombre, host, puerto, usuario, contraseña, TLS, identificador de cliente, tópicos y QoS. Cada tópico es una fila con checkbox. Desmarcarlo no lo borra. El puerto habitual es 1883 sin TLS y 8883 con TLS.
- **Escuchar** lista los brokers guardados. Solo se conectan los marcados, y cada uno necesita al menos un tópico activo. La marca es `Broker.listen` y se guarda en el JSON. Un broker nuevo queda desmarcado. Cada conexión tiene su propia sesión (`_ListenSession`) y su cliente en `self.clients`. Si uno falla, los demás siguen. Publicar usa otro client id, `{client_id}-pub-{6 hex}`, para no echar a los que escuchan.
- Si el broker rechaza una suscripción, ese tópico se deja de escuchar. En MQTT 3.1.1 un SUBACK denegado cierra la sesión.
- Publicación: broker, tópico, QoS, retain y cuerpo. Los favoritos guardan nombre, broker, tópico, cuerpo, QoS y retain. **Guardar en favoritos** pide el nombre y, si ya existe, pregunta si se reemplaza. **Cargar** rellena el formulario. **Quitar** borra el favorito elegido. Si el broker de ese favorito ya no existe, se carga el resto y se avisa.
- **Mensajes Recibidos** muestra `HH:MM:SS`, el broker y el tópico. El JSON va en una línea, coloreado. Cada mensaje tiene **Copiar**, que copia ese texto ya formateado. Si el cuerpo coincide exactamente con un payload con nombre de la configuración, el encabezado agrega ese nombre. Ya no hay pantalla para editar esos payloads ni el interruptor **Mostrar solo estos payloads**. La clave `only_saved_payloads` puede seguir en el JSON y la interfaz no la usa.
- **Archivo** es una pestaña, no una ventana aparte. La lista y el detalle se parten con un `PanedWindow` vertical. Columnas: `fecha_recepcion`, `broker`, `topico`, `payload` y `qos`. La hora guardada es `YYYY-MM-DD HH:MM:SS.mmm`. Al recargar, la fila seleccionada sigue seleccionada y el detalle no se borra. El detalle muestra texto plano o JSON indentado, y **Copiar** copia ese texto. **Borrar** (también Supr) y **Limpiar todo** piden confirmación.
- Tema claro: botones `#6577E2` y detalles `#E2CF65`. Tema oscuro: esos papeles se invierten sobre fondo gris `#3E3E3E`. El ícono de la ventana es `radar.png` y el del ejecutable es `radar.ico`.

## Dónde se guardan los datos

`%APPDATA%\RadarMqtt\config.json` guarda brokers, payloads, favoritos y el tema. `%APPDATA%\RadarMqtt\inbox.db` guarda la tabla `INBOX`. Ninguno de los dos está en el repositorio. `radar-mqtt.json`, en la raíz del proyecto, es una exportación local y tampoco se commitea.

Una base creada antes de la columna `broker` la recibe con `ALTER TABLE`. Esas filas quedan con `broker` vacío.

Una configuración vieja, sin la clave `favorites`, se abre con la lista de favoritos vacía. Sin la clave `listen`, el broker queda desmarcado.

El primer inicio crea un broker de ejemplo (`broker.hivemq.com`, tópico `cafetera/hacer`, payload `hacer`, nombre «Hacer café»). Ese ejemplo no coincide con el contrato actual de la cafetera:

| Uso | Tópico | Cuerpo |
| --- | --- | --- |
| Pedido desde el teléfono | `cl/kope/iot/cafetera` | `{"action": "turn-on","pulso_ms": 500}` |
| Aviso de café listo | `cl/kope/iot/cafetera/status` | `{"code": 4, "message": "Cafe listo"}` |
| Orden que republica el backend | `cl/kope/iot/cafetera` | el mismo JSON con `"action": "turn-off"` |

Para ver el pulso hay que poner esos tópicos en Radar, o guardarlos como favoritos de publicación. Si el programa ya se abrió, el JSON de ejemplo no se vuelve a crear solo.

## Ejecutar

```powershell
cd C:\develop\src\kp\radar-mqtt
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

No llamar `on_close` ni cambiar el tema en una prueba: ambos guardan `%APPDATA%\RadarMqtt\config.json`. Para cerrar una ventana de prueba, usar `root.destroy()`.

## Ejecutable

```powershell
cd C:\develop\src\kp\radar-mqtt
.\build.bat
```

`build.bat` crea `.venv`, instala las dependencias y genera `dist\RadarMqtt.exe` con PyInstaller (`--icon radar.ico` y `radar.png` como dato). Si el exe está abierto, el empaquetado no puede reemplazarlo. Hay que cerrar Radar MQTT y volver a ejecutar `build.bat`. No lanzar `build.bat` sin alguien delante: termina en `pause`. El lanzador `pyinstaller.exe` del venv puede apuntar a una ruta vieja; el script usa `python.exe -m PyInstaller`.

Código: `main.py`, `radar_mqtt/app.py`, `radar_mqtt/storage.py`, `radar_mqtt/inbox.py`. La retención del mes, el borrado y la columna `broker` se prueban con `py -3 -m unittest discover -s tests`.

## Pendiente

- El broker de ejemplo y el payload «Hacer café» siguen en `cafetera/hacer` / `hacer`.
- Los payloads con nombre ya no se editan en la interfaz. Siguen en el JSON y solo sirven para rotular el registro en vivo.
- Parte de los textos de la interfaz usa voseo («Elegí», «Marcá»).
- Licencia BSD 2-Clause, en `LICENSE`.
