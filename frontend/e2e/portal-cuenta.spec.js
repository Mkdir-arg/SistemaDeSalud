import { expect, test } from "@playwright/test";

/**
 * Portal del paciente (#120): cuenta propia e identidad validada por RENAPER.
 * La API `/api/mi/*` se intercepta acá (`playwright.portal.config.js`); el
 * contrato es el del backend del #120.
 */
const DETALLE_NEUTRO = "Si el email es válido, te mandamos un correo con los pasos a seguir.";
const CUENTA = {
  email: "ana@example.com", email_verificado: true, identidad: "sin_validar",
  nombre: null, apellido: null, documento: null, sexo: null,
  identidad_validada_at: null, validacion_bloqueada_hasta: null, intentos_restantes: 3,
};
// Como el simulado de RENAPER: el nombre y el apellido vienen de ahí.
const VALIDADA = { ...CUENTA, identidad: "validada", nombre: "Ana María", apellido: "Pérez", documento: "34521521", sexo: "F", identidad_validada_at: "2026-10-06T10:00:00-03:00" };
const PERFIL = { nombre: "Ana María", apellido: "Pérez", documento: "34521521", fecha_nacimiento: "1990-03-14" };
const SESION = { access: "hp_access_1", refresh: "hp_refresh_1", access_vence: "2026-10-06T11:00:00-03:00" };

/**
 * Intercepta la API. `rutas` mapea «MÉTODO /ruta/» (sin `/api/mi`) a una función
 * que recibe el pedido y devuelve `{status, body}`. Lo que no está mapeado
 * falla a la vista. El resto de `/api/` (la sesión del sistema) responde 401, o
 * lo que diga `sistema`, y queda anotado en `pedidos.sistema`.
 * Solo la ruta del backend: un patrón suelto también atrapa /src/api/*.js de Vite.
 */
async function api(page, rutas, { sistema = () => ({ status: 401, body: { detail: "Sin sesión del sistema." } }) } = {}) {
  const pedidos = [];
  pedidos.sistema = [];
  await page.route(/^https?:\/\/[^/]+\/api\//, async (ruta) => {
    const req = ruta.request();
    const path = new URL(req.url()).pathname;
    if (!path.startsWith("/api/mi/")) {
      pedidos.sistema.push({ path, headers: req.headers() });
      const { status, body } = sistema(path);
      return ruta.fulfill({ status, json: body });
    }
    const clave = `${req.method()} ${path.slice("/api/mi".length)}`;
    const pedido = { clave, headers: req.headers(), body: req.postData() ? req.postDataJSON() : null };
    pedidos.push(pedido);
    const manejar = rutas[clave];
    if (!manejar) return ruta.fulfill({ status: 599, json: { detail: `sin mock: ${clave}` } });
    const { status = 200, body = null, demora = 0 } = await manejar(pedido);
    if (demora) await new Promise((r) => setTimeout(r, demora));
    return body === null ? ruta.fulfill({ status }) : ruta.fulfill({ status, json: body });
  });
  return pedidos;
}

const de = (pedidos, clave) => pedidos.filter((p) => p.clave === clave);

/** Rutas de una sesión: ingresar devuelve tokens y la cuenta, que se lee de `estado`. */
function conSesion(estado, extra = {}) {
  return {
    "POST /cuenta/ingresar/": () => ({ body: { ...SESION, cuenta: estado.cuenta } }),
    "GET /cuenta/": () => ({ body: estado.cuenta }),
    "GET /perfil/": () => ({ body: PERFIL }),
    "POST /cuenta/salir/": () => ({ status: 204 }),
    ...extra,
  };
}

async function ingresar(page, email = "ana@example.com", password = "una-clave-larga") {
  await page.goto("/mi/ingresar");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Contraseña").fill(password);
  await page.getByRole("button", { name: "Ingresar" }).click();
}

test("bienvenida pública, en tema claro y sin la marca de la demo", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("salud.tema", "oscuro"));
  await api(page, {});
  await page.goto("/mi");
  await expect(page.getByRole("heading", { name: "Tu cuenta de paciente" })).toBeVisible();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await expect(page.getByText("Clínica Modelo")).toHaveCount(0);
  await expect(page).toHaveTitle("Mi portal de salud");
  await page.getByRole("link", { name: "Crear cuenta" }).click();
  await expect(page).toHaveURL("/mi/crear-cuenta");
});

