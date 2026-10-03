# Radar MQTT — estado del desarrollo

Documento para retomar el trabajo. Actualizado el 3 de octubre de 2026.

Cliente de Windows para escuchar un broker MQTT y publicar mensajes. La interfaz es Tkinter y la conexión usa Eclipse Paho (`paho-mqtt`).

Repositorio: https://github.com/edokope4/radar-mqtt

La app Android que publica el pedido está en `C:\develop\cafetera`. El servicio que avisa cuando el café está listo está en `C:\develop\cafetera-under-backend`.

## Qué hace

No se conecta al abrirse. Hay que pulsar **Comenzar a escuchar**.

- Brokers guardados: nombre, host, puerto, usuario, contraseña, TLS, identificador de cliente, tópicos (uno por línea, se pueden desactivar) y QoS. El puerto habitual es 1883 sin TLS y 8883 con TLS.
- Payloads guardados con nombre. Si el texto del mensaje coincide, el registro lo marca con ese nombre. **Mostrar solo estos payloads** oculta el resto.
- Ventana de publicación: broker, tópico, QoS, retain y cuerpo del mensaje.
- Favoritos de publicación. Guardan nombre, broker, tópico, cuerpo, QoS y retain. **Guardar en favoritos** pide el nombre y, si ya existe, pregunta si se reemplaza. **Cargar** rellena el formulario. **Quitar** borra el favorito elegido. Si el broker de ese favorito ya no existe, se carga el resto y se avisa.
- Tema oscuro, guardado en la configuración. También se puede exportar e importar el JSON de ajustes.

## Dónde se guardan los datos

`%APPDATA%\RadarMqtt\config.json`. No está en el repositorio.

Una configuración vieja, sin la clave `favorites`, se abre con la lista de favoritos vacía.

El primer inicio crea un broker de ejemplo (`test.mosquitto.org`, tópico `cafetera/hacer`, payload `hacer`, nombre «Hacer café»). Ese ejemplo no coincide con el contrato actual de la cafetera:

| Uso | Tópico | Cuerpo |
| --- | --- | --- |
| Pedido desde el teléfono | `cl/kope/iot/cafetera` | `{"action": "turn-on","pulso_ms": 500}` |
| Aviso de café listo | `cl/kope/iot/cafetera/status` | `{"code": 4, "message": "Cafe listo"}` |
| Orden que republica el backend | `cl/kope/iot/cafetera` | el mismo JSON con `"action": "turn-off"` |

Para ver el pulso hay que poner esos tópicos en Radar, o guardarlos como favoritos de publicación. Si el programa ya se abrió, el JSON de ejemplo no se vuelve a crear solo.

## Ejecutar

```powershell
cd C:\develop\radar-mqtt
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Ejecutable

```powershell
cd C:\develop\radar-mqtt
.\build.bat
```

`build.bat` crea `.venv`, instala las dependencias y genera `dist\RadarMqtt.exe` con PyInstaller. Si el exe está abierto, el empaquetado no puede reemplazarlo. Hay que cerrar Radar MQTT y volver a ejecutar `build.bat`. El exe que quedó de una compilación anterior no incluye los favoritos hasta que se regenere.

Código: `main.py`, `radar_mqtt/app.py`, `radar_mqtt/storage.py`.

## Pendiente

- El broker de ejemplo y el payload «Hacer café» siguen en `cafetera/hacer` / `hacer`.
- Parte de los textos viejos de la interfaz usa voseo («Elegí», «Escribí»). Los de favoritos están en español neutro.
- Licencia BSD 2-Clause, en `LICENSE`.
