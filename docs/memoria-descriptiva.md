# Memoria descriptiva del proyecto — Enterprise Agent Suite

**Versión:** 2.0 — Agosto 2026
**Proyecto:** Caso de uso IA 2026
**Organización:** Dicsys — consultora de servicios tecnológicos (analítica de datos,
BI, ERP, gestión documental)
**Modalidad de entrega:** repositorio Git, sin deploy, con documentación descriptiva

---

## 1. Antecedentes y motivación

Dicsys trabaja con diversos clientes y gestiona recursos empresariales en frentes
permanentes: **analítica de datos** (ventas, proyectos, horas), **finanzas**
(cobranzas, facturación), **gestión documental** (políticas, manuales, contratos)
y **gestión de personal** (perfiles, habilidades, asignaciones). Esas consultas
hoy dependen de personas que conocen dónde está cada dato y cada documento.

En paralelo, el mercado de gestión empresarial atraviesa el pasaje de la IA
"asistente de texto" a la **IA agéntica**: sistemas que interpretan un pedido,
deciden qué acciones ejecutar sobre los sistemas de la organización y devuelven un
resultado accionable. La investigación de mercado realizada para este proyecto
(ver [casos-innovacion.md](casos-innovacion.md)) muestra adopción masiva, retornos
medibles y, en particular, que los proveedores de modelos canalizan la demanda
empresarial a través de consultoras: **demostrar capacidad propia de construcción
de agentes es hoy un diferencial comercial directo para Dicsys**.

El proyecto se desarrolló en **dos etapas** con propósitos distintos, y la
distinción importa para leer el resto de este documento:

| Etapa | Pregunta que responde | Resultado |
|---|---|---|
| **Caso de uso** | ¿Sabemos *construir* un sistema agéntico sobre los dominios de negocio? | Suite multi-agente con CLI, API, chat web, tablero, roles y versión móvil |
| **Núcleo verificable** | ¿Sabemos *ingenierizarlo*: medirlo, protegerlo y auditarlo? | Recuperación propia, evaluación con umbrales, seguridad de agentes, observabilidad y memoria |

La segunda etapa es la que separa una demostración de una capacidad. Construir un
agente que funciona en cinco ejemplos elegidos es accesible; poder afirmar con
números qué tan bien recupera, demostrar que no inventa cifras y declarar
exactamente qué se probó y qué no, es otra cosa.

## 2. Objetivos

**Objetivo general:** demostrar, con un producto ejecutable y documentado, la
capacidad de Dicsys para diseñar, construir **y verificar** soluciones agénticas
de gestión empresarial con mejores prácticas de ingeniería y de desarrollo
asistido por IA.

**Objetivos específicos:**

1. Implementar un sistema multi-agente (orquestador + especialistas) sobre los
   dominios de negocio de la empresa, demostrando la extensibilidad del patrón —el
   cuarto dominio, finanzas, se agregó sin tocar el resto del sistema.
2. Aplicar el principio "el modelo decide, el código ejecuta" con validación,
   trazabilidad y manejo de errores de nivel productivo.
3. **Medir lo que se afirma.** Que la calidad de la recuperación, la ausencia de
   cifras inventadas y la resistencia a inyecciones sean números con umbral en CI
   y no aseveraciones de un README.
4. **Correr por completo sin servicios externos**, incluida toda la maquinaria de
   recuperación semántica: sin pesos preentrenados, sin red y sin credenciales.
5. Hacer el resultado **evaluable por cualquiera**: instalación en un comando y
   demostración completa sin credenciales.
6. Documentar el fundamento (investigación de mercado), el diseño (arquitectura y
   ADRs), el uso (funcional y guía de uso) y el proceso (guía de vibecoding).
7. **Declarar los límites con la misma claridad que los logros**, incluido lo que
   quedó sin verificar.

## 3. Descripción de la solución

### 3.1 La suite agéntica

