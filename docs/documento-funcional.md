# Documento funcional — Enterprise Agent Suite

**Versión:** 1.1 — Agosto 2026
**Proyecto:** Caso de uso IA 2026 — Suite agéntica de gestión empresarial

---

## 1. Propósito

Permitir que cualquier persona de la organización consulte, **en lenguaje natural**,
información de gestión de cuatro dominios de negocio — ventas/proyectos, finanzas
(cobranzas), documentación interna y personal — y reciba una respuesta única, fundada en datos y con fuentes
citadas, producida por un sistema de agentes de IA.

## 2. Actores

| Actor | Descripción |
|---|---|
| Usuario de negocio | Dirección, líderes de proyecto, comercial, finanzas, RRHH: consulta por CLI o por el chat web |
| Evaluador técnico | Revisa el caso de uso; ejecuta la demo sin credenciales |
| Orquestador | Agente coordinador: interpreta, delega y sintetiza |
| Especialistas | Analista de Datos, Analista Financiero, Gestor Documental, Gestor de Personal |

## 3. Alcance funcional

### 3.1 Requerimientos funcionales

| ID | Requerimiento | Estado |
|---|---|---|
| RF-01 | Recibir consultas en lenguaje natural por CLI (`enterprise-agents ask "..."`) | ✅ |
| RF-02 | Clasificar la consulta y delegarla al/los especialistas correctos sin intervención del usuario | ✅ |
| RF-03 | **Analítica**: informar facturación total y desglosada por cliente, servicio y mes | ✅ |
| RF-04 | **Analítica**: informar estado de proyectos (horas presupuestadas vs consumidas) y **alertar** proyectos con consumo > 90% no finalizados | ✅ |
| RF-05 | **Documental**: encontrar el documento interno relevante para una consulta y responder citando el archivo fuente | ✅ |
| RF-06 | **Documental**: entregar el contenido completo de un documento a pedido | ✅ |
| RF-07 | **Personal**: listar perfiles por habilidad técnica, ordenados por disponibilidad | ✅ |
| RF-08 | **Personal**: listar personas con disponibilidad sobre un umbral configurable | ✅ |
| RF-09 | Resolver consultas **multi-dominio** en una sola interacción, delegando a varios especialistas | ✅ |
| RF-10 | Responder de forma controlada ante consultas fuera de dominio (sin inventar) | ✅ |
| RF-11 | Ejecutarse íntegramente **sin credenciales** en modo demo (mock) | ✅ |
| RF-12 | Ejecutarse contra el modelo real con `--live` y `ANTHROPIC_API_KEY` | ✅ |
| RF-13 | Mostrar la traza de delegaciones y herramientas con el flag `-v` | ✅ |
| RF-14 | **Finanzas**: informar estado de cobranzas, facturas vencidas (ordenadas por antigüedad) y deuda por cliente | ✅ |
| RF-15 | Exponer el orquestador como **API HTTP** (`POST /consultar`, `GET /salud`) | ✅ |
| RF-16 | Ofrecer una **interfaz de chat web** para demos (`enterprise-agents serve`) | ✅ |
| RF-17 | Correr un **set de evaluación** de 6 escenarios con criterios verificables, en mock o contra el modelo real (`enterprise-agents eval [--live]`) | ✅ |

### 3.2 Requerimientos no funcionales

| ID | Requerimiento | Implementación |
|---|---|---|
| RNF-01 | Trazabilidad: todo dato de una respuesta proviene de una herramienta identificable | Logging por llamada; el modelo no accede a datos directamente |
| RNF-02 | Seguridad: validación de argumentos generados por el modelo | Bloqueo de path traversal; errores encapsulados como `tool_result` |
| RNF-03 | Privacidad: minimización de datos de personas | Prompt del gestor de personal; datos sintéticos |
| RNF-04 | Control de costos: sin bucles infinitos | `max_iterations` en todo bucle; prompt caching en modo live |
| RNF-05 | Calidad verificable en CI | 94 tests + cobertura ≥ 85 % + lint + formato + smoke test en cada push |
| RNF-06 | Idioma: interacción y documentación en español | Prompts, CLI, docs |

