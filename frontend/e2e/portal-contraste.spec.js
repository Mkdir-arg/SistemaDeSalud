import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

/**
 * Contraste AA de la app del paciente (#122), medido sobre las pantallas reales
 * (`playwright.portal-app.config.js`, backend real y el escenario de
 * `seed_portal_e2e`), en el celular de 375 px y en la compu.
 *
 * Cómo mide (WCAG 2.x, 1.4.3): por cada texto visible, el color computado del
 * texto contra el fondo efectivo, que se arma subiendo por los ancestros y
 * componiendo sus fondos hasta dar con uno opaco (si no hay, blanco). Mínimo
 * 4.5:1, o 3:1 para texto grande (≥ 24 px, o ≥ 18.66 px en negrita).
 *  - Los colores se pasan a sRGB pintándolos en un canvas: así sirve cualquier
 *    formato que devuelva el navegador (rgb, oklch, color()).
 *  - Sobre `hen-cta` se usan los dos extremos de `--gradient-action` y se exige
 *    el peor; otro degradado, todas sus paradas. Un fondo con imagen no se puede
 *    medir así y hace fallar la prueba, para que nadie lo dé por bueno sin mirar.
 *  - La opacidad de los ancestros se aplica al texto (aproximación: no
 *    atenúa los fondos que quedan dentro del mismo ancestro translúcido).
 *  - Se ignora lo oculto, lo `aria-hidden`, lo `sr-only` y los controles
 *    deshabilitados (WCAG los exceptúa). Los placeholders se miden si tienen texto.
 *  - Sólo ve ancestros: un texto puesto encima de algo que no es su ancestro
 *    (posicionado sobre una foto) se mediría contra el fondo equivocado.
 *
 * No toca datos: los estados que dependen de lo que ya hicieron otras pruebas
 * (turno cancelable, en espera, llamado) se fuerzan reescribiendo la respuesta real.
 */
const ESCENARIO = process.env.PORTAL_E2E_ESCENARIO;
const E = ESCENARIO ? JSON.parse(readFileSync(ESCENARIO, "utf-8")) : null;
const CLAVE = process.env.DEMO_PASSWORD || "demo1234";

test.skip(!E, "Falta PORTAL_E2E_ESCENARIO (el JSON de seed_portal_e2e).");
test.describe.configure({ mode: "serial" });

// El ingreso tiene límite por email: una sola sesión, pedida por la API.
let sesion = null;

async function ingresar(page) {
  if (!sesion) {
    const r = await page.request.post("/api/mi/cuenta/ingresar/", { data: { email: E.email, password: CLAVE } });
    expect(r.ok(), await r.text()).toBeTruthy();
    sesion = await r.json();
  }
  await page.addInitScript(({ access, refresh }) => {
    if (sessionStorage.getItem("hen.portal.access")) return;
    sessionStorage.setItem("hen.portal.access", access);
    sessionStorage.setItem("hen.portal.refresh", refresh);
  }, sesion);
}

test.beforeEach(async ({ page }) => {
  // Sin animaciones: se mide el estado final, no un fundido a mitad de camino.
  await page.emulateMedia({ reducedMotion: "reduce" });
});