Aplicación Python que expone un asistente de gestión empresarial por línea de
comandos, API HTTP y chat web:

- El usuario formula una consulta en lenguaje natural.
- Un **agente orquestador** (impulsado por Claude) interpreta la consulta y la
  delega en uno o más **agentes especialistas** — Analista de Datos, Analista
  Financiero, Gestor Documental, Gestor de Personal.
- Cada especialista resuelve su parte ejecutando **herramientas de dominio**
  (funciones Python determinísticas) y responde fundado en esos datos.
- El orquestador sintetiza una única respuesta, empezando por la conclusión y
  citando las fuentes.

Superficies: CLI, chat web con memoria conversacional, versión móvil con voz,
tablero de alertas tempranas, visor de trazas, administración de usuarios y ayuda
sensible al rol. Autenticación por sesión con **RBAC a nivel de herramienta**: el
rol no solo define qué páginas se ven, sino qué dominios puede consultar el agente
en nombre de esa persona.

### 3.2 El núcleo verificable

Seis módulos construidos sobre la suite, todos **sin dependencias nuevas**:

| Módulo | Qué resuelve |
|---|---|
| **Recuperación híbrida** | BM25 más un espacio latente construido desde el propio corpus por SVD aleatorizada implementada sobre listas de Python, fusionados por *Reciprocal Rank Fusion*. Sin pesos preentrenados. |
| **Ruteo semántico** | El cliente simulado elige herramienta por similitud contra su descripción, no por palabras clave: rutear es recuperar, con las herramientas como corpus. |
| **Evaluación** | 55 consultas etiquetadas con recall@5, MRR y nDCG@5, más un **verificador de fundamentación** que detecta cifras que ninguna herramienta informó. Con umbrales en CI. |
| **Seguridad de agentes** | Saneamiento del contenido recuperado y suite de siete documentos con inyecciones de prompt, con el alcance de lo verificado declarado explícitamente. |
| **Observabilidad** | Árbol de spans por consulta con tiempos y tokens estimados, visible en la web. |
| **Memoria conversacional** | Historial por sesión con presupuesto de contexto, compactación extractiva y contextualización de repreguntas. |

La decisión transversal fue **no incorporar un modelo de embeddings
preentrenado**. Habría sido el camino corto y habría roto la propiedad más valiosa
del repositorio —clonar y correr, sin red—, además de volver no determinístico lo
que hoy se testea en milisegundos. La alternativa —construir los vectores desde el
corpus— resultó más trabajo y mejor demostración. Fundamento en
[ADR-0007](adr/0007-recuperacion-hibrida-sin-modelo-externo.md).

### 3.3 Datos

La demostración opera sobre **datos sintéticos** representativos del negocio: 20
operaciones de venta, 7 proyectos, 15 facturas, 12 empleados y **30 documentos
corporativos** (políticas, procedimientos, contratos, manuales técnicos). El
corpus documental se amplió deliberadamente de 3 a 30: con tres documentos
cualquier método de búsqueda parece funcionar, y el objetivo era tener un banco de
pruebas donde la calidad de la recuperación fuera **medible y falsable**.

Existe además un corpus separado de siete documentos con inyecciones de prompt,
usado solo por la suite de seguridad.

Todo funciona en dos modos con el mismo código: **demo offline** (sin API key,
cliente simulado determinístico) y **live** (API de Claude, modelo `claude-opus-5`).

Detalle completo en [arquitectura.md](arquitectura.md) (diseño),
[especificaciones-tecnicas.md](especificaciones-tecnicas.md) (implementación),
[documento-funcional.md](documento-funcional.md) (requerimientos y guía de prueba)
y [guia-de-uso.md](guia-de-uso.md) (manual del usuario final).

## 4. Metodología de desarrollo

El proyecto se construyó con **desarrollo asistido por IA** bajo la disciplina
documentada en [guia-vibecoding.md](guia-vibecoding.md):

