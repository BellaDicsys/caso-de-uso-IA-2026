# ADR-0004 — Superficie web propia: FastAPI, design system y tablero SVG

**Estado:** Aceptada — agosto 2026

## Contexto

La suite necesitaba superficies de uso más allá de la CLI: chat web, tablero de
control con alertas tempranas, y una versión móvil. Las alternativas incluían
usar un framework de frontend (React/Vue), una librería de gráficos (Chart.js,
Plotly) y/o una plataforma de dashboards (Grafana real).

## Decisión

- **Backend web con FastAPI + uvicorn** como fachada sobre `crear_orquestador()`
  y sobre `metrics.py`, en dependencias opcionales (`[api]`).
- **Design system propio** (`static/ds.css` + `static/ds.js`): tokens de color,
  tipografía, espaciado, elevación y movimiento estilo Material 3, con tema
  claro/oscuro y microinteracciones (ripple, snackbar, etiqueta flotante).
- **Frontend en HTML/JS vanilla** sin build step ni dependencias de terceros.
- **Gráficos en SVG generados a mano** (no una librería), con paleta validada
  para daltonismo mediante la herramienta de la skill de dataviz.

## Justificación

- **Cero build, cero dependencias de frontend**: el repositorio se evalúa con
  `pip install` y `serve`; no hace falta Node ni un bundler. Coherente con el
  principio de evaluabilidad (ADR-0003).
- **Autocontenido y offline**: sin CDNs ni servicios externos, el tablero y el
  chat funcionan en modo demo sin red, igual que el resto de la suite.
- **Control total del DS**: el pedido explícito era un design system propio con
  tema oscuro; una librería de terceros lo habría impuesto de afuera.
- **SVG a mano** para pocos gráficos evita ~200 KB de librería y da control
  fino sobre accesibilidad (separadores, extremos redondeados, etiquetas
  directas) siguiendo buenas prácticas de visualización.
- El tablero **replica el patrón de Grafana** (KPIs + alertas + series con
  refresco) sin el peso operativo de desplegar Grafana para una demo.

## Consecuencias

- Los gráficos SVG cubren los tipos que la demo necesita; un tablero con muchos
  paneles o interacciones complejas justificaría migrar a una librería.
- El DS propio hay que mantenerlo; a cambio, es liviano y a medida.
- En producción, la superficie web se serviría detrás de un reverse proxy con
  TLS y, para el tablero en tiempo real, se puede conectar Grafana real a la
  API de métricas.
