"""Conjunto etiquetado de consultas de recuperación.

Cada entrada es una consulta como la escribiría una persona y el conjunto de
documentos que la responden. Es el instrumento de medición del motor: sin esto,
"mejoré la búsqueda" es una opinión.

Criterios al etiquetar:

- **Consultas en lenguaje natural, no en jerga del índice.** "¿Puedo trabajar
  desde casa?" y no "teletrabajo modalidad".
- **Paráfrasis deliberadas.** Varias consultas evitan a propósito el término que
  usa el documento, para que la rama semántica tenga que trabajar.
- **Relevancia por respuesta, no por tema.** Un documento es relevante si
  *contesta* la pregunta. Varios documentos hablan de datos personales; solo uno
  dice cuánto tiempo se conservan.
- **Casos ambiguos incluidos** con más de un documento aceptable, en vez de
  forzar una única respuesta correcta que el corpus no tiene.
- **Consultas fuera de dominio** con conjunto relevante vacío: saber abstenerse
  es parte de la calidad, y sin estos casos la métrica premia al recuperador que
  siempre devuelve algo.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConsultaEtiquetada:
    consulta: str
    relevantes: frozenset[str]

    @property
    def fuera_de_dominio(self) -> bool:
        return not self.relevantes


def _c(consulta: str, *documentos: str) -> ConsultaEtiquetada:
    return ConsultaEtiquetada(consulta=consulta, relevantes=frozenset(documentos))


CONSULTAS: tuple[ConsultaEtiquetada, ...] = (
    # --- Personas -----------------------------------------------------------
    _c("¿cuántos días de vacaciones me corresponden?", "politica-vacaciones.md"),
    _c("¿con cuánta anticipación tengo que pedir las vacaciones?", "politica-vacaciones.md"),
    _c("¿qué pasa si me mudo, tengo algún permiso?", "politica-vacaciones.md"),
    _c("¿puedo trabajar desde casa?", "politica-teletrabajo.md"),
    _c("¿cuántos días por semana hay que ir a la oficina?", "politica-teletrabajo.md"),
    _c("¿me reintegran el internet?", "politica-teletrabajo.md"),
    _c("¿la empresa paga cursos o certificaciones?", "politica-capacitacion.md"),
    _c("¿me cubren un posgrado?", "politica-capacitacion.md"),
    _c("¿puedo aceptar un regalo de un proveedor?", "codigo-de-conducta.md"),
    _c("¿dónde denuncio una situación de acoso?", "codigo-de-conducta.md"),
    _c("¿cuánto me reconocen por día de viaje?", "politica-viaticos.md"),
    _c("¿hasta cuándo tengo para rendir los gastos?", "politica-viaticos.md"),
    _c("¿cada cuánto me evalúan?", "evaluacion-de-desempeno.md"),
    _c("¿qué pasa si no alcanzo los objetivos?", "evaluacion-de-desempeno.md"),
    _c("¿qué pasa en mi primera semana?", "manual-onboarding.md"),
    # --- Seguridad ----------------------------------------------------------
    _c("¿tengo que cambiar la clave todos los meses?", "politica-contrasenas-y-accesos.md"),
    _c("¿puedo guardar contraseñas en una planilla?", "politica-contrasenas-y-accesos.md"),
    _c(
        "¿cuándo se dan de baja los accesos de alguien que se va?",
        "politica-contrasenas-y-accesos.md",
    ),
    _c("¿qué hago si detecto una intrusión?", "plan-respuesta-incidentes.md"),
    _c(
        "¿en cuánto tiempo hay que avisarle al cliente de una filtración?",
        "plan-respuesta-incidentes.md",
    ),
    _c("¿el disco de la notebook tiene que estar cifrado?", "politica-seguridad-informacion.md"),
    _c("¿cuánto tiempo se guardan los contratos?", "politica-clasificacion-datos.md"),
    _c("¿puedo usar datos reales para probar?", "politica-proteccion-datos-personales.md"),
    _c("¿cada cuánto se respalda la base de datos?", "politica-respaldos-y-continuidad.md"),
    _c("¿probamos alguna vez que las copias sirvan?", "politica-respaldos-y-continuidad.md"),
    # --- Procesos y calidad -------------------------------------------------
    _c(
        "¿cuándo se considera que un proyecto está en riesgo?", "procedimiento-gestion-proyectos.md"
    ),
    _c("¿quién aprueba el cierre de un proyecto?", "procedimiento-gestion-proyectos.md"),
    _c("¿cuánta cobertura de pruebas se exige?", "politica-calidad-software.md"),
    _c("¿qué se necesita para dar una tarea por terminada?", "politica-calidad-software.md"),
    _c("¿quién autoriza un cambio de 100 horas?", "procedimiento-gestion-cambios.md"),
    _c("¿puedo tocar producción en una urgencia?", "procedimiento-gestion-cambios.md"),
    _c("¿qué tan grande puede ser un cambio para que lo revisen?", "guia-revision-codigo.md"),
    # --- Legales y comercial ------------------------------------------------
    _c("¿cuándo hay que firmar un acuerdo de confidencialidad?", "acuerdo-confidencialidad.md"),
    _c("¿qué disponibilidad le prometemos a un cliente crítico?", "condiciones-sla-soporte.md"),
    _c("¿qué pasa si incumplimos el nivel de servicio?", "condiciones-sla-soporte.md"),
    _c("¿podemos subcontratar sin avisarle al cliente?", "politica-subcontratacion.md"),
    _c("¿qué descuento puedo ofrecer sin pedir permiso?", "politica-precios-y-descuentos.md"),
    _c("¿cuándo dejamos de calificar una oportunidad?", "proceso-de-preventa.md"),
    _c("¿a quién escala un cliente enojado?", "politica-atencion-al-cliente.md"),
    # --- Finanzas y administración ------------------------------------------
    _c("¿qué pasa si un cliente no paga?", "politica-facturacion-y-cobranzas.md"),
    _c("¿cuándo se emiten las facturas?", "politica-facturacion-y-cobranzas.md"),
    _c("¿cuántos presupuestos necesito para una compra grande?", "politica-compras.md"),
    _c("¿puedo comprar una licencia con mi tarjeta?", "politica-compras.md"),
    _c("¿cuánto cuesta la hora de un arquitecto?", "presupuesto-y-control-de-horas.md"),
    _c("¿cada cuánto se cargan las horas?", "presupuesto-y-control-de-horas.md"),
    # --- Técnico ------------------------------------------------------------
    _c("¿qué controles corren en cada carga de datos?", "estandar-arquitectura-datos.md"),
    _c("¿cómo se versiona una interfaz?", "guia-integracion-apis.md"),
    _c("¿cuántas peticiones por minuto se permiten?", "guia-integracion-apis.md"),
    _c("¿cuándo se hace el cierre del mes en el sistema?", "manual-operacion-erp.md"),
    # --- Ambiguas: más de un documento responde razonablemente --------------
    _c(
        "¿qué obligaciones tenemos con los datos de un cliente?",
        "politica-proteccion-datos-personales.md",
        "politica-clasificacion-datos.md",
        "acuerdo-confidencialidad.md",
    ),
    _c(
        "¿qué pasa ante una caída del servicio?",
        "condiciones-sla-soporte.md",
        "plan-respuesta-incidentes.md",
        "politica-respaldos-y-continuidad.md",
    ),
    # --- Fuera de dominio: la respuesta correcta es no devolver nada --------
    _c("¿va a llover mañana?"),
    _c("recetas de cocina italiana"),
    _c("¿quién ganó el partido del domingo?"),
    _c("cotización del dólar hoy"),
)
