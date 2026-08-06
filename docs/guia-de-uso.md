# Guía de uso — Enterprise Agent Suite

Manual del usuario final: cómo levantar la aplicación en local y cómo usarla.
Para la verificación formal de aceptación ver
[documento-funcional.md §5](documento-funcional.md); para el diseño interno,
[arquitectura.md](arquitectura.md).

> La misma información, resumida y sensible al rol, está dentro de la
> aplicación en **`/ayuda`** (botón ❔ de la barra superior).

---

## 1. Correr la aplicación en local

Es la única forma de ejecución prevista: **la entrega es sin deploy**, todo corre
en la máquina de quien evalúa. No hace falta clave de API ni conexión a internet.

**Requisito:** Python 3.10 o superior.

```bash
git clone https://github.com/BellaDicsys/caso-de-uso-IA-2026.git
cd caso-de-uso-IA-2026
pip install -e ".[dev]"
```

Recomendado, para no mezclar con el Python del sistema:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Levantar la aplicación web:

```bash
enterprise-agents serve          # http://localhost:8000
```

Y entrar con un usuario de demostración:

| Usuario | Clave | Rol |
|---|---|---|
| `admin` | `admin2026` | admin |
| `gestion` | `gestion2026` | gestor |
| `consulta` | `consulta2026` | consulta |

> Sobre HTTP local, si el navegador no guarda la cookie de sesión, arrancá con
> `ENTERPRISE_AGENTS_INSEGURO=1 enterprise-agents serve`: desactiva el atributo
> `Secure` de la cookie, pensado solo para desarrollo. El servidor lo advierte al
> arrancar.

### Desde VS Code

1. **Archivo → Abrir carpeta…** y elegir el repositorio clonado.
2. `Ctrl/Cmd + Shift + P` → **Python: Select Interpreter** → el intérprete de `.venv`.
3. Terminal integrada (`Ctrl + ñ`) → `pip install -e ".[dev]"`.
4. `enterprise-agents serve` y abrir el enlace que imprime la consola.

Para depurar, cualquier comando de la CLI funciona como módulo:
`python -m enterprise_agents demo`.

### Sin navegador, desde la terminal

```bash
enterprise-agents demo                                   # 5 escenarios de negocio
enterprise-agents -v ask "¿Qué facturas vencidas hay?"   # -v muestra las delegaciones
enterprise-agents eval                                   # set de evaluación (6 escenarios)
enterprise-agents version --proximo                      # versionado automático
```

### Con el modelo real (opcional)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
enterprise-agents ask --live "¿Cuánto facturamos a Banco Andino y quién puede tomar su próximo proyecto?"
```

Sin la variable, la suite corre en **modo demo**: un cliente simulado
determinístico que ejercita exactamente el mismo bucle agéntico, sin llamadas
externas ni costo.

---

## 2. Primeros pasos en la aplicación

Al entrar por primera vez, el chat muestra una **tarjeta de inducción** con lo
mínimo para arrancar; se descarta con *Entendido* y no vuelve a aparecer. La
ayuda completa queda siempre disponible en **`/ayuda`**.

### Qué se puede preguntar

| Dominio | Ejemplos | Fuente |
|---|---|---|
| 📊 Analítica | "¿Cuánto facturamos este año?" · "¿Qué proyectos están en riesgo?" | ventas y proyectos |
| 💰 Finanzas | "¿Qué facturas vencidas hay que reclamar?" · "¿Cuál es la deuda por cliente?" | facturas |
| 📄 Documental | "¿Qué dice la política de vacaciones?" · "¿Qué SLA tenemos comprometido?" | documentos corporativos |
| 👥 Personal | "¿Quién sabe Python y está libre?" · "¿Cómo está la disponibilidad del equipo?" | legajos |

### Cómo preguntar bien

- Preguntar por el **negocio**, no por el archivo.
- Una intención por consulta; si necesitás dos cosas, preguntá dos veces.
- Pedir el criterio ("…y decime cómo lo calculaste") para que explicite fuente y cálculo.

---

## 3. El tablero de control

Disponible para los roles **gestor** y **admin** en `/tablero`. Se refresca solo
y se pausa cuando la pestaña queda oculta.

- **KPIs** — facturación total, por cobrar, vencido, proyectos en riesgo y personas
  sin asignar.
- **Alertas tempranas** — el corazón del tablero, en tres severidades:
  | Severidad | Significa | Ejemplos |
  |---|---|---|
  | **crítica** | acción hoy | facturas vencidas, proyectos por encima del presupuesto de horas |
  | **seria** | acción esta semana | consumo > 90 % de horas, concentración de riesgo en un cliente |
  | **advertencia** | a vigilar | vencimientos próximos, capacidad ociosa |
- **Gráficos** — ventas por mes, deuda por cliente y consumo por proyecto, con
  paleta validada para daltonismo (el color nunca es el único portador del dato).

Cualquier alerta se puede profundizar en el chat: preguntar por su asunto devuelve
los registros concretos detrás del número.

---

## 4. Roles y permisos

El rol define qué ve el usuario **y qué puede consultar el asistente en su nombre**:
si un dominio no corresponde al rol, el agente directamente no recibe esa herramienta.

| Rol | Chat | Dominios habilitados | Tablero | Usuarios |
|---|---|---|---|---|
| `consulta` | sí | analítica y documentación | no | no |
| `gestor` | sí | los cuatro | sí | no |
| `admin` | sí | los cuatro | sí | sí |

La sesión dura 8 horas. Dar de baja un usuario cierra sus sesiones activas en el acto.

---

## 5. Versión móvil con voz

`/movil` tiene **alcance reducido a propósito**: solo el chat, para consultar de paso.
Suma dictado (🎤) y lectura en voz alta de las respuestas (🔊) mediante la Web Speech
API del navegador — disponible en Chrome/Edge de escritorio y Android; en iOS depende
de la versión de Safari. Si no está disponible, el chat sigue funcionando escrito.

---

## 6. Límites conocidos

- Responde **solo** sobre los cuatro dominios; fuera de alcance lo dice en vez de improvisar.
- **Solo lectura**: no emite facturas, no asigna personas, no modifica documentos.
- Los datos son **sintéticos**, representativos pero no reales.
- En **modo demo** resuelve un dominio por consulta; las consultas que cruzan dos
  dominios requieren el modelo real (`--live`).
