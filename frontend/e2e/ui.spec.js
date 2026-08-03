import { expect, test } from "@playwright/test";

import { entrar, esperarPantalla, fijarTema } from "./apoyo";

/**
 * Defectos visuales que ningún test funcional ve.
 *
 * Todo esto se venía revisando a mano, con capturas, y por eso volvía: el mismo
 * par de tokens falló el contraste en TRES pantallas distintas —la fila, el
 * tablero de camas y las notificaciones— y el panel de trabajo del caso estuvo
 * varias fases metido en una columna de 320 px. Un ojo humano se cansa y una
 * captura muestra una pantalla por vez; esto mira todas.
 *
 * Corre en los dos temas porque son dos paletas distintas: un color que pasa en
 * claro puede no pasar en oscuro, y eso ya pasó con los colores de categoría de
 * nodo.
 */

const PANTALLAS = [
  { ruta: "/inicio", como: "medico" },
  { ruta: "/filas", como: "medico" },
  { ruta: "/casos", como: "medico" },
  { ruta: "/notificaciones", como: "medico" },
  { ruta: "/agenda", como: "medico" },
  { ruta: "/internacion", como: "medico" },
  { ruta: "/farmacia", como: "medico" },
  { ruta: "/supervision", como: "jefe" },
];

/** Contraste WCAG entre dos colores ya resueltos a `[r, g, b]`. */
function contraste([r1, g1, b1], [r2, g2, b2]) {
  const lum = (rgb) => {
    const [r, g, b] = rgb.map((n) => {
      const s = n / 255;
      return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const [a, b] = [lum([r1, g1, b1]), lum([r2, g2, b2])];
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

/**
 * Texto visible con su color y su fondo REAL.
 *
 * El fondo se busca subiendo por los ancestros hasta el primero que pinte: los
 * fallos que aparecieron eran justamente texto correcto sobre un contenedor
 * tintado (una fila destacada, un aviso), no sobre el fondo de la página.
 */
const RECOLECTAR = () => {
  /*
   * Cualquier color a `[r, g, b, a]`, usando el propio motor del navegador.
   *
   * Tailwind emite `oklab(... / 0.4)` para los tintes con opacidad, y leer eso
   * con una expresión regular de números da un color que no existe: la primera
   * versión de este test tomó un tinte casi blanco por negro y reportó ocho
   * fallos de contraste que no eran. Un chequeo que grita en falso se termina
   * desactivando, así que la conversión la hace el navegador.
   */
  const ctx = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  const rgba = (color) => {
    // Se PINTA y se lee el píxel, en vez de parsear el texto del color.
    //
    // `ctx.fillStyle` no normaliza: devuelve `oklab(0.95 0.002 -0.017 / 0.4)`
    // tal cual, y leerlo con una expresión regular de números da un color
    // inventado —así fue como la primera versión de este test tomó un tinte
    // casi blanco por gris medio y reportó ocho fallos que no existían—.
    // Pintar lo resuelve para cualquier espacio de color que el navegador
    // entienda, que es exactamente lo que se ve en pantalla.
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = color;
    ctx.fillRect(0, 0, 1, 1);
    const d = ctx.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], d[3] / 255];
  };
  // Un tinte semitransparente se ve mezclado con lo que tiene detrás, así que
  // se componen todos los fondos de la cadena hasta llegar a uno opaco.
  const sobre = (frente, fondo) => {
    const a = frente[3];
    return [
      Math.round(frente[0] * a + fondo[0] * (1 - a)),
      Math.round(frente[1] * a + fondo[1] * (1 - a)),
      Math.round(frente[2] * a + fondo[2] * (1 - a)),
      1,
    ];
  };
  const fondoDe = (e) => {
    const capas = [];
    let n = e;
    while (n && n !== document.documentElement) {
      const c = rgba(getComputedStyle(n).backgroundColor);
      if (c[3] > 0) {
        capas.push(c);
        if (c[3] === 1) break;
      }
      n = n.parentElement;
    }
    let base = [255, 255, 255, 1];
    for (const capa of capas.reverse()) base = sobre(capa, base);
    return base.slice(0, 3);
  };
  const out = [];
  for (const e of document.querySelectorAll("main *")) {
    if (e.children.length) continue;
    const r = e.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const txt = (e.textContent || "").trim();
    if (txt.length < 2) continue;
    const st = getComputedStyle(e);
    // Lo semitransparente es decoración (un placeholder, algo apagándose): su
    // color calculado no representa lo que se ve.
    if (st.visibility === "hidden" || Number(st.opacity) < 0.6) continue;
    const fondo = fondoDe(e);
    // El texto también puede tener alpha; se compone sobre su propio fondo.
    const col = rgba(st.color);
    out.push({
      txt: txt.slice(0, 40),
      fg: sobre(col, [...fondo, 1]).slice(0, 3),
      bg: fondo,
      size: parseFloat(st.fontSize), peso: Number(st.fontWeight) || 400,
    });
  }
  return out;
};

for (const tema of ["claro", "oscuro"]) {
  test.describe(`Revisión visual · tema ${tema}`, () => {
    for (const { ruta, como } of PANTALLAS) {
      test(`${ruta}`, async ({ page }) => {
        await entrar(page, como);
        await fijarTema(page, tema);
        await page.goto(ruta);
        await esperarPantalla(page);
        await page.waitForTimeout(1200);

        // 1. Nada se desborda a lo ancho. Una barra horizontal en una app de
        //    escritorio es siempre un error de layout, nunca una decisión.
        const desborde = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(desborde, `la página se desborda ${desborde}px a lo ancho`).toBeLessThanOrEqual(1);

        // 2. Contraste AA sobre el fondo real.
        const malos = [...new Set(
          (await page.evaluate(RECOLECTAR))
            .map((x) => {
              let ratio;
              try { ratio = contraste(x.fg, x.bg); } catch { return null; }
              const grande = x.size >= 18.66 || (x.size >= 14 && x.peso >= 700);
              return ratio < (grande ? 3 : 4.5)
                ? `${ratio.toFixed(2)}:1 — «${x.txt}» (rgb(${x.fg}) sobre rgb(${x.bg}))`
                : null;
            })
            .filter(Boolean),
        )];
        expect(malos, "texto por debajo del contraste AA").toEqual([]);
      });
    }
  });
}
