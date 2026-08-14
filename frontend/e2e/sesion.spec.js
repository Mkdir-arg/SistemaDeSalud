import { expect, test } from "@playwright/test";

import { entrar } from "./apoyo";

/**
 * Un solo refresco aunque varios pedidos venzan a la vez.
 *
 * Una pantalla dispara varias consultas en paralelo, así que cuando el access
 * token vence, todas reciben 401 casi al mismo tiempo. Sin coordinación cada una
 * pide su propio refresh: hoy eso son N viajes de más, y el día que el backend
 * active BLACKLIST_AFTER_ROTATION pasa a ser el cierre de sesión del usuario en
 * medio de la carga (el primer refresh invalidaría el token de los otros).
 *
 * El test mide lo observable: cuántos POST a /auth/token/refresh/ salen.
 */
test("varios 401 en paralelo disparan un solo refresh", async ({ page }) => {
  await entrar(page, "medico");

  // Se mide la CONCURRENCIA, no el total. Que haya dos refrescos separados en el
  // tiempo está bien (una consulta con refetch puede vencer más tarde y abrir su
  // propia tanda); lo que no puede pasar es que salgan dos a la vez, porque ahí
  // uno pisa al otro.
  const esRefresh = (r) => r.url().includes("/auth/token/refresh/");
  let enVuelo = 0;
  let pico = 0;
  page.on("request", (r) => { if (esRefresh(r)) pico = Math.max(pico, ++enVuelo); });
  page.on("requestfinished", (r) => { if (esRefresh(r)) enVuelo--; });
  page.on("requestfailed", (r) => { if (esRefresh(r)) enVuelo--; });

  // Se invalida solo el access: el refresh sigue bueno, así que la app tiene que
  // recuperarse sola en vez de mandar a login.
  await page.evaluate(() => {
    localStorage.setItem("cauce.access", "token-vencido-a-proposito");
  });

  await page.goto("/bandeja");
  await expect(page.getByRole("tablist")).toBeVisible();

  // Que el caso se haya dado de verdad: si no hubo ningún refresh, el test no
  // probó nada y hay que enterarse, no verlo pasar en verde.
  expect(pico).toBeGreaterThan(0);
  // Y nunca dos en paralelo, por más consultas que hayan fallado juntas.
  expect(pico).toBe(1);

  // Y la sesión sigue abierta, con el token renovado en lugar de borrado.
  await expect(page).not.toHaveURL(/\/login/);
  const refresh = await page.evaluate(() => localStorage.getItem("cauce.refresh"));
  expect(refresh).toBeTruthy();
});

/**
 * El pedido rezagado: el que vuelve tarde no pide un segundo refresh.
 *
 * El test de arriba cubre los 401 SIMULTÁNEOS, que se juntan en el refresco en
 * vuelo. Falta el otro caso, que es el que de verdad aparece: un pedido más
 * lento sale con el token viejo y vuelve cuando otro ya refrescó. Ahí no hay
 * refresco en vuelo al que sumarse y abría uno nuevo, para un token que ya
 * estaba renovado.
 *
 * Hoy eso es una rotación de más. El día que se active BLACKLIST_AFTER_ROTATION,
 * dos rezagados que coincidan se invalidan el token entre sí y la sesión se
 * cierra en medio de la pantalla.
 *
 * Apareció como un rojo suelto de la suite completa que no se reproducía
 * aislado; se ataja acá con los tiempos forzados en vez de dejarlo como
 * intermitente, que es como se convierte en un rojo que todos ignoran.
 */
test("un pedido que vuelve tarde no dispara un segundo refresh", async ({ page }) => {
  await entrar(page, "medico");

  let refrescos = 0;
  page.on("request", (r) => {
    if (r.url().includes("/auth/token/refresh/")) refrescos++;
  });

  const VENCIDO = "token-vencido-a-proposito";
  await page.evaluate((t) => localStorage.setItem("cauce.access", t), VENCIDO);

  /*
   * Los pedidos se identifican por el token con el que SALEN, no por el orden.
   *
   * La primera versión de este test contaba pedidos y demoraba al segundo, pero
   * el segundo era el REINTENTO del primero —que ya viajaba con el token nuevo—,
   * así que nunca había un rezagado y el test pasaba igual sin el arreglo.
   *
   * Acá se demora el segundo que lleva el token viejo: ése es el rezagado, y su
   * 401 vuelve cuando el refresco del primero ya terminó.
   */
  let conTokenViejo = 0;
  await page.route("**/api/**", async (ruta) => {
    const auth = ruta.request().headers()["authorization"] || "";
    if (auth.includes(VENCIDO)) {
      conTokenViejo += 1;
      if (conTokenViejo === 2) await new Promise((r) => setTimeout(r, 600));
    }
    return ruta.continue();
  });

  await page.goto("/bandeja");
  await expect(page.getByRole("tablist")).toBeVisible();

  // Que el caso se haya dado de verdad: sin dos pedidos con el token viejo no
  // hay rezagado y el test no probó nada.
  expect(conTokenViejo).toBeGreaterThan(1);
  expect(refrescos).toBe(1);
  await expect(page).not.toHaveURL(/\/login/);
});