### 3.3 Fuera de alcance (versión demo)

- Deploy productivo y autenticación de usuarios (el chat web es local, para demos).
- Conexión a sistemas reales (DWH, gestor documental, HRIS) — diseñada y documentada
  en `arquitectura.md` § Camino a producción, no implementada.
- Escritura de datos (la suite es de solo lectura sobre los datos de ejemplo).

## 4. Casos de uso

### CU-01 — Consulta de facturación

- **Actor:** usuario de negocio.
- **Disparador:** `enterprise-agents ask "¿Cuánto facturamos este año y quiénes son nuestros principales clientes?"`
- **Flujo principal:** orquestador → `delegar_analista_datos` → `resumen_ventas()` →
  síntesis.
- **Resultado esperado:** total facturado (471.100 USD en los datos de ejemplo),
  ranking de clientes encabezado por Banco Andino, desglose por servicio y por mes.

### CU-02 — Consulta de normativa interna

- **Disparador:** `enterprise-agents ask "¿Cuántos días de vacaciones le corresponden a alguien con 7 años de antigüedad?"`
- **Flujo principal:** orquestador → `delegar_gestor_documental` →
  `buscar_documentos()` → (live: `leer_documento()`) → respuesta citando
  `politica-vacaciones.md`.
- **Resultado esperado:** en modo live, la respuesta es "21 días hábiles" con cita
  del documento y versión; en modo mock, la identificación del documento correcto.

### CU-03 — Armado de equipo por habilidad

- **Disparador:** `enterprise-agents ask "Necesito armar un equipo con Python: ¿qué perfiles tienen disponibilidad?"`
- **Flujo principal:** orquestador → `delegar_gestor_personal` →
  `buscar_por_habilidad("python")` → síntesis.
- **Resultado esperado:** perfiles con Python ordenados por disponibilidad
  descendente (Martina López y Tomás Herrera al 100% encabezan la lista).

### CU-04 — Detección de proyectos en riesgo

- **Disparador:** `enterprise-agents ask "¿Qué proyectos están en riesgo por consumo de horas?"`
- **Flujo principal:** orquestador → `delegar_analista_datos` → `avance_proyectos()`.
- **Resultado esperado:** P-2026-05 (API Historia Clínica, 96% de horas consumidas)
  marcado con "⚠ consumo alto"; los proyectos finalizados no alertan.

### CU-07 — Consulta de cobranzas

- **Disparador:** `enterprise-agents ask "¿Qué facturas vencidas hay que reclamar?"`
- **Flujo principal:** orquestador → `delegar_analista_finanzas` → `facturas_vencidas()`.
- **Resultado esperado:** 3 facturas vencidas por 47.700 USD, con FC-2026-0115
  (la más antigua) primera en la lista de reclamo.

### CU-08 — Consulta por chat web

- **Disparador:** `enterprise-agents serve` y abrir `http://localhost:8000`.
- **Flujo principal:** el navegador envía `POST /consultar`; el backend ejecuta el
  mismo orquestador que la CLI y devuelve la respuesta al chat.

### CU-05 — Consulta multi-dominio (modo live)

- **Disparador:** `enterprise-agents ask --live "¿Cuánto facturamos a Banco Andino y quién puede tomar su próximo proyecto?"`
- **Flujo principal:** el orquestador delega en **dos** especialistas (analista +
  personal) y sintetiza una única respuesta con ambas fuentes.

### CU-06 — Consulta fuera de dominio

- **Disparador:** `enterprise-agents ask "¿Va a llover mañana?"`
- **Resultado esperado:** el sistema informa que no corresponde a sus dominios y
  orienta al usuario; **no inventa** una respuesta.

## 5. Guía de prueba (aceptación)