test("crear cuenta pide solo el email, muestra el mensaje neutro y deja reenviar", async ({ page }) => {
  let primera = true;
  const pedidos = await api(page, {
    "POST /cuenta/registro/": () => {
      if (primera) { primera = false; return { status: 400, body: { email: ["Ingresá un email válido."] } }; }
      return { status: 202, body: { detail: DETALLE_NEUTRO } };
    },
    "POST /cuenta/reenviar-verificacion/": () => ({ status: 202, body: { detail: "Si corresponde, te reenviamos el correo." } }),
  });
  await page.goto("/mi/crear-cuenta");
  await expect(page.getByLabel("Email")).toHaveAttribute("autocomplete", "email");
  // La contraseña se elige desde el enlace del correo, no acá.
  await expect(page.locator("input[type=password]")).toHaveCount(0);
  await page.getByLabel("Email").fill("ana@");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(page.getByText("Ingresá un email válido.")).toBeVisible();
  await expect(page.getByLabel("Email", { exact: true })).toHaveAttribute("aria-invalid", "true");

  await page.getByLabel("Email").fill("ana@example.com");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(page.getByText("Abrí el enlace que te mandamos para elegir tu contraseña.")).toBeVisible();
  await expect(page.getByText(DETALLE_NEUTRO)).toBeVisible();
  await expect(page.getByText(/ya existe|no existe/i)).toHaveCount(0);
  expect(de(pedidos, "POST /cuenta/registro/").at(-1).body).toEqual({ email: "ana@example.com" });

  await page.getByRole("button", { name: "Reenviar el correo" }).click();
  await expect(page.getByText("Si corresponde, te reenviamos el correo.")).toBeVisible();
  expect(de(pedidos, "POST /cuenta/reenviar-verificacion/")[0].body).toEqual({ email: "ana@example.com" });
});

/** En la pantalla del enlace: elige la contraseña y la repite. */
async function elegirClave(page, clave = "una-clave-larga") {
  await page.getByLabel("Contraseña", { exact: true }).fill(clave);
  await page.getByLabel("Repetí la contraseña").fill(clave);
  await page.getByRole("button", { name: "Guardar y entrar" }).click();
}

test("el enlace del alta elige la contraseña, deja logueada y lleva a validar la identidad", async ({ page }) => {
  const estado = { cuenta: CUENTA };
  const pedidos = await api(page, conSesion(estado, {
    "POST /cuenta/verificar-email/": () => ({ body: { ...SESION, cuenta: CUENTA } }),
  }));
  await page.goto("/mi/verificar-email#token=tok-verif-123");
  await expect(page.getByRole("heading", { name: "Elegí tu contraseña" })).toBeVisible();
  // El token sale de la barra apenas se lee.
  expect(page.url()).not.toContain("#");
  expect(page.url()).not.toContain("tok-verif-123");
  await expect(page.getByLabel("Contraseña", { exact: true })).toHaveAttribute("autocomplete", "new-password");
  await elegirClave(page);
  await expect(page).toHaveURL("/mi/validar-identidad");
  const enviados = de(pedidos, "POST /cuenta/verificar-email/");
  expect(enviados).toHaveLength(1);
  expect(enviados[0].body).toEqual({ token: "tok-verif-123", password: "una-clave-larga" });
  expect(await page.evaluate(() => sessionStorage.getItem("hen.portal.access"))).toBe(SESION.access);
});

test("una contraseña débil no gasta el enlace: se reintenta con el mismo token", async ({ page }) => {
  let intentos = 0;
  const pedidos = await api(page, conSesion({ cuenta: VALIDADA }, {
    "POST /cuenta/verificar-email/": () => {
      intentos += 1;
      if (intentos === 1) return { status: 400, body: { password: ["La contraseña es demasiado corta."] } };
      return { body: { ...SESION, cuenta: VALIDADA } };
    },
  }));
  await page.goto("/mi/verificar-email#token=tok-debil");
  await elegirClave(page, "corta");
  await expect(page.getByText("La contraseña es demasiado corta.")).toBeVisible();
  await expect(page.getByLabel("Contraseña", { exact: true })).toHaveAttribute("aria-invalid", "true");
  await elegirClave(page, "una-clave-larga");
  await expect(page).toHaveURL("/mi/cuenta");
  expect(de(pedidos, "POST /cuenta/verificar-email/").map((p) => p.body.token)).toEqual(["tok-debil", "tok-debil"]);
});

