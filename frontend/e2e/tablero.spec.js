import { expect, test } from "@playwright/test";

import { entrar, esperarPantalla } from "./apoyo";

/**
 * Tablero del hospital.
 *
 * Los números vienen de la API stubbeada a propósito: lo que se prueba acá es
 * cómo la pantalla LEE esos números, y con la base de demo —que cambia sola,
 * porque los tests de la fila llaman pacientes de verdad— un «sin medición» o un
 * paciente repetido aparecen o no según el día.
 */
const TABLERO = {
  periodo: { desde: "2026-07-17", hasta: "2026-08-15", dias: 30, agrupacion: "dia" },
  resumen: {
    casos_activos: 120, en_cola: 8, urgentes: 2,
    ingresos: 177, cerrados: 66,
    espera_prom_min: 22.4, atencion_prom_min: 18, resolucion_prom_h: 4.2,
    turnos_periodo: 649, turnos_presentes: 274, turnos_ausentes: 59,
    turnos_cancelados: 35, turnos_sin_registrar: 281, ausentismo: 18,
    camas_total: 0, camas_operativas: 0, camas_ocupadas: 0, camas_libres: 0, ocupacion_camas: 0,
  },
  por_area: [
    {
      area_id: 1, nombre: "Guardia", activos: 40, en_cola: 8, atendidos: 1,
      espera_prom_min: 22.4, atencion_prom_min: 18, resolucion_prom_h: 3.1,
    },
    {
      // La de MÁS carga y sin fila: nunca tiene medición de espera. No es un
      // caso de borde, es el estado permanente de toda internación.
      area_id: 2, nombre: "Internación", activos: 58, en_cola: 0, atendidos: 0,
      espera_prom_min: null, atencion_prom_min: 0, resolucion_prom_h: 0,
    },
  ],
  por_estado: { cerrado: 113, recibido: 14 },
  serie_ingresos: [
    { fecha: "2026-08-13", casos: 40 },
    { fecha: "2026-08-14", casos: 51 },
    { fecha: "2026-08-15", casos: 56 },
  ],
  top_demoras: [
    { caso_id: 32952, paciente: "Silvia Castro", area: "Guardia", nodo: "Sala de espera", urgente: false, espera_min: 292 },
    { caso_id: 32938, paciente: "Silvia Castro", area: "Guardia", nodo: "Sala de espera", urgente: false, espera_min: 210 },
    { caso_id: 32971, paciente: "Marta Luna", area: "Guardia", nodo: "Sala de espera", urgente: false, espera_min: 120 },
  ],
};

const TABLERO_AREA = {
  area: { id: 1, nombre: "Guardia" },
  periodo: TABLERO.periodo,
  resumen: {
    activos: 40, en_cola: 8, atendidos: 1, ingresos: 106, cerrados: 66,
    espera_prom_min: null, atencion_prom_min: 18, resolucion_prom_h: 3.1,
  },
  por_paso: [], por_estado: { cerrado: 66 }, serie_ingresos: TABLERO.serie_ingresos,
  top_demoras: [], casos: [], flujos: [],
};

async function conTablero(page, datos = TABLERO, area = TABLERO_AREA) {
  const json = (cuerpo) => ({ status: 200, contentType: "application/json", body: JSON.stringify(cuerpo) });
  await page.route("**/api/instituciones/*/tablero/*", (r) => r.fulfill(json(datos)));
  await page.route("**/api/areas/*/tablero/*", (r) => r.fulfill(json(area)));
}

/** Color computado de una variable del tema, para comparar contra lo pintado. */
function colorDe(page, variable) {
  return page.evaluate((v) => {
    const d = document.createElement("div");
    d.style.color = `var(${v})`;
    document.body.append(d);
    const c = getComputedStyle(d).color;
    d.remove();
    return c;
  }, variable);
}

/** Distancia entre dos colores `rgb(r, g, b)`. Dos grises vecinos dan ~36. */
function distancia(a, b) {
  const n = (c) => c.match(/\d+(\.\d+)?/g).slice(0, 3).map(Number);
  const [x, y] = [n(a), n(b)];
  return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]);
}

