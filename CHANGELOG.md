# Changelog

Todas las versiones publicadas de la Enterprise Agent Suite. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el versionado es
[semántico](https://semver.org/lang/es/); las entradas se generan
automáticamente desde los *Conventional Commits* (ver
[docs/adr/0006-versionado-automatico.md](docs/adr/0006-versionado-automatico.md)).
Las versiones anteriores a la puesta en marcha del versionado automático se
reconstruyeron a partir del historial.

## 0.6.0 — 2026-08-06

### Nuevas funcionalidades

- **recuperacion**: motor híbrido BM25 + espacio latente derivado del corpus
- **datos**: amplía el corpus documental de 3 a 30 documentos

## 0.5.1 — 2026-08-06

### Correcciones

- **ayuda**: corrige la afirmación de que el asistente mantiene el hilo

## 0.5.0 — 2026-08-06

### Nuevas funcionalidades

- **ayuda**: sección de ayuda e inducción al usuario

### Documentación

- sincroniza las métricas del proyecto con el estado actual

## 0.4.0 — 2026-08-05

### Nuevas funcionalidades

- **versionado**: versionado automático desde Conventional Commits

### Documentación

- **changelog**: reconstruye el historial previo al versionado automático

## 0.3.0 — 2026-08-05

### Nuevas funcionalidades

- **tablero**: tablero de control con KPIs, alertas tempranas por severidad y
  gráficos SVG con paleta validada para daltonismo
- **auth**: autenticación por sesión y RBAC de tres roles (consulta, gestor, admin)
- **ds**: design system propio (`ds.css` / `ds.js`) estilo Material 3, con tema
  claro/oscuro y microinteracciones
- **movil**: versión móvil de alcance reducido con chat de voz (Web Speech API)
- **usuarios**: alta, baja y asignación de roles desde la web (rol admin)

### Correcciones

- **seguridad**: correcciones de la auditoría adversarial — open redirect en el
  login, revocación de sesiones al eliminar un usuario, límite de intentos de
  autenticación, cookie `Secure` y RBAC a nivel de herramienta
- **ruteo**: coincidencia por prefijo de palabra en el cliente mock, para evitar
  falsos positivos por subcadena

### Rendimiento

- **api**: orquestadores por rol construidos una sola vez y páginas HTML cacheadas
- **datos**: lectura de CSV con caché invalidada por fecha de modificación

## 0.2.0 — 2026-08-04

### Nuevas funcionalidades

- **finanzas**: cuarto dominio (cobranzas, facturas vencidas y deuda por cliente)
- **api**: API HTTP con FastAPI y chat web sobre el orquestador
- **evals**: set de evaluación de seis escenarios con criterios verificables

### Refactors

- **paquete**: rename del proyecto a Enterprise Agent Suite

## 0.1.0 — 2026-08-03

### Nuevas funcionalidades

- **agentes**: orquestador y especialistas de analítica, gestión documental y
  personal, con herramientas de dominio sobre datos sintéticos
- **llm**: capa `LLMClient` con cliente Anthropic y cliente mock determinístico
- **cli**: comandos `demo` y `ask`

### Documentación

- memoria descriptiva, documento funcional, especificaciones técnicas,
  arquitectura, casos de innovación, guía de vibecoding y ADRs
