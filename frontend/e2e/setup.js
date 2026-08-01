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
  // `box=null` son los que ESPERAN. Sin eso también cuenta a los ya llamados a un
  // box, y el número no baja aunque la fila se vacíe: el chequeo daría luz verde
  // justo cuando no queda nadie a quien llamar.
  const cola = await fetch(`${API}/api/items-fila/?atendido=false&box=null&page_size=1`, {
    headers: { Authorization: `Bearer ${token.access}` },
  }).then((r) => r.json());

  // Una siembra fresca deja 7 esperando (los otros que informa el seed ya fueron
  // llamados a un box). Cada corrida completa gasta uno, así que 3 avisa con
  // varias corridas de anticipación sin molestar en el uso normal.
  const EN_COLA_MINIMO = 3;
  if ((cola.count ?? 0) < EN_COLA_MINIMO) {
    throw new Error(
      `\n\n  Quedan ${cola.count ?? 0} pacientes en cola y la suite necesita al menos ${EN_COLA_MINIMO}.\n` +
        "  Es normal después de correr la suite un par de veces: los tests de la fila\n" +
        "  llaman pacientes de verdad y la van vaciando.\n" +
        `  Volvé a sembrar:  ${SEMBRAR}\n`,
    );
  }

  console.log(`Demo lista: ${casos.count} casos, ${cola.count} en cola.`);
}
