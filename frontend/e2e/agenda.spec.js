import { expect, test } from "@playwright/test";

import { entrar, esperarPantalla } from "./apoyo";

/**
 * Turnos programados.
 *
 * La agenda se opera desde dos lados a la vez: el mostrador, con el paciente
 * enfrente, y el teléfono, con alguien que no sabe ni el día ni el nombre de la
 * profesional. Lo que esta pantalla no puede contestar se paga con un horario
 * que queda tomado por alguien que avisó que no venía.
 */
test.describe("Agenda", () => {
  async function abrir(page) {
    await entrar(page, "medico");
    await page.goto("/agenda");
    await esperarPantalla(page);
    // Por nivel: la barra superior del Shell también se titula «Turnos programados».
    await expect(page.getByRole("heading", { name: "Turnos programados", level: 2 })).toBeVisible();
  }

  const cabecera = (page) => page.locator("section").first();
  const resultados = (page) => page.getByRole("list", { name: "Turnos encontrados" });

  /**
   * Un turno futuro de una agenda DISTINTA a la que abre la pantalla.
   *
   * Es la única forma de probar lo que importa: si se busca alguien de la agenda
   * que ya está en pantalla, el test pasa igual sin buscador.
   */
  async function turnoDeOtraAgenda(page) {
    // Exacto: «Fecha de la agenda» también contiene «agenda» y el localizador
    // engancharía los dos.
    const visible = await page.getByLabel("Agenda", { exact: true }).inputValue();
    return page.evaluate(async (agendaVisible) => {
      const tok = sessionStorage.getItem("cauce.access") ?? localStorage.getItem("cauce.access");
      const d = new Date();
      const hoy = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
      const r = await fetch(`/api/turnos/?desde=${hoy}&ordering=inicio&page_size=100`, {
        headers: { Authorization: `Bearer ${tok}` },
      });
      const datos = await r.json();
      return (datos.results || []).find(
        (t) =>
          String(t.agenda) !== String(agendaVisible) &&
          ["reservado", "confirmado"].includes(t.estado) &&
          t.documento,
      );
    }, visible);
  }

  test("se encuentra el turno de un paciente sin saber la agenda ni el día", async ({ page }) => {
    /*
     * Llama la señora: «tengo turno con la doctora, no puedo ir». No se acuerda
     * del día y no sabe si es Suárez o Gómez.
     *
     * Sin esto hay que ir agenda por agenda y día por día, con otra persona
     * esperando en el mostrador, así que en la práctica se corta el teléfono sin
     * cancelar: el horario queda tomado, no se reasigna a nadie de la lista de
     * espera y el turno termina contado como «no vino». Es un ausentismo falso
     * de alguien que sí avisó, y con ese número se decide cuánto sobreturnear.
     */
    await abrir(page);
    const turno = await turnoDeOtraAgenda(page);
    expect(turno, "la demo no tiene turnos futuros en otra agenda").toBeTruthy();

    await page.getByLabel("Buscar el turno de un paciente").fill(turno.documento);

    const d = new Date(turno.inicio);
    // El separador lo pone el navegador («17/08» o «17-08» según la versión): lo
    // que tiene que estar es el día y el mes, no un formato en particular.
    const ddmm = new RegExp(
      `${String(d.getDate()).padStart(2, "0")}[-/]${String(d.getMonth() + 1).padStart(2, "0")}`,
    );
    // La fecha y la agenda son la mitad de la respuesta: son justo lo que quien
    // llama no sabe, y sin ellas no se le puede confirmar que se está cancelando
    // el turno que tiene en la mano.
    const fila = resultados(page)
      .getByRole("listitem")
      .filter({ hasText: turno.paciente })
      .filter({ hasText: turno.agenda_nombre })
      .filter({ hasText: ddmm });
    await expect(fila).toHaveCount(1);
    await expect(fila.getByRole("button", { name: "Cancelar" })).toBeVisible();

    // «Llegó» abriría el caso de un turno de otro día: lo llaman por altavoz, no
    // aparece nadie y no se cierra nunca. «No vino» le cargaría un ausentismo a
    // quien justamente está llamando para avisar.
    await expect(fila.getByRole("button", { name: "Llegó" })).toHaveCount(0);
    await expect(fila.getByRole("button", { name: "No vino" })).toHaveCount(0);

    // Y en la grilla del día, que es donde el paciente está enfrente, «Llegó»
    // tiene que seguir estando: es la acción que abre el caso y arranca la
    // atención, o sea lo único que hace que el turno valga algo.
    await page.getByLabel("Agenda", { exact: true }).selectOption(String(turno.agenda));
    await page.getByLabel("Fecha de la agenda").fill(turno.inicio.slice(0, 10));
    await expect(page.getByRole("button", { name: "Llegó" }).first()).toBeVisible();
  });

  test("sin coincidencias lo dice en vez de dejar la pantalla igual", async ({ page }) => {
    /*
     * «No tiene turnos» es una respuesta que se le puede dar al teléfono. Una
     * lista vacía sin texto se lee como que la pantalla todavía está buscando, y
     * ahí se vuelve a lo de antes: mirar agenda por agenda por las dudas.
     */
    await abrir(page);
    await page.getByLabel("Buscar el turno de un paciente").fill("zzzzz-no-existe");
    await expect(page.getByText(/Sin turnos de hoy en adelante/)).toBeVisible();
  });

  /*
   * La grilla del día se fuerza en los tres tests que siguen.
   *
   * La demo no tiene ningún sobreturno dado —y darlos desde el test le cambia la
   * agenda a todos los demás—, así que el caso que importa (un horario con los
   * cupos agotados) no se puede mirar contra los datos sembrados. El resumen y el
   * renglón salen los dos de esta respuesta, que es justo lo que se comprueba.
   */
  const unDia = (sobreturnosMax, sobrePorHorario) => {
    const fecha = new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 10);
    const horario = (hora, sobreturnos, ocupado = true, cupos = 1, titulares = null) => {
      const dados = titulares ?? (ocupado ? 1 : 0);
      const libres = Math.max(0, cupos - dados);
      return {
        inicio: `${fecha}T${hora}:00-03:00`,
        duracion_min: 20,
        cupos,
        libres,
        ocupado: libres === 0,
        turno_id: null,
        paciente: dados > 0 ? "Paciente de prueba" : null,
        estado: dados > 0 ? "reservado" : null,
        titulares: dados,
        sobreturnos,
        sobreturnos_max: sobreturnosMax,
        admite_sobreturno: libres === 0 && sobreturnos < sobreturnosMax,
        bloqueado: false,
        fuera_de_grilla: false,
      };
    };
    return {
      agenda: { id: 1, nombre: "Agenda de prueba", sobreturnos_max: sobreturnosMax },
      fecha,
      horarios: [
        horario("08:00", sobrePorHorario[0]),
        horario("08:20", sobrePorHorario[1]),
        horario("08:40", 0, false),
      ],
    };
  };

  async function conDia(page, cuerpo) {
    await page.route(/\/api\/agendas\/\d+\/dia\//, (r) =>
      r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(cuerpo) }),
    );
  }

  async function abrirConDia(page, cuerpo) {
    await entrar(page, "medico");
    await conDia(page, cuerpo);
    await page.goto("/agenda");
    await esperarPantalla(page);
  }

  test("el resumen del día suma los sobreturnos", async ({ page }) => {
    /*
     * «¿Cuánta gente tiene hoy la doctora?» es el número que se mira para decidir
     * si se acepta uno más. Contando sólo a los titulares, un día con dos
     * horarios llenos y tres sobreturnos se resume «2/3 dados» y quien pregunta
     * se lleva una respuesta que no es la del día que va a atender.
     */
    await abrirConDia(page, unDia(2, [2, 1]));
    await expect(cabecera(page)).toContainText("2/3");
    await expect(cabecera(page)).toContainText("3 sobreturnos");
  });

  test("el horario con los cupos agotados lo dice en vez de quedar vacío", async ({ page }) => {
    /*
     * Frente a «¿me da un sobreturno a las 10?», un renglón sin el «+» y sin
     * texto no distingue «ya se usaron los dos» de «esta agenda no toma
     * sobreturnos»: la respuesta al paciente sale a tanteo, y las dos veces que
     * sale mal terminan igual —o se promete algo que no se puede dar, o se niega
     * un lugar que estaba—.
     */
    await abrirConDia(page, unDia(2, [2, 1]));
    const renglon = page.getByRole("listitem").filter({ hasText: "08:00" }).first();
    await expect(renglon).toContainText("2/2 sobreturnos");
    // Donde todavía entra uno no va el cartelito: ahí la respuesta es el «+».
    const conLugar = page.getByRole("listitem").filter({ hasText: "08:20" }).first();
    await expect(conLugar).not.toContainText("sobreturnos");
  });

  test("un horario de tres puestos dice cuántos lugares quedan y sigue ofreciendo turno", async ({ page }) => {
    /*
     * El vacunatorio y la sala de enfermería atienden a tres personas a las 10.
     * Con un solo cupo por horario, el renglón con un paciente adentro se
     * dibujaba «ocupado» y sin botón: los otros dos lugares existían en la agenda
     * y no había forma de darlos, así que se anotaban en un papel.
     */
    const fecha = new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 10);
    await abrirConDia(page, {
      agenda: { id: 1, nombre: "Vacunatorio", sobreturnos_max: 0 },
      fecha,
      horarios: [{
        inicio: `${fecha}T10:00:00-03:00`,
        duracion_min: 20, cupos: 3, libres: 2, ocupado: false,
        turno_id: null, paciente: "Paciente de prueba", estado: "reservado",
        titulares: 1, sobreturnos: 0, sobreturnos_max: 0,
        admite_sobreturno: false, bloqueado: false, fuera_de_grilla: false,
      }],
    });
    const renglon = page.getByRole("listitem").filter({ hasText: "10:00" }).first();
    await expect(renglon).toContainText("1 de 3 lugares");
    await expect(renglon.getByRole("button", { name: "Dar turno" })).toBeVisible();
  });

  test("la semana se ve de un vistazo, con el bloqueo dibujado encima", async ({ page }) => {
    /*
     * «¿Cómo viene la semana?» se contestaba apretando «Día siguiente» siete
     * veces. Y el bloqueo —vacaciones, un feriado— no tenía ninguna pantalla: la
     * única forma de cerrar una tarde era borrar la franja, que se lleva el
     * horario habitual y deja los turnos dados fuera de la grilla.
     */
    const lunes = "2026-08-17";
    await entrar(page, "medico");
    await page.route(/\/api\/agendas\/\d+\/semana\//, (r) =>
      r.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          agenda: { id: 1, nombre: "Agenda de prueba", sobreturnos_max: 2 },
          desde: lunes,
          dias: [0, 1, 2, 3, 4, 5, 6].map((i) => {
            const f = new Date(`${lunes}T12:00:00`);
            f.setDate(f.getDate() + i);
            const fecha = f.toISOString().slice(0, 10);
            return {
              fecha,
              horarios: i === 1
                ? [{
                    inicio: `${fecha}T09:00:00-03:00`, duracion_min: 20, cupos: 1, libres: 0,
                    ocupado: true, titulares: 1, sobreturnos: 0, sobreturnos_max: 2,
                    admite_sobreturno: true, bloqueado: false, fuera_de_grilla: false,
                  }, {
                    inicio: `${fecha}T09:20:00-03:00`, duracion_min: 20, cupos: 1, libres: 1,
                    ocupado: false, titulares: 0, sobreturnos: 0, sobreturnos_max: 2,
                    admite_sobreturno: false, bloqueado: false, fuera_de_grilla: false,
                  }]
                : [],
            };
          }),
        }),
      }),
    );
    await page.route(/\/api\/bloqueos-agenda\/\?/, (r) =>
      r.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 1,
          results: [{
            id: 9, agenda: 1, motivo: "Congreso",
            desde: `${lunes}T14:00:00-03:00`, hasta: `${lunes}T18:00:00-03:00`,
          }],
        }),
      }),
    );
    await page.goto("/agenda");
    await esperarPantalla(page);
    await page.getByRole("button", { name: "Semana" }).click();

    const semana = page.locator("section").filter({ hasText: "Bloqueos de esta semana" });
    // El resumen del día es lo que se busca de reojo: cuántos dados y cuántos
    // quedan, sin abrir el día.
    await expect(semana).toContainText("1 dados · 1 libres");
    await expect(semana).toContainText("Congreso");
  });

  test("una agenda que no toma sobreturnos lo dice una vez arriba", async ({ page }) => {
    /*
     * Con el máximo en cero el «+» no aparece en ningún renglón, y esa ausencia
     * se lee igual que «hoy ya se llenaron»: el administrativo lo intenta horario
     * por horario antes de darse cuenta de que no existe la opción.
     */
    await abrirConDia(page, unDia(0, [0, 0]));
    await expect(cabecera(page)).toContainText("Esta agenda no toma sobreturnos");
    await expect(page.getByRole("button", { name: /Agregar un sobreturno/ })).toHaveCount(0);
  });
});
