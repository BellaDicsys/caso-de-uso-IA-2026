# ADR-0005 — Autenticación por sesión y control de acceso por roles (RBAC)

**Estado:** Aceptada — agosto 2026

## Contexto

La superficie web expone datos de gestión (facturación, deuda, personal) que no
deberían ser públicos, y funciones sensibles (gestión de usuarios). Se necesitaba
autenticación y autorización, sin introducir una dependencia pesada ni un
proveedor de identidad externo en una demo sin deploy.

## Decisión

- **Autenticación por sesión** con cookie `HttpOnly` + `SameSite=Lax` y token
  aleatorio (`secrets.token_urlsafe`), con expiración.
- **Claves con hash PBKDF2-HMAC-SHA256** (200k iteraciones) y salt por usuario;
  nunca se almacenan en claro. Comparación en tiempo constante
  (`secrets.compare_digest`) y costo uniforme ante usuario inexistente para
  mitigar enumeración por *timing*.
- **RBAC de tres roles** verificado en el servidor:
  - `consulta`: chat.
  - `gestor`: chat + tablero.
  - `admin`: todo + gestión de usuarios.
- **Almacén de usuarios en JSON** (`data/usuarios.json`) con usuarios de
  demostración y claves documentadas en el README.
- La **CLI no pasa por esta capa**: es una herramienta de operación local.

## Justificación

- Cubre el pedido (gestión de usuarios y roles con autenticación) con la
  biblioteca estándar, sin dependencias nuevas de runtime.
- El control de acceso vive en el **servidor** (helpers `_requerir` / `_pagina`),
  no en el frontend: ocultar un botón no alcanza; los endpoints validan el rol.
- PBKDF2 es un estándar razonable y disponible en `hashlib`; el diseño permite
  subir el costo o cambiar de algoritmo en un solo lugar.

## Consecuencias

- Las sesiones viven **en memoria** del proceso: con varios workers de uvicorn
  habría que moverlas a un almacén compartido (Redis) — aceptable para la demo,
  documentado para producción.
- Las claves de demostración están en el repositorio a propósito, para que la
  web sea evaluable sin setup. En producción, este almacén se reemplaza por el
  **directorio corporativo (SSO/OIDC o passkeys)** y las cookies se sirven con
  el atributo `Secure` detrás de TLS.
- Para formularios que mutan estado con cookies de sesión, producción debería
  sumar protección **CSRF** (token por sesión o cabecera personalizada).