- iteraciones chicas con criterio de aceptación verificable;
- verificación automática en cada paso: tests, lint, formato, smoke test,
  evaluación y suite de seguridad;
- **medir antes de afirmar**: toda mejora del motor de recuperación se contrastó
  contra el conjunto etiquetado, no contra la intuición;
- decisiones estructurales registradas como ADRs en el momento de tomarlas, con
  las alternativas descartadas y su motivo;
- historial legible por máquina: *Conventional Commits* de los que se derivan la
  versión, el changelog y las releases, sin intervención manual;
- contexto operativo del repositorio para agentes de código (`CLAUDE.md`);
- secretos y datos reales fuera del repositorio por diseño.

## 5. Resultados alcanzados

| Dimensión | Resultado |
|---|---|
| Producto | Suite con 4 dominios, 8 superficies de uso y 6 módulos de ingeniería de IA |
| Código | ~13.100 líneas (código, frontend, tests, datos y documentación); núcleo con **1 sola dependencia de runtime** |
| Calidad | **305 tests** automatizados, cobertura **95 %** (umbral 85 % en CI), lint y formato limpios, CI en Python 3.10 y 3.12 |
| Calidad de recuperación | acierto@5 **0,902** · recall@5 **0,895** · MRR **0,776** · nDCG@5 **0,804** · abstención **1,000**, con umbrales que hacen fallar el pipeline |
| Fundamentación | Toda cifra de una respuesta debe provenir de una herramienta de esa misma ejecución; verificado en cada escenario, sin modelo juez |
| Seguridad | 7 categorías de inyección de prompt contenidas, más dos defensas estructurales (RBAC por herramienta y solo lectura) |
| Evaluabilidad | Demostración completa **sin credenciales ni red** en dos comandos |
| Documentación | 8 documentos y **12 ADRs**, más el changelog generado automáticamente y el contexto para agentes de código |
| Auditoría | **Dos rondas** adversariales documentadas, con sus hallazgos corregidos y sus límites declarados |

## 6. Evidencia de criterio de ingeniería

Esta sección existe porque es lo que distingue el proyecto de una demostración
funcional, y porque el repositorio la sostiene con evidencia verificable.

### 6.1 La medición contradijo la intuición, y se siguió a la medición

Apenas existió el conjunto etiquetado se probó la mejora que parecía más obvia
—extender el recortador de sufijos a las terminaciones de infinitivo, para
conectar *subcontratar* con *subcontratación*—. **Resultó neta negativa**: el
acierto quedó igual y MRR y nDCG empeoraron (0,776 → 0,760 y 0,804 → 0,788). Se
revirtió. Sin medición se habría incorporado por sensata, y el sistema habría
quedado peor con la convicción de haber mejorado.

De la misma forma se verificó empíricamente una afirmación propia: entre K=10 y
K=100 en la constante de fusión, las cuatro métricas no se mueven.

### 6.2 Se decidió no construir dos veces

- **No hay índice aproximado (ANN).** Con 190 fragmentos sería más código, más
  superficie de error y **peor latencia** por el sobrecosto de la estructura. Se
  dejó anotado el umbral a partir del cual valdría la pena.
- **Las trazas no persisten en base de datos.** Agregaría un archivo que
  administrar, un esquema que migrar y una retención que implementar, para una
  demostración de un solo proceso. En producción esto se reemplaza por el sistema
  de trazas de la organización, no por una base local.

En ambos casos la decisión —y su motivo— quedó escrita en el ADR correspondiente.
Saber qué **no** construir es tan demostrable como saber construir.

### 6.3 Los instrumentos encontraron defectos reales

| Qué lo encontró | Defecto |
|---|---|
| El conjunto etiquetado | El recuperador **siempre devolvía su top-k**: una consulta ajena recibía cuatro pasajes con total confianza |
| Los tests de ruteo | El cliente simulado devolvía un **nombre de archivo fijo**, y parecía acertar por casualidad |
| Los tests de trazas | Los errores de herramienta **no quedaban marcados** |
| Los tests de memoria | Un umbral mal calibrado hacía que **un cambio de tema volviera al tema anterior** |