test("el enlace del alta vencido o usado ofrece pedir otro", async ({ page }) => {
  await api(page, { "POST /cuenta/verificar-email/": () => ({ status: 400, body: { detail: "El enlace no es válido.", codigo: "enlace_invalido" } }) });
  await page.goto("/mi/verificar-email#token=viejo");
  await elegirClave(page);
  await expect(page.getByRole("heading", { name: "El enlace ya no sirve" })).toBeVisible();
  await expect(page.getByText("El enlace no es válido.")).toBeVisible();
  await page.getByRole("link", { name: "Pedir un enlace nuevo" }).click();
  await expect(page).toHaveURL("/mi/reenviar-verificacion");
});

test("un segundo enlace pegado en la misma pestaña se procesa", async ({ page }) => {
  const pedidos = await api(page, conSesion({ cuenta: CUENTA }, {
    "POST /cuenta/verificar-email/": (p) => (p.body.token === "tok-b"
      ? { body: { ...SESION, cuenta: CUENTA } }
      : { status: 400, body: { detail: "El enlace no es válido.", codigo: "enlace_invalido" } }),
  }));
  await page.goto("/mi/verificar-email#token=tok-a");
  await elegirClave(page);
  await expect(page.getByRole("heading", { name: "El enlace ya no sirve" })).toBeVisible();
  await page.evaluate(() => { window.mismaCarga = true; });
  // Navegación de fragmento: el documento no se recarga y la pantalla arranca de cero.
  await page.goto("/mi/verificar-email#token=tok-b");
  await expect(page.getByRole("button", { name: "Guardar y entrar" })).toBeVisible();
  expect(await page.evaluate(() => window.mismaCarga)).toBe(true);
  await expect.poll(() => page.url()).not.toContain("tok-b");
  await elegirClave(page);
  await expect(page).toHaveURL("/mi/validar-identidad");
  expect(de(pedidos, "POST /cuenta/verificar-email/").map((p) => p.body.token)).toEqual(["tok-a", "tok-b"]);
});

test("el mismo enlace pegado dos veces también sale de la barra", async ({ page }) => {
  const pedidos = await api(page, conSesion({ cuenta: CUENTA }, {
    "POST /cuenta/verificar-email/": () => ({ body: { ...SESION, cuenta: CUENTA } }),
  }));
  await page.goto("/mi/verificar-email#token=tok-x");
  await expect(page.getByRole("heading", { name: "Elegí tu contraseña" })).toBeVisible();
  await expect.poll(() => page.url()).not.toContain("tok-x");
  await page.evaluate(() => { window.mismaCarga = true; });
  await page.goto("/mi/verificar-email#token=tok-x");
  await expect.poll(() => page.url()).not.toContain("tok-x");
  expect(await page.evaluate(() => window.mismaCarga)).toBe(true);
  await elegirClave(page);
  await expect(page).toHaveURL("/mi/validar-identidad");
  expect(de(pedidos, "POST /cuenta/verificar-email/").map((p) => p.body.token)).toEqual(["tok-x"]);
});

test("reenviar la verificación muestra el mensaje neutro", async ({ page }) => {
  const pedidos = await api(page, { "POST /cuenta/reenviar-verificacion/": () => ({ status: 202, body: { detail: DETALLE_NEUTRO } }) });
  await page.goto("/mi/reenviar-verificacion");
  await page.getByLabel("Email").fill("nadie@example.com");
  await page.getByRole("button", { name: "Reenviar el enlace" }).click();
  await expect(page.getByText(DETALLE_NEUTRO)).toBeVisible();
  expect(de(pedidos, "POST /cuenta/reenviar-verificacion/")[0].body).toEqual({ email: "nadie@example.com" });
});

