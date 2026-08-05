/* EAS-DS — comportamiento compartido del design system:
   tema claro/oscuro, ripple, snackbar (estados del sistema) y fetch con estados. */

/* ---------- Tema ---------- */
(function initTema() {
  const guardado = localStorage.getItem("eas-tema");
  const preferido = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  document.documentElement.dataset.theme = guardado || preferido;
})();

function alternarTema() {
  const html = document.documentElement;
  html.dataset.theme = html.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem("eas-tema", html.dataset.theme);
  document.dispatchEvent(new CustomEvent("eas-tema-cambiado"));
}

/* ---------- Ripple (microinteracción de botones) ---------- */
document.addEventListener("pointerdown", (e) => {
  const btn = e.target.closest(".ds-btn");
  if (!btn || btn.disabled) return;
  const r = btn.getBoundingClientRect();
  const onda = document.createElement("span");
  const d = Math.max(r.width, r.height);
  onda.className = "ds-ripple";
  onda.style.width = onda.style.height = d + "px";
  onda.style.left = (e.clientX - r.left - d / 2) + "px";
  onda.style.top = (e.clientY - r.top - d / 2) + "px";
  btn.appendChild(onda);
  onda.addEventListener("animationend", () => onda.remove());
});

/* ---------- Snackbar (respuesta de estados del sistema) ---------- */
let _snackbarTimer = null;
function snackbar(mensaje, tipo = "") {
  let el = document.getElementById("ds-snackbar");
  if (!el) {
    el = document.createElement("div");
    el.id = "ds-snackbar";
    el.setAttribute("role", "status");
    document.body.appendChild(el);
  }
  el.className = "ds-snackbar " + tipo;
  el.textContent = mensaje;
  requestAnimationFrame(() => el.classList.add("visible"));
  clearTimeout(_snackbarTimer);
  _snackbarTimer = setTimeout(() => el.classList.remove("visible"), 4000);
}

/* ---------- Fetch con manejo de estados ---------- */
async function pedir(url, opciones = {}) {
  let r;
  try {
    r = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...opciones,
    });
  } catch {
    snackbar("Sin conexión con el servidor.", "error");
    throw new Error("red");
  }
  if (r.status === 401) { location.href = "/login?next=" + location.pathname; throw new Error("401"); }
  if (!r.ok) {
    const detalle = (await r.json().catch(() => ({}))).detail || `Error ${r.status}`;
    snackbar(detalle, "error");
    throw new Error(detalle);
  }
  return r.json();
}

/* ---------- Barra de aplicación compartida ---------- */
async function montarAppbar(activa) {
  const s = await pedir("/sesion").catch(() => null);
  if (!s) return null;
  const nav = document.querySelector(".ds-appbar nav");
  if (nav) {
    const tabs = [["/", "Chat", true]];
    if (["admin", "gestor"].includes(s.rol)) tabs.push(["/tablero", "Tablero", true]);
    if (s.rol === "admin") tabs.push(["/usuarios", "Usuarios", true]);
    nav.innerHTML = tabs
      .map(([ruta, nombre]) =>
        `<a class="ds-tab${ruta === activa ? " activa" : ""}" href="${ruta}">${nombre}</a>`)
      .join("");
  }
  const info = document.getElementById("ds-usuario");
  if (info) info.innerHTML =
    `<span class="ds-chip">${s.usuario} · ${s.rol}</span>` +
    `<span class="ds-estado" title="estado del sistema"><span class="punto"></span>${s.modo}</span>`;
  return s;
}

function salir() {
  fetch("/salir", { method: "POST" }).then(() => location.href = "/login");
}
