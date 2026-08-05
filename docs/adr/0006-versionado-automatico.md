# ADR-0006 — Versionado automático desde los mensajes de commit

**Estado:** Aceptada — agosto 2026

## Contexto

La versión del proyecto se mantenía a mano y en dos lugares (`pyproject.toml` y
`__init__.py`), lo que ya había producido una inconsistencia detectada en la
auditoría adversarial (`0.3.0` en la API vs `0.1.0` en el empaquetado). Además no
había tags, ni changelog, ni forma de saber qué cambió entre dos puntos del
historial: para una entrega que se evalúa leyendo el repositorio, eso es
información faltante.

Las herramientas habituales del ecosistema (`semantic-release`,
`commitizen`, `setuptools-scm`) resuelven el problema, pero agregan dependencias
—en algún caso todo un runtime de Node— a un proyecto cuyo núcleo tiene **una
sola dependencia de runtime**.

## Decisión

Derivar la versión de los **Conventional Commits** con una implementación propia
de ~200 líneas en `src/enterprise_agents/versionado.py`, expuesta como
`enterprise-agents version` y ejecutada por el workflow `release.yml` en la rama
por defecto:

| Commit | Salto |
|---|---|
| `fix:` · `perf:` · `refactor:` · `revert:` | parche |
| `feat:` | menor |
| `feat!:` o `BREAKING CHANGE:` en el cuerpo | mayor (menor mientras la versión sea `0.x`) |
| `docs:` · `test:` · `ci:` · `build:` · `chore:` · `style:` | ninguno |

El pipeline calcula el salto sobre los commits posteriores al último tag,
actualiza `__version__` y `CHANGELOG.md`, commitea con `[skip ci]`, crea el tag
`vX.Y.Z` y publica la release de GitHub con las notas generadas.

`pyproject.toml` pasa a declarar `dynamic = ["version"]` leyendo
`enterprise_agents.__version__`: una única fuente de verdad para el paquete, la
API HTTP (`FastAPI(version=...)`) y la CLI.

## Justificación

- **Cero dependencias nuevas**: solo la biblioteca estándar y `git`, coherente
  con el resto del proyecto.
- **Testeable**: el análisis son funciones puras (`analizar`,
  `siguiente_version`, `notas_de_version`, `actualizar_changelog`); lo único
  impuro son dos llamadas a `git log` / `git describe` y la escritura de los
  archivos. La misma disciplina de `tools/`: el código de decisión se puede
  probar sin entorno.
- **El historial pasa a ser documentación**: el changelog no se redacta, se
  deriva; no puede quedar desactualizado respecto de lo que se hizo.
- **Coherente con la demo**: `enterprise-agents version --proximo` permite ver
  localmente qué se publicaría, sin CI.

## Consecuencias

- Los mensajes de commit pasan a ser parte del contrato del repositorio: un
  commit fuera de convención simplemente no aparece en el changelog ni mueve la
  versión (se ignora en silencio, no rompe el pipeline). Queda documentado en
  `CLAUDE.md` y en el README.
- El workflow necesita `contents: write` y `fetch-depth: 0` (el análisis depende
  del historial y de los tags).
- Los commits del propio release llevan `[skip ci]` para no reentrar en el
  workflow; son `chore(release):`, que además no provocan salto.
- Mientras el proyecto siga en `0.x` un cambio de ruptura sube la menor
  (semver 2.0.0 §4); al llegar a `1.0.0` la regla cambia sola.