test("ingresar con credenciales inválidas (o sin confirmar) ayuda a quien recién se registró y no renueva", async ({ page }) => {
  const pedidos = await api(page, {
    "POST /cuenta/ingresar/": () => ({ status: 401, body: { detail: "Email o contraseña incorrectos.", codigo: "credenciales_invalidas" } }),
  });
  await ingresar(page);
  await expect(page.getByText("Email o contraseña incorrectos.")).toBeVisible();
  await expect(page.getByText(/¿Recién creaste tu cuenta\? Abrí el enlace que te mandamos para elegir tu contraseña/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Reenviar el correo" })).toHaveAttribute("href", "/mi/reenviar-verificacion");
  await expect(page.getByLabel("Contraseña")).toHaveAttribute("autocomplete", "current-password");
  expect(de(pedidos, "POST /cuenta/renovar/")).toHaveLength(0);
  await expect(page).toHaveURL("/mi/ingresar");
  expect(await page.evaluate(() => sessionStorage.getItem("hen.portal.access"))).toBeNull();
});

test("ingresar con la cuenta validada va a «tu cuenta está lista» y saluda por nombre", async ({ page }) => {
  await api(page, conSesion({ cuenta: VALIDADA }));
  await ingresar(page);
  await expect(page).toHaveURL("/mi/cuenta");
  await expect(page.getByRole("heading", { name: "Hola, Ana María" })).toBeVisible();
  await expect(page.getByText("Tu cuenta está lista")).toBeVisible();
  await expect(page.getByText("34.521.521")).toBeVisible();
  await expect(page.getByText("14/03/1990")).toBeVisible();
  // Entrar a una pantalla que no le corresponde la devuelve a la suya.
  await page.goto("/mi/validar-identidad");
  await expect(page).toHaveURL("/mi/cuenta");
});

test("olvidé mi contraseña y restablecer con el token del enlace", async ({ page }) => {
  const pedidos = await api(page, {
    "POST /cuenta/olvide/": () => ({ status: 202, body: { detail: DETALLE_NEUTRO } }),
    "POST /cuenta/restablecer/": () => ({ body: { detail: "Tu contraseña se cambió." } }),
  });
  await page.goto("/mi/ingresar");
  await page.getByRole("link", { name: "Olvidé mi contraseña" }).click();
  await page.getByLabel("Email").fill("ana@example.com");
  await page.getByRole("button", { name: "Enviar el enlace" }).click();
  await expect(page.getByText(DETALLE_NEUTRO)).toBeVisible();

  await page.goto("/mi/restablecer#token=tok-recupero");
  await expect(page.getByRole("heading", { name: "Nueva contraseña" })).toBeVisible();
  expect(page.url()).not.toContain("tok-recupero");
  await expect(page.getByLabel("Contraseña nueva")).toHaveAttribute("autocomplete", "new-password");
  await page.getByLabel("Contraseña nueva").fill("otra-clave-larga");
  await page.getByLabel("Repetí la contraseña").fill("otra-clave-larga");
  await page.getByRole("button", { name: "Guardar contraseña" }).click();
  await expect(page.getByRole("heading", { name: "Listo, cambiaste tu contraseña" })).toBeVisible();
  expect(de(pedidos, "POST /cuenta/restablecer/")[0].body).toEqual({ token: "tok-recupero", password: "otra-clave-larga" });
});

test("restablecer con un enlace inválido ofrece pedir otro", async ({ page }) => {
  await api(page, { "POST /cuenta/restablecer/": () => ({ status: 400, body: { detail: "El enlace no es válido.", codigo: "enlace_invalido" } }) });
  await page.goto("/mi/restablecer#token=usado");
  await page.getByLabel("Contraseña nueva").fill("otra-clave-larga");
  await page.getByLabel("Repetí la contraseña").fill("otra-clave-larga");
  await page.getByRole("button", { name: "Guardar contraseña" }).click();
  await expect(page.getByRole("heading", { name: "El enlace ya no sirve" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Pedir un enlace nuevo" })).toHaveAttribute("href", "/mi/olvide");
});

async function completarIdentidad(page) {
  await page.getByLabel("Número de documento").fill("34521521");
  await page.getByText("Femenino").click();
  await page.getByLabel("Número de trámite").fill("00123456789");
}

test("validar identidad: muestra «validando…» y llega a la cuenta lista", async ({ page }) => {
  const estado = { cuenta: CUENTA };
  const pedidos = await api(page, conSesion(estado, {
    "POST /cuenta/validar-identidad/": () => { estado.cuenta = VALIDADA; return { body: VALIDADA, demora: 600 }; },
  }));
  await ingresar(page);
  await expect(page).toHaveURL("/mi/validar-identidad");
  await expect(page.getByLabel("Número de documento")).toHaveAttribute("inputmode", "numeric");
  // El nombre y el apellido salen de RENAPER: el formulario no los pide.
  await expect(page.getByLabel("Nombre", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Apellido")).toHaveCount(0);
  await expect(page.getByLabel("Número de trámite")).toHaveAttribute("inputmode", "numeric");
  await expect(page.getByText("Te quedan 3 intentos para validar.")).toBeVisible();
  await page.getByText("¿Dónde encuentro el número de trámite?").click();
  await expect(page.getByText(/En el DNI tarjeta está en el frente/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Validar identidad" })).toBeDisabled();
  await completarIdentidad(page);
  await expect(page.getByLabel("Número de documento")).toHaveValue("34.521.521");
  await page.getByRole("button", { name: "Validar identidad" }).click();
  await expect(page.getByText("Validando tu identidad con RENAPER…")).toBeVisible();
  await expect(page).toHaveURL("/mi/cuenta");
  await expect(page.getByRole("heading", { name: "Hola, Ana" })).toBeVisible();
  const cuerpo = de(pedidos, "POST /cuenta/validar-identidad/")[0].body;
  expect(cuerpo).toEqual({ documento: "34521521", sexo: "F", numero_tramite: "00123456789" });
  expect(cuerpo).not.toHaveProperty("nombre");
  expect(cuerpo).not.toHaveProperty("apellido");
});

test("validar identidad: los datos no coinciden, quedan intentos y se puede revisar", async ({ page }) => {
  const estado = { cuenta: CUENTA };
  await api(page, conSesion(estado, {
    "POST /cuenta/validar-identidad/": () => {
      estado.cuenta = { ...CUENTA, intentos_restantes: 2 };
      return { status: 422, body: { codigo: "no_coincide", detail: "Los datos no coinciden.", intentos_restantes: 2 } };
    },
  }));
  await ingresar(page);
  await completarIdentidad(page);
  await page.getByRole("button", { name: "Validar identidad" }).click();
  await expect(page.getByRole("heading", { name: "No se pudo validar" })).toBeVisible();
  await expect(page.getByText("Te quedan 2 intentos.")).toBeVisible();
  await page.getByRole("button", { name: "Revisar los datos" }).click();
  // Vuelve al formulario con lo que había escrito.
  await expect(page.getByLabel("Número de trámite")).toHaveValue("00123456789");
  await expect(page.getByText("Te quedan 2 intentos para validar.")).toBeVisible();
});

test("validar identidad: bloqueada dice hasta cuándo y no deja reintentar", async ({ page }) => {
  const hasta = "2026-10-06T18:30:00-03:00";
  const estado = { cuenta: CUENTA };
  await api(page, conSesion(estado, {
    "POST /cuenta/validar-identidad/": () => {
      estado.cuenta = { ...CUENTA, intentos_restantes: 0, validacion_bloqueada_hasta: hasta };
      return { status: 423, body: { codigo: "validacion_bloqueada", detail: "Superaste los intentos.", bloqueada_hasta: hasta } };
    },
  }));
  await page.clock.install({ time: new Date("2026-10-06T10:00:00-03:00") });
  await ingresar(page);
  await completarIdentidad(page);
  await page.getByRole("button", { name: "Validar identidad" }).click();
  await expect(page.getByRole("heading", { name: "Superaste los intentos" })).toBeVisible();
  await expect(page.getByText("06/10/2026 · 18:30")).toBeVisible();
  await expect(page.getByRole("button", { name: "Revisar los datos" })).toHaveCount(0);
  // Al volver a entrar, el bloqueo sale de la cuenta.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Superaste los intentos" })).toBeVisible();
});

test("validar identidad: RENAPER no responde, no cuenta como intento y se puede reintentar", async ({ page }) => {
  let llamadas = 0;
  const estado = { cuenta: CUENTA };
  await api(page, conSesion(estado, {
    "POST /cuenta/validar-identidad/": () => {
      llamadas += 1;
      if (llamadas === 1) return { status: 503, body: { codigo: "servicio_no_disponible", detail: "RENAPER no respondió." } };
      estado.cuenta = VALIDADA;
      return { body: VALIDADA };
    },
  }));
  await ingresar(page);
  await completarIdentidad(page);
  await page.getByRole("button", { name: "Validar identidad" }).click();
  await expect(page.getByRole("heading", { name: "No pudimos consultar a RENAPER" })).toBeVisible();
  await expect(page.getByText(/No cuenta como intento/)).toBeVisible();
  await page.getByRole("button", { name: "Reintentar" }).click();
  await expect(page).toHaveURL("/mi/cuenta");
  expect(llamadas).toBe(2);
});

test("validar identidad: documento en uso en otra cuenta", async ({ page }) => {
  await api(page, conSesion({ cuenta: CUENTA }, {
    "POST /cuenta/validar-identidad/": () => ({ status: 409, body: { codigo: "documento_en_uso", detail: "Ese documento ya está validado en otra cuenta." } }),
  }));
  await ingresar(page);
  await completarIdentidad(page);
  await page.getByRole("button", { name: "Validar identidad" }).click();
  await expect(page.getByRole("heading", { name: "Ese DNI ya tiene una cuenta" })).toBeVisible();
});

test("validar identidad: otro intento en curso responde 429 y se avisa en el formulario", async ({ page }) => {
  await api(page, conSesion({ cuenta: CUENTA }, {
    "POST /cuenta/validar-identidad/": () => ({ status: 429, body: { codigo: "validacion_en_curso", detail: "Ya estamos validando tu identidad. Esperá unos segundos." } }),
  }));
  await ingresar(page);
  await completarIdentidad(page);
  await page.getByRole("button", { name: "Validar identidad" }).click();
  await expect(page.getByText("Ya estamos validando tu identidad. Esperá unos segundos y volvé a intentar.")).toBeVisible();
  await expect(page.getByText("Hiciste demasiados intentos. Probá de nuevo en unos minutos.")).toHaveCount(0);
  await expect(page.getByLabel("Número de trámite")).toHaveValue("00123456789");
});

test("429: demasiados intentos", async ({ page }) => {
  await api(page, { "POST /cuenta/ingresar/": () => ({ status: 429, body: { detail: "Request was throttled." } }) });
  await ingresar(page);
  await expect(page.getByText("Hiciste demasiados intentos. Probá de nuevo en unos minutos.")).toBeVisible();
  await expect(page.getByText("Request was throttled.")).toHaveCount(0);
});

test("el portal nunca manda la sesión del sistema ni la simulación", async ({ page }) => {
  // Una pestaña con sesión de HEN y una simulación activa.
  await page.addInitScript(() => {
    sessionStorage.setItem("salud.access", "jwt-del-sistema");
    sessionStorage.setItem("salud.simulacion", JSON.stringify({ id: "sim-1" }));
  });
  // El sistema la reconoce: así su cliente no descarta la sesión por un 401.
  const pedidos = await api(page, conSesion({ cuenta: VALIDADA }), { sistema: () => ({ status: 200, body: { id: 1, email: "medica@hen.local" } }) });
  await ingresar(page);
  await expect(page.getByRole("heading", { name: "Hola, Ana" })).toBeVisible();
  // La prueba vale si la sesión del sistema y la simulación estaban activas de verdad.
  expect(pedidos.sistema.some((p) => p.headers.authorization === "Bearer jwt-del-sistema" && p.headers["x-hen-simulacion"] === "sim-1")).toBe(true);
  expect(de(pedidos, "GET /cuenta/").length + de(pedidos, "GET /perfil/").length).toBeGreaterThan(0);
  for (const p of pedidos) {
    expect(p.headers["x-hen-simulacion"], p.clave).toBeUndefined();
    expect(p.headers.authorization || "", p.clave).not.toContain("jwt-del-sistema");
  }
  expect(de(pedidos, "POST /cuenta/ingresar/")[0].headers.authorization).toBeUndefined();
  for (const p of [...de(pedidos, "GET /perfil/"), ...de(pedidos, "GET /cuenta/")]) expect(p.headers.authorization).toBe("Bearer hp_access_1");
  // Y no pisa la sesión del sistema.
  expect(await page.evaluate(() => sessionStorage.getItem("salud.access"))).toBe("jwt-del-sistema");
});

/** Arranca con una sesión del portal ya guardada (solo en la primera carga). */
async function sesionGuardada(page, access, refresh) {
  await page.addInitScript(([a, r]) => {
    if (sessionStorage.getItem("prueba.iniciada")) return;
    sessionStorage.setItem("prueba.iniciada", "1");
    sessionStorage.setItem("hen.portal.access", a);
    sessionStorage.setItem("hen.portal.refresh", r);
  }, [access, refresh]);
}

test("401: renueva una sola vez y reintenta con el token nuevo", async ({ page }) => {
  await sesionGuardada(page, "hp_viejo", "hp_r_viejo");
  const vigente = (p) => p.headers.authorization === "Bearer hp_nuevo";
  const pedidos = await api(page, {
    "GET /cuenta/": (p) => (vigente(p) ? { body: VALIDADA } : { status: 401, body: { detail: "Sesión vencida." } }),
    "GET /perfil/": (p) => (vigente(p) ? { body: PERFIL } : { status: 401, body: { detail: "Sesión vencida." } }),
    "POST /cuenta/renovar/": () => ({ body: { access: "hp_nuevo", refresh: "hp_r_nuevo", access_vence: SESION.access_vence, cuenta: VALIDADA } }),
  });
  await page.goto("/mi/cuenta");
  await expect(page.getByRole("heading", { name: "Hola, Ana" })).toBeVisible();
  const renovaciones = de(pedidos, "POST /cuenta/renovar/");
  expect(renovaciones).toHaveLength(1);
  expect(renovaciones[0].body).toEqual({ refresh: "hp_r_viejo" });
  expect(renovaciones[0].headers.authorization).toBeUndefined();
  expect(de(pedidos, "GET /cuenta/").map((p) => p.headers.authorization)).toEqual(["Bearer hp_viejo", "Bearer hp_nuevo"]);
  expect(await page.evaluate(() => [sessionStorage.getItem("hen.portal.access"), sessionStorage.getItem("hen.portal.refresh")])).toEqual(["hp_nuevo", "hp_r_nuevo"]);
});

test("una sola renovación en vuelo: dos 401 a la vez renuevan una vez y reintentan con el token nuevo", async ({ page }) => {
  await sesionGuardada(page, "hp_viejo", "hp_r_viejo");
  const vigente = (p) => p.headers.authorization === "Bearer hp_nuevo";
  const pedidos = await api(page, {
    "GET /cuenta/": (p) => (vigente(p) ? { body: VALIDADA } : { status: 401, body: { detail: "Sesión vencida." } }),
    "GET /perfil/": (p) => (vigente(p) ? { body: PERFIL } : { status: 401, body: { detail: "Sesión vencida." } }),
    // Demora: los dos 401 llegan mientras la renovación sigue en curso.
    "POST /cuenta/renovar/": () => ({ body: { access: "hp_nuevo", refresh: "hp_r_nuevo", access_vence: SESION.access_vence, cuenta: VALIDADA }, demora: 500 }),
  });
  // Una pantalla pública que no pide nada: los dos pedidos salen del cliente a la vez.
  await page.goto("/mi/olvide");
  const respuestas = await page.evaluate(async () => {
    const { portal } = await import("/src/api/portal.js");
    return Promise.all([portal.get("/cuenta/"), portal.get("/perfil/")]);
  });
  expect(respuestas).toEqual([VALIDADA, PERFIL]);
  expect(de(pedidos, "POST /cuenta/renovar/")).toHaveLength(1);
  expect(de(pedidos, "GET /cuenta/").map((p) => p.headers.authorization)).toEqual(["Bearer hp_viejo", "Bearer hp_nuevo"]);
  expect(de(pedidos, "GET /perfil/").map((p) => p.headers.authorization)).toEqual(["Bearer hp_viejo", "Bearer hp_nuevo"]);
});

for (const [status, texto] of [
  [429, "Hiciste demasiados intentos. Probá de nuevo en unos minutos."],
  [503, "El servicio no está disponible en este momento. Reintentá más tarde."],
]) {
  test(`renovar con ${status} no cierra la sesión: conserva los tokens y avisa`, async ({ page }) => {
    await sesionGuardada(page, "hp_viejo", "hp_r_viejo");
    const pedidos = await api(page, {
      "GET /cuenta/": () => ({ status: 401, body: { detail: "Sesión vencida." } }),
      "POST /cuenta/renovar/": () => ({ status, body: { detail: "No ahora." } }),
    });
    await page.goto("/mi/cuenta");
    // Un 5xx se reintenta (TanStack Query) antes de mostrar el error.
    await expect(page.getByText(texto)).toBeVisible({ timeout: 15000 });
    await expect(page).toHaveURL("/mi/cuenta");
    await expect(page.getByRole("button", { name: "Reintentar" })).toBeVisible();
    expect(de(pedidos, "POST /cuenta/renovar/").length).toBeGreaterThan(0);
    expect(await page.evaluate(() => [sessionStorage.getItem("hen.portal.access"), sessionStorage.getItem("hen.portal.refresh")])).toEqual(["hp_viejo", "hp_r_viejo"]);
  });
}

test("401 sin renovación posible: limpia la sesión y vuelve a ingresar", async ({ page }) => {
  await sesionGuardada(page, "hp_viejo", "hp_r_viejo");
  const pedidos = await api(page, {
    "GET /cuenta/": () => ({ status: 401, body: { detail: "Sesión vencida." } }),
    "POST /cuenta/renovar/": () => ({ status: 401, body: { detail: "No sirve." } }),
  });
  await page.goto("/mi/cuenta");
  await expect(page).toHaveURL("/mi/ingresar");
  await expect(page.getByText("Tu sesión venció. Ingresá de nuevo.")).toBeVisible();
  expect(de(pedidos, "POST /cuenta/renovar/")).toHaveLength(1);
  expect(await page.evaluate(() => [sessionStorage.getItem("hen.portal.access"), sessionStorage.getItem("hen.portal.refresh")])).toEqual([null, null]);
});

test("cerrar sesión revoca la sesión y olvida los tokens", async ({ page }) => {
  const pedidos = await api(page, conSesion({ cuenta: VALIDADA }));
  await ingresar(page);
  await expect(page.getByRole("heading", { name: "Hola, Ana" })).toBeVisible();
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL("/mi/ingresar");
  await expect(page.getByText("Cerraste sesión.")).toBeVisible();
  const salidas = de(pedidos, "POST /cuenta/salir/");
  expect(salidas).toHaveLength(1);
  expect(salidas[0].headers.authorization).toBe("Bearer hp_access_1");
  expect(await page.evaluate(() => [sessionStorage.getItem("hen.portal.access"), sessionStorage.getItem("hen.portal.refresh")])).toEqual([null, null]);
  await page.goto("/mi/cuenta");
  await expect(page).toHaveURL("/mi/ingresar");
});

test("cerrar sesión durante una renovación espera el token rotado y sale con él", async ({ page }) => {
  await sesionGuardada(page, "hp_viejo", "hp_r_viejo");
  let vencido = false;
  const valido = (p) => p.headers.authorization === "Bearer hp_nuevo" || (!vencido && p.headers.authorization === "Bearer hp_viejo");
  const pedidos = await api(page, {
    "GET /cuenta/": (p) => (valido(p) ? { body: VALIDADA } : { status: 401, body: { detail: "Sesión vencida." } }),
    "GET /perfil/": (p) => (valido(p) ? { body: PERFIL } : { status: 401, body: { detail: "Sesión vencida." } }),
    // La renovación tarda: «Cerrar sesión» se toca mientras sigue en curso.
    "POST /cuenta/renovar/": () => ({ body: { access: "hp_nuevo", refresh: "hp_r_nuevo", access_vence: SESION.access_vence, cuenta: VALIDADA }, demora: 800 }),
    "POST /cuenta/salir/": () => ({ status: 204 }),
  });
  await page.goto("/mi/cuenta");
  await expect(page.getByRole("heading", { name: "Hola, Ana" })).toBeVisible();
  vencido = true;
  // Un pedido protegido vence y dispara la renovación (mismo cliente que la app).
  await page.evaluate(() => { import("/src/api/portal.js").then(({ portal }) => portal.get("/perfil/").catch(() => null)); });
  await expect.poll(() => de(pedidos, "POST /cuenta/renovar/").length).toBe(1);
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL("/mi/ingresar");
  const salidas = de(pedidos, "POST /cuenta/salir/");
  expect(salidas).toHaveLength(1);
  expect(salidas[0].headers.authorization).toBe("Bearer hp_nuevo");
  expect(await page.evaluate(() => [sessionStorage.getItem("hen.portal.access"), sessionStorage.getItem("hen.portal.refresh")])).toEqual([null, null]);
});