/**
 * Un fallo del servidor al arrancar no es un cierre de sesión.
 *
 * Al montar, la app pregunta quién es la persona. Si esa consulta fallaba por
 * cualquier motivo se borraba el token y aparecía el login: un microcorte, o el
 * backend reiniciando, echaba a alguien en medio de una guardia. Peor todavía,
 * era silencioso — parecía que se había deslogueado sola.
 */
test("un 500 al arrancar no cierra la sesión: ofrece reintentar", async ({ page }) => {
  await entrar(page, "medico");

  // El servidor se cae justo para la consulta de identidad.
  let caido = true;
  await page.route("**/usuarios/me/", (route) =>
    caido ? route.fulfill({ status: 500, body: "{}" }) : route.continue(),
  );

  await page.reload();

  // No manda a login ni borra el token: avisa y da salida.
  await expect(page.getByRole("alert")).toContainText("No se pudo conectar");
  await expect(page).not.toHaveURL(/\/login/);
  expect(await page.evaluate(() => localStorage.getItem("cauce.refresh"))).toBeTruthy();

  // Y cuando el servidor vuelve, se recupera sin volver a escribir la contraseña.
  caido = false;
  await page.getByRole("button", { name: /Reintentar/ }).click();
  await expect(page.getByRole("alert")).toBeHidden();
});

/**
 * «Mantener la sesión iniciada» decide dónde vive el token.
 *
 * En una guardia la máquina es compartida. Si alguien destilda la casilla, su
 * token tiene que morir al cerrar el navegador y no quedar para el turno
 * siguiente: eso es `sessionStorage`. La casilla existía desde antes pero no
 * hacía nada —la sesión quedaba siempre guardada en el equipo—, que es peor que
 * no tenerla, porque la gente se apoya en ella.
 */
test.describe("Dónde queda la sesión", () => {
  const donde = (page) =>
    page.evaluate(() => ({
      local: !!localStorage.getItem("cauce.refresh"),
      sesion: !!sessionStorage.getItem("cauce.refresh"),
    }));

  async function entrarCon(page, recordar) {
    await page.goto("/login");
    await page.fill('input[type="email"]', "guardia.med@hospital.gob.ar");
    await page.fill('input[type="password"]', "demo1234");
    const casilla = page.getByLabel(/Mantener la sesión/);
    if (recordar) await casilla.check();
    else await casilla.uncheck();
    await page.click('button[type="submit"]');
    await page.waitForURL((u) => !u.pathname.startsWith("/login"));
  }

  test("destildada, el token no queda en el equipo", async ({ page }) => {
    await entrarCon(page, false);
    expect(await donde(page)).toEqual({ local: false, sesion: true });
  });

  test("tildada, el token sobrevive al cierre del navegador", async ({ page }) => {
    await entrarCon(page, true);
    expect(await donde(page)).toEqual({ local: true, sesion: false });
  });

  test("cambiar de opción no deja el token viejo dando vueltas", async ({ page }) => {
    await entrarCon(page, true);
    await page.evaluate(() => localStorage.removeItem("cauce.tema")); // ruido aparte
    await entrarCon(page, false);
    // Lo importante: en localStorage no puede haber quedado el de la vez anterior.
    expect(await donde(page)).toEqual({ local: false, sesion: true });
  });
});

/** Una credencial realmente rechazada sí tiene que mandar a login. */
test("un 401 al arrancar sí cierra la sesión", async ({ page }) => {
  await entrar(page, "medico");
  await page.route("**/usuarios/me/", (route) => route.fulfill({ status: 401, body: "{}" }));
  await page.reload();
  await expect(page).toHaveURL(/\/login/);
});