### 5.1 Preparación (una sola vez)

```bash
git clone <repo> && cd caso-de-uso-IA-2026
pip install -e ".[dev]"
```

### 5.2 Pruebas automáticas

| Paso | Comando | Criterio de aceptación |
|---|---|---|
| 1 | `python -m pytest --cov` | 94 tests OK y cobertura ≥ 85 %, sin red |
| 2 | `ruff check . && ruff format --check .` | Sin errores |

### 5.3 Pruebas funcionales en modo demo (sin API key)

| Paso | Comando | Verificar |
|---|---|---|
| 3 | `enterprise-agents demo` | Corre los 5 escenarios (CU-01 a CU-04 y CU-07) con los resultados esperados de cada uno |
| 4 | `enterprise-agents -v ask "¿Qué proyectos están en riesgo?"` | La traza muestra `[orquestador] herramienta delegar_analista_datos` y `[analista_datos] herramienta avance_proyectos`; la respuesta marca P-2026-05 |
| 5 | `enterprise-agents ask "¿Va a llover mañana?"` | Respuesta controlada de fuera de dominio (CU-06) |
| 6 | `enterprise-agents eval` | Reporte "6/6 escenarios OK" y exit code 0 (RF-17) |
| 7 | `enterprise-agents serve` + abrir http://localhost:8000 | El chat responde las sugerencias precargadas (CU-08); `GET /salud` devuelve `{"estado": "ok", "modo": "demo"}` |

### 5.4 Pruebas con el modelo real (opcional, requiere API key)

| Paso | Comando | Verificar |
|---|---|---|
| 8 | `export ANTHROPIC_API_KEY=sk-ant-...` | — |
| 9 | `enterprise-agents ask --live "¿Cuántos días de vacaciones me corresponden con 7 años de antigüedad?"` | Respuesta "21 días hábiles" citando `politica-vacaciones.md` (CU-02 completo) |
| 10 | `enterprise-agents -v ask --live "¿Cuánto facturamos a Banco Andino y quién puede tomar su próximo proyecto?"` | La traza muestra delegación a **dos** especialistas; la síntesis integra facturación (150.700 USD) y perfiles disponibles (CU-05) |

### 5.5 Matriz de trazabilidad

| Requerimiento | Caso de uso | Test automatizado |
|---|---|---|
| RF-03 | CU-01 | `test_resumen_ventas_incluye_total_y_clientes`, `test_consulta_de_ventas_llega_al_analista` |
| RF-04 | CU-04 | `test_avance_proyectos_marca_riesgo_de_consumo` |
| RF-05 | CU-02 | `test_buscar_documentos_encuentra_politica_de_vacaciones`, `test_consulta_documental_cita_el_documento` |
| RF-07 | CU-03 | `test_buscar_por_habilidad_ordena_por_disponibilidad`, `test_consulta_de_personal_devuelve_perfiles` |
| RF-08 | CU-03 | `test_disponibilidad_equipo_respeta_umbral` |
| RF-10 | CU-06 | `test_consulta_fuera_de_dominio_no_inventa` |
| RF-14 | CU-07 | `test_estado_cobranzas_totaliza_por_estado`, `test_facturas_vencidas_ordena_por_antiguedad`, `test_deuda_por_cliente_filtra_y_agrupa`, `test_consulta_de_cobranzas_llega_al_analista_financiero` |
| RF-15/16 | CU-08 | `test_salud_reporta_modo_demo`, `test_chat_web_se_sirve_en_raiz`, `test_consultar_devuelve_respuesta_del_orquestador`, `test_consultar_valida_entrada` |
| RF-17 | — | `test_evaluacion_completa_en_mock` |
| RNF-02 | — | `test_leer_documento_bloquea_path_traversal`, `test_error_de_herramienta_vuelve_al_modelo_como_tool_result` |
| RNF-04 | — | `test_limite_de_iteraciones_corta_el_bucle` |
