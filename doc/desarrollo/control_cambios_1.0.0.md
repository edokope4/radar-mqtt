# Control de Cambios — v1.0.0

**Versión:** 1.0.0
**Estado:** en curso
**Versión anterior liberada:** ninguna

---

## Resumen

| # | Cambio | Tipo | Requiere acción al instalar |
|---|--------|------|-----------------------------|
| 1 | En Archivo se ve el MD5 del mensaje para comprobar si dos payloads son iguales | Mejora | No |

---

## 1. Comparar mensajes por su MD5

**Tipo:** Mejora · **Fecha:** 16/10/2026

**Situación anterior:** Para saber si dos mensajes guardados eran iguales había que revisar el contenido completo.

**Qué cambia:** Al elegir un mensaje en Archivo, junto al visor aparece el MD5 de ese payload. El mismo código indica el mismo contenido.

**Efecto para la operación:** Se puede comparar mensajes sin leer el texto entero. El código corresponde al payload tal como se recibió. El JSON indentado de la pantalla no cambia el MD5. Si no hay un mensaje elegido, el espacio queda vacío.

---

## Referencias

No hay pauta de instalación para este cambio.
