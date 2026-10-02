# Radar MQTT

Cliente de escritorio para suscribirse a un broker MQTT y reconocer payloads guardados. Cuando el texto de un mensaje coincide con uno de la lista, el registro muestra el nombre asociado.

La interfaz está hecha con Tkinter y la conexión usa [Eclipse Paho](https://eclipse.dev/paho/) (`paho-mqtt`).

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

1. Elige o crea un broker: nombre, host, puerto, usuario, contraseña, client id, QoS y TLS.
2. Escribe los tópicos, uno por línea. El puerto habitual es 1883 sin TLS y 8883 con TLS.
3. Guarda los payloads con un nombre y el texto exacto del mensaje. El valor predeterminado es el tópico `cafetera/hacer` y el payload `hacer`, etiquetado como «Hacer café».
4. Pulsa **Comenzar a escuchar**. Si activas **Mostrar solo estos payloads**, el registro oculta los mensajes que no coinciden.

La configuración se guarda en `%APPDATA%\RadarMqtt\config.json`.

## Ejecutable

`build.bat` crea el entorno virtual, instala las dependencias y genera `dist\RadarMqtt.exe` con PyInstaller.

## Licencia

BSD 2-Clause. Ver [LICENSE](LICENSE).
