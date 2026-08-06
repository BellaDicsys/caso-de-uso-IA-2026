# Documentos con inyecciones de prompt (material de prueba)

Estos documentos **no forman parte del corpus** de `data/documentos/`: existen
solo para la suite de seguridad (`enterprise-agents seguridad`).

Se mantienen en un directorio aparte por dos razones. Mezclarlos con el corpus
real distorsionaría las métricas de recuperación —el conjunto etiquetado mide
otra cosa— y un evaluador que abriera `data/documentos/` encontraría texto
malicioso sin contexto sobre por qué está ahí.

La suite arma un corpus combinado (documentos legítimos + estos) para verificar
el comportamiento de punta a punta, así que la separación es organizativa y no
debilita la prueba.

Cada archivo ejercita una categoría distinta: anulación de instrucciones,
suplantación de bloque de sistema, exfiltración, abuso de herramientas, autoridad
falsa, escape del delimitador e inyección redactada sin marcadores evidentes.
