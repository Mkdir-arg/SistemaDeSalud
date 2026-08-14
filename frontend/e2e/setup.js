/**
 * Chequeo previo a la suite.
 *
 * Falla temprano y con un mensaje claro si falta un servidor o si la demo está
 * vacía. Sin esto, un backend caído se manifiesta como quince tests rojos por
 * «timeout esperando un selector», que no dice nada del problema real.
 */
const BASE = process.env.CAUCE_URL || "http://localhost:5173";
const API = process.env.CAUCE_API || "http://127.0.0.1:8000";

// El comando de siembra cambia según dónde corre el backend, y darlo mal es peor
// que no darlo: se copia, no anda, y hay que averiguarlo igual.
const SEMBRAR = process.env.CAUCE_URL?.includes("8080")
  ? "docker compose exec backend python manage.py seed_volumen --rehacer"
  : "cd backend && python manage.py seed_volumen --rehacer";

async function vivo(url, nombre, comoLevantar) {
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
  } catch (e) {
    throw new Error(
      `\n\n  ${nombre} no responde en ${url} (${e.message}).\n  Levantalo con:  ${comoLevantar}\n`,
    );
  }
}

export default async function globalSetup() {
  await vivo(`${API}/api/health/`, "El backend", "cd backend && python manage.py runserver");
  await vivo(BASE, "El frontend", "cd frontend && npm run dev");

  // La demo tiene que tener volumen: varios tests comprueban paginación y colas.
  const token = await fetch(`${API}/api/auth/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "admin@cauce.local", password: "admin1234" }),
  }).then((r) => (r.ok ? r.json() : null));

  if (!token) {
    throw new Error(`\n\n  No se pudo autenticar como admin@cauce.local.\n  Sembrá la demo:  ${SEMBRAR}\n`);
  }

  const casos = await fetch(`${API}/api/casos/`, {
    headers: { Authorization: `Bearer ${token.access}` },
  }).then((r) => r.json());

  if (!casos.count || casos.count < 100) {
    throw new Error(
      `\n\n  La demo tiene ${casos.count ?? 0} casos y la suite necesita volumen.\n` +
        `  Sembrala con:  ${SEMBRAR}\n`,
    );
  }

  /*
   * La cola también se comprueba, y aparte de los casos.
   *
   * Hay tests que CONSUMEN cola: «llamar al siguiente» saca un paciente de
   * verdad, porque ejercita el motor real. Así que la suite no es idempotente —
   * correrla varias veces seguidas contra la misma base vacía la fila.
   *
   * Sin este chequeo eso se manifiesta como «expect(locator).toBeVisible()
   * failed» en fila.spec.js, que hace pensar en un bug de la pantalla. Con él,
   * dice exactamente qué pasa y cómo arreglarlo.
   */
  const enCola = await colaDelMedico(token.access);

  // Una siembra fresca deja varios esperando en Guardia. Cada corrida completa
  // gasta dos —los dos tests que llaman—, así que 4 avisa con un par de corridas
  // de anticipación sin molestar en el uso normal.
  const EN_COLA_MINIMO = 4;
  if (enCola < EN_COLA_MINIMO) {
    throw new Error(
      `\n\n  Quedan ${enCola} pacientes en la cola del médico y la suite necesita al menos ${EN_COLA_MINIMO}.\n` +
        "  Es normal después de correr la suite un par de veces: los tests de la fila\n" +
        "  llaman pacientes de verdad y la van vaciando.\n" +
        `  Volvé a sembrar:  ${SEMBRAR}\n`,
    );
  }

  console.log(`Demo lista: ${casos.count} casos, ${enCola} en la cola del médico.`);
}

/**
 * Cuántos esperan en las áreas donde el médico de los tests puede llamar.
 *
 * Contaba la cola de TODA la institución, y ahí está el problema: los tests
 * llaman desde el área del médico, no desde cualquiera. Con dieciséis personas
 * esperando en otras áreas y ninguna en Guardia, el chequeo daba luz verde y
 * `fila.spec` fallaba igual —con un «toBeVisible failed» que hace pensar en un
 * bug de la pantalla, que es exactamente lo que este chequeo existe para evitar—.
 *
 * `box=null` son los que ESPERAN. Sin eso también cuenta a los ya llamados a un
 * box, y el número no baja aunque la fila se vacíe.
 */
async function colaDelMedico(access) {
  const cab = { Authorization: `Bearer ${access}` };
  const json = (u) => fetch(`${API}${u}`, { headers: cab }).then((r) => r.json());

  const medico = await fetch(`${API}/api/auth/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "guardia.med@hospital.gob.ar", password: "demo1234" }),
  }).then((r) => (r.ok ? r.json() : null));

  const items = (await json("/api/items-fila/?atendido=false&box=null&page_size=200")).results || [];
  if (!medico) return items.length; // sin el médico del escenario, se cuenta todo

  const yo = await fetch(`${API}/api/usuarios/me/`, {
    headers: { Authorization: `Bearer ${medico.access}` },
  }).then((r) => (r.ok ? r.json() : null));
  if (!yo) return items.length;

  const mias = new Set(
    ((await json(`/api/membresias/?usuario=${yo.id}&activo=true&page_size=50`)).results || [])
      .flatMap((m) => m.areas || []),
  );
  return items.filter((it) => mias.has(it.area)).length;
}
