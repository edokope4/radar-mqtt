# Radar MQTT

Cliente de escritorio para Windows. Se suscribe a uno o más brokers MQTT, publica mensajes y guarda lo recibido. La interfaz está hecha con Tkinter y la conexión usa [Eclipse Paho](https://eclipse.dev/paho/) (`paho-mqtt`). Versión 1.0.0.

Este proyecto ha sido desarrollado con la ayuda de [Cursor](https://cursor.com).

## Requisitos

- Python 3 con Tkinter
- Windows, para el script de empaquetado y el ajuste de DPI

## Ejecutar

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

## Uso

La ventana no se conecta al abrirse. Abajo está **Comenzar a escuchar**. El menú **Ver** abre las pestañas **Brokers**, **Escuchar**, **Publicar**, **Mensajes Recibidos** y **Archivo**. **Ver → Oscuro** cambia el tema. **Ver → Acerca de...** muestra la versión y el enlace al repositorio.

1. En **Brokers**, elegí o creá un broker: nombre, host, puerto, usuario, contraseña, client id, QoS y TLS. El puerto habitual es 1883 sin TLS y 8883 con TLS.
2. Agregá tópicos a la lista. Desmarcar uno lo deja guardado, pero no se escucha.
3. En **Escuchar**, marcá los brokers que deben conectarse y, debajo de cada uno, los tópicos activos. Es la misma lista que en **Brokers**: un cambio en una pestaña queda en la otra. **Comenzar a escuchar** usa solo los brokers marcados y omite los que no tengan un tópico activo.
4. En **Publicar**, elegí broker, tópico, QoS, si el mensaje queda retenido, y el cuerpo. **Guardar en favoritos** pide un nombre. **Cargar** rellena el formulario. **Quitar** borra el favorito elegido.
5. **Mensajes Recibidos** muestra la hora, el broker y el tópico. Si el cuerpo es JSON, se ve en una línea y con color. **Copiar** copia ese texto. Si el cuerpo coincide exactamente con un payload con nombre guardado en la configuración, el registro muestra ese nombre. El primer inicio incluye el ejemplo «Hacer café» para el texto `hacer`.
6. **Archivo** lista el último mes. La hora de recepción incluye milisegundos. Abajo se ve el mensaje elegido, en texto plano o como JSON indentado. **Copiar** copia lo que se está viendo. Junto al visor está el MD5 del payload recibido: si dos mensajes tienen el mismo código, el contenido es el mismo. **Borrar** quita el mensaje seleccionado y **Limpiar todo** vacía la lista. La selección se mantiene cuando la lista se actualiza.

Los límites entre la lista y el detalle de **Archivo** se pueden arrastrar. Si el contenido no entra, aparece una barra de desplazamiento.

La configuración se guarda en `%APPDATA%\RadarMqtt\config.json`. También se puede exportar e importar desde el menú **Broker**.

Los mensajes quedan en `%APPDATA%\RadarMqtt\inbox.db`, tabla `INBOX`: `fecha_recepcion`, `broker`, `topico`, `payload` y `qos`. Una base anterior recibe la columna `broker` al abrirse; las filas viejas quedan con ese campo vacío.

## Ejecutable

`build.bat` crea el entorno virtual, instala las dependencias y genera `dist\RadarMqtt.exe` con PyInstaller. Si el ejecutable está abierto, hay que cerrarlo antes de volver a compilar.

## Licencia

BSD 2-Clause. Ver [LICENSE](LICENSE).
