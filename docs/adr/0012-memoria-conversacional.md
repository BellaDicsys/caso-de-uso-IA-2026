# ADR-0012 — Memoria conversacional con compactación y contextualización

**Estado:** Aceptada — agosto 2026

## Contexto

Hasta acá cada consulta se resolvía de cero: el historial que se veía en pantalla
era del navegador, no del asistente. Repreguntar *"¿y la más antigua?"* no
funcionaba, y estaba declarado como límite conocido en la ayuda, la guía de uso y
la memoria descriptiva. Es la primera cosa que prueba cualquiera que use el chat
treinta segundos.

## Decisión

Dos piezas que resuelven problemas distintos.

### 1. Historial con presupuesto y compactación extractiva

Una conversación por sesión, con presupuesto de contexto. Cuando la estimación de
tokens lo supera, los turnos más antiguos se compactan en un resumen y los
**recientes quedan intactos**: la referencia de una repregunta apunta casi
siempre al turno inmediato anterior, así que perder ese detalle rompería justo el
caso de uso que la memoria viene a habilitar.

El resumen es **extractivo**: selecciona oraciones que ya existen, no redacta
nuevas. Es una decisión de seguridad, no de simplicidad. Un resumen generativo
necesitaría el modelo, costaría una llamada por compactación y —lo importante—
podría introducir afirmaciones que ninguna herramienta produjo, que es
exactamente lo que el verificador de fundamentación del ADR-0009 existe para
impedir. Un extractivo no puede inventar: en el peor caso elige mal qué
conservar.

La compactación es acumulativa: el resumen previo entra al siguiente, así que no
se descarta lo ya condensado.

### 2. Contextualización de la consulta

Una repregunta no dice de qué habla. Antes de rutearla o recuperar con ella se la
completa con los términos informativos del turno anterior. Es la técnica estándar
de búsqueda conversacional y tiene la ventaja decisiva de **funcionar sin
modelo**: se apoya en el mismo preprocesamiento léxico del motor de recuperación.

Sin esto, la memoria habría sido plomería para `--live` y nada más: el cliente
simulado no razona, así que arrastrar el historial no le habría servido para
resolver la referencia.

## Justificación

- **Solo el orquestador recibe historial.** Los especialistas siguen recibiendo
  tareas autocontenidas y por lo tanto siguen siendo *stateless*, que es lo que
  permite construirlos una vez y reusarlos entre requests.
- **La tarea que se delega va contextualizada, no cruda.** El esquema de la
  herramienta de delegación ya pedía una tarea "autocontenida con todo el
  contexto necesario"; hacerlo es lo que un modelo real redactaría. Sin esto el
  orquestador rutea bien y el especialista recibe *"¿y la más antigua?"* sin
  referente, así que falla un nivel más abajo.
- **El estado de la memoria es visible.** El chat muestra cuántos turnos recuerda
  y cuánto contexto arrastra, y hay un botón para empezar de nuevo. Una memoria
  invisible es una fuente de sorpresas: el usuario no entiende por qué el
  asistente responde algo que no le preguntó.

## Consecuencias

- La memoria vive en memoria del proceso, por sesión, y se descarta al salir.
  Mismo riesgo aceptado que las sesiones y las trazas.
- Los tres documentos que declaraban la falta de memoria como límite conocido se
  actualizan.
- **El umbral de autosuficiencia se calibró contra un fallo real.** Estaba en
  tres términos informativos, y con ese valor *"¿qué dice la política de
  vacaciones?"* —que aporta exactamente dos, *política* y *vacación*— quedaba
  clasificada como repregunta: se le anexaba el tema anterior y un cambio de tema
  volvía al tema viejo. Lo detectó un test escrito para eso. Quedó en dos: errar
  hacia abajo cuesta no contextualizar una repregunta rara; errar hacia arriba
  desvía consultas legítimas, que es mucho peor.
- La contextualización es una heurística de superficie. Una referencia a dos
  turnos atrás, o una que dependa de la *respuesta* y no de la pregunta anterior,
  no la resuelve. El modelo real sí, porque recibe el historial completo.