test.describe("Tablero", () => {
  test.beforeEach(async ({ page }) => {
    await entrar(page, "admin");
    await conTablero(page);
  });

  test("una espera sin medición no se muestra como el mejor número de la tabla", async ({ page }) => {
    /*
     * El backend manda `null` a propósito y lo explica dos veces: «un 0 se lee
     * como 'acá no se espera' y se pinta del mejor color de la pantalla». Si esto
     * falla, el área con más carga del hospital aparece en verde y sin número, y
     * el jefe le saca gente para mandarla a Guardia.
     */
    await page.goto("/dashboard");
    await esperarPantalla(page);

    const tabla = page.locator("table").filter({ hasText: "ESPERA PROM." });
    const celda = tabla.locator("tbody tr", { hasText: "Internación" }).locator("td").nth(3);
    await expect(celda).toHaveText("—");

    const pintado = await celda.evaluate((el) => getComputedStyle(el).color);
    expect(pintado).not.toBe(await colorDe(page, "--color-badge-green-fg"));
  });

  test("la comparativa por área no convierte «sin medición» en cero", async ({ page }) => {
    /*
     * Con `|| 0` Internación salía primera en el gráfico con la barra en «0 min»
     * y en verde. Si el área desaparece sin decirlo, el jefe compara siete áreas
     * creyendo que están las ocho: por eso hay que nombrarlas.
     */
    await page.goto("/dashboard");
    await esperarPantalla(page);
    await page.getByRole("button", { name: "Espera", exact: true }).click();

    await expect(page.getByText(/Sin medición en el período: Internación/)).toBeVisible();
    await expect(page.getByText("0 min", { exact: true })).toHaveCount(0);
  });

  test("el ausentismo dice sobre cuántos turnos se calculó y cuántos quedaron abiertos", async ({ page }) => {
    /*
     * El 18 % es honesto pero va sobre 333 de 649 turnos. Con ese número se
     * decide sobreturno: sin el denominador y sin los 281 que nadie cerró, la
     * dirección sobreturnea al 18 % con un ausentismo real más cerca del 40 y la
     * sala de espera se desborda.
     */
    await page.goto("/dashboard");
    await esperarPantalla(page);

    await expect(page.getByText(/\d+ de \d+ turnos resueltos/)).toBeVisible();
    // `.first()` porque el tile aparece dos veces a propósito: la tira «Requiere
    // atención» repite los indicadores críticos que también están en la grilla
    // de abajo, igual que hace con «Urgentes» y «Espera prom.». Sin acotar, el
    // modo estricto de Playwright falla por encontrar dos.
    await expect(page.getByText("Turnos sin registrar").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Cerrarlos en la agenda" }).first()).toBeVisible();
  });

  test("en la dona, «Recibido» y «Cerrado» no son el mismo color ni dependen sólo del color", async ({ page }) => {
    /*
     * Los dos grises de badge dan 1,37:1 entre sí: los arcos se funden en uno y
     * el gigante gris se lee como «casi todo cerrado» con un 11 % de gente que
     * entró y nadie tocó adentro. Adentro del SVG no hay etiquetas, así que el
     * color era lo único que separaba un estado del otro.
     */
    await page.goto("/dashboard");
    await esperarPantalla(page);

    // Sólo los arcos de la dona llevan `stroke` propio; el resto de los círculos
    // de la pantalla toma el color por clase.
    const colores = await page.locator("svg circle").evaluateAll((els) =>
      els.filter((el) => el.getAttribute("stroke")).map((el) => getComputedStyle(el).stroke));
    expect(colores.length).toBe(2);
    // Los dos grises que había distaban ~36 en RGB: a esa distancia son el mismo
    // color a simple vista.
    expect(distancia(colores[0], colores[1])).toBeGreaterThan(60);

    // Y aparte del color: cada arco se nombra solo al pasar el mouse.
    await expect(page.locator("svg circle title")).toHaveText([
      "Cerrado: 113 (89%)",
      "Recibido: 14 (11%)",
    ]);
  });

  test("el top de demoras distingue dos casos del mismo paciente", async ({ page }) => {
    /*
     * Sin el código de caso, tres filas de «Silvia Castro» salen idénticas salvo
     * por los minutos: el jefe cree que hay tres pacientes demorados y no sabe
     * cuál abrir.
     */
    await page.goto("/dashboard");
    await esperarPantalla(page);

    await expect(page.getByText("#32952 · Guardia · Sala de espera")).toBeVisible();
    await expect(page.getByText("#32938 · Guardia · Sala de espera")).toBeVisible();
    await expect(page.getByText("2 casos en cola").first()).toBeVisible();
  });

  test("cuando el servidor recorta el rango, la pantalla lo dice", async ({ page }) => {
    /*
     * El backend recorta a 366 días y devuelve el rango real en `periodo`. Si no
     * se muestra, dirección pide «desde 2020», lee un total y se lo lleva a una
     * decisión de presupuesto creyendo que son seis años de historia.
     */
    await conTablero(page, {
      ...TABLERO,
      periodo: { desde: "2025-08-15", hasta: "2026-08-15", dias: 366, agrupacion: "semana" },
    });
    await page.goto("/dashboard?desde=2020-01-01&hasta=2026-08-15");
    await esperarPantalla(page);

    await expect(page.getByText(/Se muestran del.*15\/08\/2025.*al.*15\/08\/2026/)).toBeVisible();
    // Y el calendario no ofrece lo que el servidor no va a contestar.
    await expect(page.getByLabel("Desde")).toHaveAttribute("min", /\d{4}-\d{2}-\d{2}/);
  });

  test("la solapa de área muestra la producción del período, no una foto de un estado de paso", async ({ page }) => {
    /*
     * `atendidos` es la foto viva de los casos parados entre la atención y el
     * cierre: Guardia leía «Ingresos 106 / Atendidos 1» sobre treinta días en los
     * que cerró 66. Es el número que se lleva a la reunión de dotación.
     */
    await page.goto("/dashboard?area=1");
    await esperarPantalla(page);

    await expect(page.getByText("Cerrados", { exact: true })).toBeVisible();
    await expect(page.getByText("66", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Atendidos", { exact: true })).toHaveCount(0);
  });

  test("el rango se calcula en hora local: a las 23 no salta al día siguiente", async ({ page }) => {
    /*
     * `toISOString()` pasa a UTC antes de recortar y Buenos Aires es UTC-3: de
     * 21:00 a medianoche el rango se corría un día y la serie terminaba en un
     * bucket futuro que vale 0 —justo el punto que la línea dibuja más grande
     * porque es «hoy»—. El turno noche leía que dejaron de entrar pacientes.
     */
    await page.clock.setFixedTime(new Date("2026-08-15T23:30:00-03:00"));
    await page.goto("/dashboard");
    await esperarPantalla(page);

    await expect(page.getByLabel("Hasta")).toHaveValue("2026-08-15");
    await expect(page.getByLabel("Desde")).toHaveValue("2026-07-17");
  });
});
