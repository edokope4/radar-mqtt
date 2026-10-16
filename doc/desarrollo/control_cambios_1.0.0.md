# Control de Cambios — v1.0.0

**Versión:** 1.0.0
**Estado:** en curso
**Versión anterior liberada:** ninguna

---

## Resumen

| # | Cambio | Tipo | Requiere acción al instalar |
|---|--------|------|-----------------------------|
| 1 | En Archivo se ve el MD5 del mensaje para comprobar si dos payloads son iguales | Mejora | No |
| 2 | En Escuchar se elige, por cada broker, qué tópicos quedan activos | Mejora | No |

---

## 1. Comparar mensajes por su MD5

**Tipo:** Mejora · **Fecha:** 16/10/2026

**Situación anterior:** Para saber si dos mensajes guardados eran iguales había que revisar el contenido completo.

**Qué cambia:** Al elegir un mensaje en Archivo, junto al visor aparece el MD5 de ese payload. El mismo código indica el mismo contenido.

**Efecto para la operación:** Se puede comparar mensajes sin leer el texto entero. El código corresponde al payload tal como se recibió. El JSON indentado de la pantalla no cambia el MD5. Si no hay un mensaje elegido, el espacio queda vacío.

---

## 2. Elegir los tópicos al armar la escucha

**Tipo:** Mejora · **Fecha:** 16/10/2026

**Situación anterior:** En Escuchar solo se marcaba el broker. Los tópicos se activaban o desactivaban en la ficha de cada broker.

**Qué cambia:** Debajo de cada broker, Escuchar muestra sus tópicos con una casilla. La misma casilla sigue en Brokers. Un cambio en cualquiera de las dos pantallas queda guardado para la otra.

**Efecto para la operación:** Se puede armar qué se escucha sin abrir cada broker. Un tópico desmarcado no se suscribe. Si un broker marcado no tiene ningún tópico activo, no se conecta.

---

## Referencias

No hay pauta de instalación para este cambio.
