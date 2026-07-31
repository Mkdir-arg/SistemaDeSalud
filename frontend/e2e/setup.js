/**
 * Chequeo previo a la suite.
 *
 * Falla temprano y con un mensaje claro si falta un servidor o si la demo está
 * vacía. Sin esto, un backend caído se manifiesta como quince tests rojos por
 * «timeout esperando un selector», que no dice nada del problema real.
 */
const BASE = process.env.CAUCE_URL || "http://localhost:5173";
const API = process.env.CAUCE_API || "http://127.0.0.1:8000";

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
    throw new Error("\n\n  No se pudo autenticar como admin@cauce.local.\n  Sembrá la demo:  cd backend && python manage.py seed_volumen --rehacer\n");
  }

  const casos = await fetch(`${API}/api/casos/`, {
    headers: { Authorization: `Bearer ${token.access}` },
  }).then((r) => r.json());

  if (!casos.count || casos.count < 100) {
    throw new Error(
      `\n\n  La demo tiene ${casos.count ?? 0} casos y la suite necesita volumen.\n` +
        "  Sembrala con:  cd backend && python manage.py seed_volumen --rehacer\n",
    );
  }
  console.log(`Demo lista: ${casos.count} casos.`);
}