/** Mide el contraste de todo el texto visible dentro de `raiz` (en la página). */
function medirEnPagina(raiz) {
  const lienzo = document.createElement("canvas");
  lienzo.width = lienzo.height = 1;
  const ctx = lienzo.getContext("2d", { willReadFrequently: true });
  const cache = new Map();
  function rgba(color) {
    if (cache.has(color)) return cache.get(color);
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = "rgba(0, 0, 0, 0)";
    ctx.fillStyle = color;
    ctx.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data;
    const c = { r, g, b, a: a / 255 };
    cache.set(color, c);
    return c;
  }
  const sobre = (arriba, abajo) => ({
    r: arriba.r * arriba.a + abajo.r * (1 - arriba.a),
    g: arriba.g * arriba.a + abajo.g * (1 - arriba.a),
    b: arriba.b * arriba.a + abajo.b * (1 - arriba.a),
    a: 1,
  });
  const lin = (v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  const luminancia = (c) => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
  const razon = (a, b) => { const [x, y] = [luminancia(a), luminancia(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const hex = (c) => `#${[c.r, c.g, c.b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("")}`;
  const COLOR = /(?:rgba?|hsla?|oklch|oklab|lab|lch|color)\([^()]*\)|#[0-9a-f]{3,8}\b|\b(?:transparent|white|black)\b/gi;
  const extremosCta = (getComputedStyle(document.documentElement).getPropertyValue("--gradient-action").match(COLOR) || []).map(rgba);

  function describir(el) {
    const clases = typeof el.className === "string" ? el.className.trim().split(/\s+/).slice(0, 4).join(".") : "";
    return `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ""}${clases ? `.${clases}` : ""}`;
  }

  /** Fondos posibles detrás de `el` (más de uno si hay un degradado), o un motivo para no medir. */
  function fondos(el) {
    const capas = []; // de arriba hacia abajo
    for (let n = el; n; n = n.parentElement) {
      const s = getComputedStyle(n);
      const imagen = s.backgroundImage;
      if (imagen && imagen !== "none") {
        if (/url\(/.test(imagen)) return { motivo: `fondo con imagen en ${describir(n)}` };
        const paradas = n.classList.contains("hen-cta") ? extremosCta : (imagen.match(COLOR) || []).map(rgba);
        if (!paradas.length) return { motivo: `degradado sin colores legibles en ${describir(n)}` };
        capas.push(paradas);
        if (paradas.every((p) => p.a === 1)) return { candidatos: componer(capas, [{ r: 255, g: 255, b: 255, a: 1 }]) };
      }
      const color = rgba(s.backgroundColor);
      if (color.a > 0) {
        capas.push([color]);
        if (color.a === 1) break;
      }
    }
    return { candidatos: componer(capas, [{ r: 255, g: 255, b: 255, a: 1 }]) };
  }
  function componer(capas, base) {
    let candidatos = base;
    for (const capa of [...capas].reverse()) candidatos = candidatos.flatMap((c) => capa.map((p) => sobre(p, c)));
    return candidatos;
  }

  function opacidad(el) {
    let o = 1;
    for (let n = el; n; n = n.parentElement) o *= Number(getComputedStyle(n).opacity);
    return o;
  }

  const fallas = [];
  const noMedibles = [];
  let medidos = 0;
  const vistos = new Set();

  function revisar(el, texto, colorTexto) {
    if (el.closest('[aria-hidden="true"], :disabled, [aria-disabled="true"], [inert]')) return;
    if (!el.checkVisibility({ opacityProperty: true, visibilityProperty: true })) return;
    const s = getComputedStyle(el);
    const t = { ...rgba(colorTexto) };
    t.a *= opacidad(el);
    if (t.a === 0) return;
    const f = fondos(el);
    const resumen = texto.replace(/\s+/g, " ").trim().slice(0, 60);
    if (f.motivo) { noMedibles.push(`«${resumen}» (${describir(el)}): ${f.motivo}`); return; }
    const tam = parseFloat(s.fontSize);
    const grande = tam >= 24 || (tam >= 18.66 && Number(s.fontWeight) >= 700);
    const minimo = grande ? 3 : 4.5;
    medidos += 1;
    let peor = null;
    for (const fondo of f.candidatos) {
      const visto = sobre(t, fondo);
      const r = razon(visto, fondo);
      if (!peor || r < peor.r) peor = { r, visto, fondo };
    }
    if (peor.r + 1e-9 < minimo) {
      const clave = `${resumen}|${hex(peor.visto)}|${hex(peor.fondo)}`;
      if (vistos.has(clave)) return;
      vistos.add(clave);
      fallas.push(`«${resumen}» (${describir(el)}, ${tam}px/${s.fontWeight}): texto ${hex(peor.visto)} sobre ${hex(peor.fondo)} = ${peor.r.toFixed(2)}:1, pide ${minimo}:1`);
    }
  }

  const raices = [...document.querySelectorAll(raiz)];
  for (const r of raices) {
    const caminante = document.createTreeWalker(r, NodeFilter.SHOW_TEXT);
    for (let nodo = caminante.nextNode(); nodo; nodo = caminante.nextNode()) {
      if (!nodo.textContent.trim()) continue;
      const el = nodo.parentElement;
      if (!el || ["SCRIPT", "STYLE", "NOSCRIPT", "TITLE", "OPTION"].includes(el.tagName)) continue;
      const rango = document.createRange();
      rango.selectNodeContents(nodo);
      const caja = rango.getBoundingClientRect();
      if (caja.width <= 1 || caja.height <= 1) continue; // sr-only y recortados
      revisar(el, nodo.textContent, getComputedStyle(el).color);
    }
    for (const campo of r.querySelectorAll("input, textarea, select")) {
      if (["hidden", "checkbox", "radio", "submit", "button", "file", "range", "color"].includes(campo.type)) continue;
      if (campo.value) revisar(campo, campo.type === "password" ? "(contraseña)" : campo.value, getComputedStyle(campo).color);
      else if (campo.placeholder?.trim()) revisar(campo, `placeholder: ${campo.placeholder}`, getComputedStyle(campo, "::placeholder").color);
    }
  }
  return { raices: raices.length, medidos, fallas, noMedibles };
}

async function revisar(page, raiz = "body") {
  // Que terminen las transiciones finitas (las infinitas, como el pulso, no cuentan).
  await page.waitForFunction(() => document.getAnimations().every((a) => a.playState !== "running" || a.effect?.getComputedTiming().iterations === Infinity));
  const r = await page.evaluate(medirEnPagina, raiz);
  expect(r.raices, `no se encontró ${raiz}`).toBeGreaterThan(0);
  expect(r.medidos, "no se midió ningún texto").toBeGreaterThan(0);
  expect(r.noMedibles, `textos que no se pudieron medir:\n${r.noMedibles.join("\n")}`).toEqual([]);
  expect(r.fallas, `contraste por debajo de AA:\n${r.fallas.join("\n")}`).toEqual([]);
}

/** Reescribe una respuesta real de `/api/mi/*`. */
async function reescribir(page, ruta, cambio) {
  await page.route(`**/api/mi${ruta}`, async (r) => {
    if (r.request().method() !== "GET") return r.fallback();
    const real = await r.fetch();
    await r.fulfill({ response: real, json: cambio(await real.json()) });
  });
}

test("bienvenida e ingreso, sin sesión", async ({ page }) => {
  await page.goto("/mi");
  await expect(page.getByRole("heading", { name: "Tu cuenta de paciente" })).toBeVisible();
  await revisar(page);

  await page.goto("/mi/ingresar");
  await expect(page.getByLabel("Email")).toBeVisible();
  await revisar(page);

  // El error de credenciales, sin gastar intentos del límite de ingresos.
  await page.route("**/api/mi/cuenta/ingresar/", (r) => r.fulfill({ status: 401, json: { detail: "Email o contraseña incorrectos.", codigo: "credenciales_invalidas" } }));
  await page.getByLabel("Email").fill(E.email);
  await page.getByLabel("Contraseña").fill("incorrecta");
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await revisar(page);
});

test("inicio, turnos, estudios, cobertura y cuenta", async ({ page }) => {
  await ingresar(page);
  const pantallas = [
    ["/mi/inicio", page.getByRole("heading", { name: "Hola, Andrea" })],
    ["/mi/turnos", page.locator(`a[href="/mi/turnos/${E.turno_cercano}"]`)],
    ["/mi/turnos?ver=anteriores", page.getByRole("tab", { name: "Anteriores", selected: true })],
    [`/mi/turnos/${E.turno_cercano}`, page.getByText(/Faltan menos de 24 horas/)],
    ["/mi/estudios", page.getByText("Hemograma completo")],
    ["/mi/cobertura", page.getByText("Mutual del Valle")],
    ["/mi/cuenta", page.getByText("FIC199001")],
  ];
  for (const [ruta, señal] of pantallas) {
    await test.step(ruta, async () => {
      await page.goto(ruta);
      await expect(señal).toBeVisible();
      await revisar(page);
    });
  }
});

test("turno cancelable y la hoja de cancelar", async ({ page }) => {
  await ingresar(page);
  // Otra prueba puede haberlo cancelado ya: se lo muestra como reservado.
  await reescribir(page, "/turnos/", (d) => ({
    ...d,
    turnos: d.turnos.map((t) => (t.id === E.turno_cancelable
      ? { ...t, estado: "reservado", estado_display: "Reservado", cancelado_via: "", puede_confirmar: true, puede_cancelar: true, motivo_no_cancelable: null }
      : t)),
  }));
  await page.goto(`/mi/turnos/${E.turno_cancelable}`);
  await expect(page.getByRole("button", { name: "Cancelar turno" })).toBeVisible();
  await revisar(page);

  await page.goto(`/mi/turnos/${E.turno_cancelable}?cancelar`);
  await expect(page.getByRole("dialog")).toBeVisible();
  // Detrás queda el velo: sólo se mide la hoja.
  await revisar(page, '[role="dialog"]');
});

test("sala de espera: en espera, sin fila y llamado", async ({ page }) => {
  await ingresar(page);
  let estado = "en_espera";
  await reescribir(page, "/llamado/", (d) => {
    const institucion = d.institucion || { nombre: "Hospital Central" };
    if (estado === "llamado") return { estado, box: "Box 1", institucion, llamado_at: new Date().toISOString(), veces: 2 };
    return estado === "en_espera" ? { estado, institucion } : { estado };
  });
  await page.goto("/mi/llamado");
  await expect(page.getByText("Estás en la sala de espera")).toBeVisible();
  await revisar(page);

  estado = "sin_fila";
  await page.reload();
  await expect(page.getByText("No estás en una sala de espera")).toBeVisible();
  await revisar(page);

  estado = "llamado";
  await page.reload();
  await expect(page.getByRole("alert")).toContainText("Te están llamando");
  // Pantalla completa encima de todo: sólo se mide el aviso.
  await revisar(page, '[role="alert"]');
});

test("errores y vacíos", async ({ page }) => {
  await ingresar(page);
  await page.route("**/api/mi/turnos/", (r) => r.abort("internetdisconnected"));
  await page.goto("/mi/turnos");
  await expect(page.getByText("No pudimos cargar tus turnos.")).toBeVisible();
  await revisar(page);

  await page.route("**/api/mi/resultados/", (r) => r.fulfill({ json: { resultados: [] } }));
  await page.route("**/api/mi/cobertura/", (r) => r.fulfill({ json: { coberturas: [] } }));
  await page.goto("/mi/estudios");
  await expect(page.getByText("Todavía no tenés estudios")).toBeVisible();
  await revisar(page);
  await page.goto("/mi/cobertura");
  await expect(page.getByText("No encontramos una cobertura vigente")).toBeVisible();
  await revisar(page);
});

test("sesión vencida", async ({ page }) => {
  await ingresar(page);
  await page.goto("/mi/inicio");
  await page.evaluate(() => {
    sessionStorage.setItem("hen.portal.access", "hp_vencido");
    sessionStorage.setItem("hen.portal.refresh", "hp_vencido");
  });
  await page.goto("/mi/turnos");
  await expect(page.getByText("Tu sesión venció. Ingresá de nuevo.")).toBeVisible();
  await revisar(page);
});
