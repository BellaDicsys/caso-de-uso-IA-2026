# Memoria descriptiva del proyecto — Enterprise Agent Suite

**Versión:** 1.1 — Agosto 2026
**Proyecto:** Caso de uso IA 2026
**Organización:** Dicsys — consultora de servicios tecnológicos (analítica de datos,
BI, ERP, gestión documental)
**Modalidad de entrega:** repositorio Git, sin deploy, con documentación descriptiva

---

## 1. Antecedentes y motivación

Dicsys trabaja con diversos clientes y gestiona recursos empresariales en frentes
permanentes: **analítica de datos** (ventas, proyectos, horas), **finanzas**
(cobranzas, facturación), **gestión documental** (políticas, manuales, contratos)
y **gestión de personal** (perfiles, habilidades, asignaciones). Estas consultas hoy dependen de personas que conocen
dónde está cada dato y cada documento.

En paralelo, el mercado de gestión empresarial atraviesa el pasaje de la IA
"asistente de texto" a la **IA agéntica**: sistemas que interpretan un pedido,
deciden qué acciones ejecutar sobre los sistemas de la organización y devuelven un
resultado accionable. La investigación de mercado realizada para este proyecto
(ver [casos-innovacion.md](casos-innovacion.md)) muestra adopción masiva, retornos
medibles y, en particular, que los proveedores de modelos canalizan la demanda
empresarial a través de consultoras: **demostrar capacidad propia de construcción
de agentes es hoy un diferencial comercial directo para Dicsys**.

## 2. Objetivos

**Objetivo general:** demostrar, con un producto ejecutable y documentado, la
capacidad de Dicsys para diseñar y construir soluciones agénticas de gestión
empresarial con mejores prácticas de ingeniería y de desarrollo asistido por IA.

**Objetivos específicos:**

1. Implementar un sistema multi-agente (orquestador + especialistas) sobre los
   dominios de negocio de la empresa, demostrando además la extensibilidad del
   patrón (el cuarto dominio, finanzas, se agregó sin tocar el resto del sistema).
2. Aplicar el principio "el modelo decide, el código ejecuta" con validación,
   trazabilidad y manejo de errores de nivel productivo.
3. Hacer el resultado **evaluable por cualquiera**: instalación en un comando y
   demo completa sin credenciales.
4. Documentar el fundamento (investigación de mercado), el diseño (arquitectura y
   ADRs), el uso (documento funcional) y el proceso (guía de vibecoding).
5. Dejar trazado el camino de evolución a producción sin cambios de arquitectura.

## 3. Descripción de la solución

La **Enterprise Agent Suite** es una aplicación Python que expone un asistente de
gestión empresarial por línea de comandos, por API HTTP y por chat web:

- El usuario formula una consulta en lenguaje natural.
- Un **agente orquestador** (impulsado por Claude) interpreta la consulta y la
  delega en uno o más **agentes especialistas** — Analista de Datos, Analista
  Financiero, Gestor Documental, Gestor de Personal — mediante herramientas de
  delegación.
- Cada especialista resuelve su parte ejecutando **herramientas de dominio**
  (funciones Python determinísticas sobre los datos de la organización) y responde
  fundado en esos datos.
- El orquestador sintetiza una única respuesta, empezando por la conclusión y
  citando las fuentes.

La demo opera sobre **datos sintéticos** representativos del negocio (20
operaciones de venta, 7 proyectos, 15 facturas, 12 empleados, 3 documentos
corporativos) y
funciona en dos modos con el mismo código: **demo offline** (sin API key, cliente
simulado determinístico) y **live** (API de Claude, modelo `claude-opus-5`).

Detalle completo en: [arquitectura.md](arquitectura.md) (diseño),
[especificaciones-tecnicas.md](especificaciones-tecnicas.md) (implementación) y
[documento-funcional.md](documento-funcional.md) (requerimientos, casos de uso y
guía de prueba).

## 4. Metodología de desarrollo

El proyecto se construyó con **desarrollo asistido por IA** bajo la disciplina
documentada en [guia-vibecoding.md](guia-vibecoding.md):

- iteraciones chicas con criterio de aceptación verificable;
- verificación automática en cada paso (tests, lint, formato, smoke test);
- decisiones estructurales registradas como ADRs en el momento de tomarlas;
- historial legible por máquina: *Conventional Commits* de los que se derivan la
  versión, el changelog y las releases, sin intervención manual;
- contexto operativo del repositorio para agentes de código (`CLAUDE.md`);
- secretos y datos reales fuera del repositorio por diseño.

## 5. Resultados alcanzados

| Dimensión | Resultado |
|---|---|
| Producto | Suite con 4 dominios de negocio, 5 escenarios de demo, consultas libres, API HTTP y chat web |
| Código | ~2.700 líneas (código, tests, datos y docs); núcleo con 1 sola dependencia de runtime |
| Calidad | 94 tests automatizados (cobertura 94 %) + set de evaluación de 6 escenarios; lint y formato limpios; CI en GitHub Actions; auditoría adversarial documentada |
| Evaluabilidad | Demo completa sin credenciales en 2 comandos |
| Documentación | 8 documentos: arquitectura, especificaciones técnicas, funcional, memoria, investigación de mercado, guía de vibecoding, auditoría adversarial y 6 ADRs, más el changelog generado |
| Seguridad | Validación de argumentos del modelo, bloqueo de path traversal, límites de iteración, manejo de rechazos del modelo |

## 6. Líneas de evolución

1. **Conexión a sistemas reales** — DWH para analítica, búsqueda semántica para
   documental, HRIS para personal (las herramientas son el único punto de cambio).
2. **Nuevos canales** — el chat web y la API HTTP ya existen como base; siguen
   bot de Slack/Teams e integración en el portal interno.
3. **Nuevos dominios** — compras, soporte, legales: el patrón quedó demostrado
   con el alta de finanzas sin tocar el resto del sistema.
4. **Evaluación continua** — el set de evaluación ya corre en CI en modo mock;
   siguiente paso: ejecutarlo periódicamente contra el modelo real (`eval --live`).
5. **Gobernanza productiva** — permisos por herramienta y usuario, auditoría
   centralizada, políticas de datos sensibles.

## 7. Conclusión

El proyecto cumple el objetivo de demostración: un sistema agéntico real —no un
prototipo de prompt— con arquitectura escalable, prácticas de ingeniería
verificables y documentación completa, alineado con los casos de innovación que
están definiendo la gestión empresarial en 2026. Constituye una base concreta
sobre la cual Dicsys puede construir propuestas comerciales de soluciones
agénticas para sus clientes.
