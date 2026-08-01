/** Utilidades compartidas por la suite. */

export const USUARIOS = {
  admin: { email: "admin@cauce.local", pass: "admin1234" },
  medico: { email: "guardia.med@hospital.gob.ar", pass: "demo1234" },
  enfermeria: { email: "guardia.enf@hospital.gob.ar", pass: "demo1234" },
  jefe: { email: "guardia.jefe@hospital.gob.ar", pass: "demo1234" },
};

/**
 * Entra con un usuario y queda parado DENTRO de su institución.
 *
 * El super admin aterriza primero en el directorio de la plataforma y tiene que
 * elegir institución; el resto entra directo a la suya.
 *
 * La señal de «ya estoy adentro» es la URL /inicio. Ojo: el directorio TAMBIÉN
 * tiene un <aside>, así que esperar por el aside da un falso positivo y la
 * función vuelve sin haber entrado — con el resultado de que el test corre
 * entero contra la pantalla equivocada.
 */
export async function entrar(page, quien = "medico") {
  const u = USUARIOS[quien];
  await page.goto("/login");
  await page.fill('input[type="email"]', u.email);
  await page.fill('input[type="password"]', u.pass);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));

  const ingresar = page.getByRole("button", { name: /Ingresar/ }).first();
  await Promise.race([
    page.waitForURL(/\/inicio/).catch(() => {}),
    ingresar.waitFor({ state: "visible" }).catch(() => {}),
  ]);
  if (await ingresar.isVisible().catch(() => false)) await ingresar.click();
  await page.waitForURL(/\/inicio/);
}

/** ¿La página desborda en horizontal? Nunca debe pasar, en ningún ancho. */
export const desbordaHorizontal = (page) =>
  page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);

/** Fija el tema sin pasar por la interfaz (útil para preparar un test). */
export async function fijarTema(page, tema) {
  await page.evaluate((t) => localStorage.setItem("cauce.tema", t), tema);
  await page.reload();
  await page.waitForTimeout(600);
}

/**
 * Devuelve todos los textos visibles que NO llegan al contraste AA de WCAG,
 * calculando la razón real contra el fondo efectivo de cada elemento.
 *
 * Se mide en vez de revisar capturas porque el contraste es un número, y porque
 * es requisito de pliego en licitación pública: conviene que sea un test que
 * falla, no algo que alguien tiene que acordarse de mirar.
 */
export async function fallosDeContraste(page) {
  return page.evaluate(() => {
    /**
     * Luminancia relativa (WCAG) de un color computado.
     *
     * Hay que aceptar DOS formatos: `rgb(r, g, b)` con canales 0-255, y
     * `color(srgb r g b)` con canales 0-1, que es lo que devuelve el navegador
     * para cualquier color salido de `color-mix()`. Tratar el segundo como si
     * fuera 0-255 da luminancia ~0 para todo y el contraste sale 1:1 — un
     * medidor equivocado es peor que no medir.
     */
    const lum = (css) => {
      const m = css.match(/[\d.]+/g);
      if (!m) return null;
      const esCero255 = !css.startsWith("color(");
      const [r, g, b] = m.slice(0, 3).map(Number).map((v) => {
        const s = esCero255 ? v / 255 : v;
        return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    // Sube por los ancestros hasta encontrar un fondo realmente opaco.
    const fondoDe = (el) => {
      let n = el;
      while (n && n !== document.documentElement) {
        const bg = getComputedStyle(n).backgroundColor;
        const m = bg.match(/[\d.]+/g);
        if (m && (m.length < 4 || Number(m[3]) > 0.5)) return bg;
        n = n.parentElement;
      }
      return getComputedStyle(document.body).backgroundColor;
    };

    const fallos = [];
    document.querySelectorAll("*").forEach((el) => {
      const texto = [...el.childNodes]
        .filter((n) => n.nodeType === 3 && n.textContent.trim())
        .map((n) => n.textContent.trim())
        .join(" ");
      if (!texto) return;
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return;
      const cs = getComputedStyle(el);
      if (cs.visibility === "hidden" || cs.opacity === "0") return;

      const lf = lum(cs.color);
      const lb = lum(fondoDe(el));
      if (lf === null || lb === null) return;
      const [hi, lo] = [lf, lb].sort((a, b) => b - a);
      const razon = (hi + 0.05) / (lo + 0.05);

      // WCAG AA: 3:1 para texto grande (≥24px, o ≥18.66px en negrita), 4.5:1 el resto.
      const px = parseFloat(cs.fontSize);
      const grande = px >= 24 || (px >= 18.66 && Number(cs.fontWeight) >= 700);
      const minimo = grande ? 3 : 4.5;

      if (razon < minimo) {
        fallos.push({ texto: texto.slice(0, 40), razon: Number(razon.toFixed(2)), minimo });
      }
    });
    return fallos;
  });
}
