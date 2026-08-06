# ADR-0011 — Observabilidad: trazas de ejecución y estimación de tokens

**Estado:** Aceptada — agosto 2026

## Contexto

Un agente sin trazas es inauditable. Se ve la respuesta, pero no de dónde salió,
qué herramientas corrieron, en qué orden, cuánto tardó cada una ni cuánto
contexto consumió. Cuando algo sale mal —una cifra rara, una latencia de diez
segundos, una respuesta vacía— sin traza solo queda volver a ejecutar y mirar.

El módulo del arnés de evaluación ya había necesitado parte de esto: el
verificador de fundamentación tiene que saber qué produjo cada herramienta. Quedó
como una lista plana de spans, suficiente para verificar pero no para entender.

## Decisión

### Trazas jerárquicas

`trazas.py` registra cada llamada a herramienta con su agente, argumentos,
resultado, duración y padre. Tres decisiones de diseño:

1. **Los agentes no saben que existe.** El bucle emite eventos; quien quiera
   escucharlos abre un `capturar()`. Fuera de una captura no cuesta nada.
2. **Variable de contexto, no parámetro.** No contamina la firma de
   `Agent.run()` ni la de las herramientas, y el anidamiento se resuelve solo.
3. **El span se agrega al entrar, no al salir.** Si se agregara al final, una
   herramienta anidada quedaría registrada *antes* que la delegación que la
   contiene, porque termina antes. El árbol saldría invertido.

### Estimación de tokens

`tokens.py` estima sin llamar a ningún servicio. El conteo exacto lo define el
tokenizador del proveedor y no se puede reproducir sin su vocabulario; la API
ofrece `count_tokens` pero es una llamada de red, y este repositorio tiene que
poder medirse sin credenciales.

Se declara como estimación **en toda la interfaz**: en el visor, en la CLI y en
los docstrings. Sirve para comparar consultas entre sí y detectar una que se fue
de escala, no como medida de facturación.

No se incluye una tabla de precios: los precios cambian, y una tabla
desactualizada dentro del repositorio sería peor que no tenerla.

### Superficies

- `/trazas` — visor web con el árbol de spans, tiempos, tokens y una barra
  proporcional al span más lento, que es la forma de ver de un vistazo dónde se
  fue el tiempo. Roles gestor y admin.
- `enterprise-agents -v ask` — imprime el árbol en la terminal.
- Toda consulta de `/consultar` queda registrada.

## Justificación

- **La jerarquía no es cosmética.** Una lista plana de `[facturas_vencidas,
  delegar_analista_finanzas]` sugiere que la delegación ocurrió después. El árbol
  muestra lo que pasó.
- **Los tokens se suman por contexto y no una sola vez.** La salida de una
  herramienta cuenta en el especialista que la llamó y otra vez, dentro de la
  respuesta de ese especialista, en el orquestador. No es doble conteo: es la
  carga que el sistema procesó, que es lo que determina el costo. Para el aporte
  de un solo nivel está `tokens_por_agente`.

## Consecuencias

- **En memoria, no en SQLite.** Persistir agregaría un archivo que administrar,
  un esquema que migrar y una retención que implementar, para una demo de un
  solo proceso. Sería demostrar una técnica en vez de resolver un problema —el
  mismo criterio con que se descartó el índice aproximado en el ADR-0007. Es
  coherente además con el resto del estado de la demo (sesiones, control de
  intentos), ya documentado como riesgo aceptado. En producción esto se
  reemplaza por el sistema de trazas de la organización, no por SQLite: la forma
  de `Traza.a_dict()` está pensada para que ese salto sea un exportador.
- **Se corrigió un defecto de contrato al escribir los tests.** El bucle agéntico
  atrapa las excepciones de las herramientas a propósito —el error vuelve al
  modelo como `tool_result` para que se recupere—, así que la traza nunca las
  veía propagarse y los errores no quedaban marcados. El registro pasó a recibir
  un buzón (`Salida`) donde el llamador marca el error explícitamente.
- El resumen de cada span saltea el preámbulo de saneamiento: si no, todos los
  spans documentales se verían iguales y ninguno diría qué devolvió.