### 6.4 La segunda auditoría halló un defecto introducido por una mejora

El visor de observabilidad —una funcionalidad nueva— dejaba que cualquier usuario
con rol de gestión leyera las consultas de los demás, con la salida completa de
las herramientas. Se verificó con dos sesiones simultáneas antes de darlo por
cierto, se corrigió con aislamiento por usuario y quedó con test de regresión.

Se registra en la [auditoría](auditoria-adversarial.md) sin suavizarlo: una mejora
puede abrir un agujero, y el valor de auditar dos veces es exactamente ese.

## 7. Líneas de evolución

1. **Conexión a sistemas reales** — DWH para analítica, repositorio documental del
   cliente, HRIS para personal. Las herramientas son el único punto de cambio, y
   el motor de recuperación ya define el contrato (`Embedder`) para enchufar un
   modelo local o remoto sin tocar el resto.
2. **Nuevos canales** — el chat web y la API HTTP ya existen; siguen bot de
   Slack/Teams e integración en el portal interno.
3. **Nuevos dominios** — compras, soporte, legales: el patrón quedó demostrado con
   el alta de finanzas sin tocar el resto del sistema.
4. **Evaluación contra el modelo real** — el arnés ya corre en CI en modo
   simulado; el paso siguiente es ejecutarlo periódicamente con `--live` y
   versionar los resultados.
5. **Memoria entre sesiones** — la conversación ya persiste dentro de la sesión
   con presupuesto y compactación; sigue conservarla entre sesiones y por usuario,
   con una política de retención acordada.
6. **Observabilidad productiva** — exportar las trazas al sistema de la
   organización (OpenTelemetry hacia un colector) en lugar del registro en memoria.
7. **Gobernanza** — permisos por herramienta y usuario, auditoría centralizada,
   políticas de datos sensibles.

## 8. Alcance y límites declarados

Se enuncian con el mismo énfasis que los resultados, porque un informe que afirma
más de lo que probó vale menos que uno que declara su alcance:

- **Los datos son sintéticos.** El proyecto demuestra el patrón y su
  extensibilidad, no el manejo de datos productivos sucios.
- **Las credenciales de demostración están en el repositorio** a propósito, para
  que el proyecto sea evaluable sin configuración. El servidor lo advierte al
  arrancar.
- **La suite de seguridad no prueba que el modelo obedezca la delimitación.**
  Verifica las tres capas que son código y declara que la cuarta requiere el
  modelo real.
- **El conteo de tokens es una estimación** calculada localmente, útil para
  comparar consultas entre sí y no como medida de facturación.
- **El estado vive en memoria** (sesiones, trazas, conversaciones): se pierde al
  reiniciar y no funcionaría con varios workers.
- **Todo lo que depende del modelo real quedó sin verificar** en este repositorio,
  por no disponer de clave de API en el entorno de construcción. Se cierra
  corriendo `eval --live` y `seguridad --live` y versionando el resultado.

## 9. Conclusión

El proyecto cumple el objetivo de demostración en sus dos niveles. Como caso de
uso, es un sistema agéntico real —no un prototipo de prompt— sobre los dominios de
negocio de la empresa, con arquitectura extensible y superficie de producto
completa. Como demostración de capacidad de ingeniería, aporta lo que rara vez se
muestra: **métricas de calidad con umbrales que hacen fallar el pipeline, un
verificador que detecta cifras inventadas, una suite de seguridad que declara su
alcance, y un registro honesto de las decisiones que la medición obligó a
revertir**.

Constituye una base concreta sobre la cual Dicsys puede construir propuestas
comerciales de soluciones agénticas, y —más importante— un argumento verificable
de que esas propuestas se pueden sostener con números.
