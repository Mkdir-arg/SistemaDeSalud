import { fileURLToPath, URL } from "node:url";

import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Destino del proxy hacia Django. En local apunta a 127.0.0.1:8000; dentro de
// Docker Compose se inyecta VITE_PROXY_TARGET=http://backend:8000.
const proxyTarget = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";

// Nombre visible del sistema en el <title> y el favicon de index.html. El resto de
// la app lo lee de src/lib/marca.js, con el mismo valor por defecto. Ver
// docs/NOMBRE-DEL-SISTEMA.md.
function nombreSistema(nombre) {
  const escapar = (t) => t.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="16" fill="#7031C7"/><text x="32" y="34" fill="#fff" font-family="Arial, sans-serif" font-size="36" font-weight="700" text-anchor="middle" dominant-baseline="middle">${escapar(nombre.charAt(0))}</text></svg>`;
  return {
    name: "nombre-sistema",
    // «pre»: Vite decodifica las URL del HTML y `%FAVICON_SISTEMA%` no es válida.
    transformIndexHtml: {
      order: "pre",
      handler: (html) => html
        .replaceAll("%NOMBRE_SISTEMA%", escapar(nombre))
        .replaceAll("%FAVICON_SISTEMA%", `data:image/svg+xml,${encodeURIComponent(svg)}`),
    },
  };
}

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss(), nombreSistema(loadEnv(mode, process.cwd(), "VITE_").VITE_NOMBRE_SISTEMA?.trim() || "PLEXO")],
  // Caché de dependencias pre-empaquetadas. Se puede mover con VITE_CACHE_DIR para
  // que dos servidores que comparten node_modules (worktrees) no choquen al
  // renombrar node_modules/.vite/deps_temp_* (EPERM en Windows).
  cacheDir: process.env.VITE_CACHE_DIR || "node_modules/.vite",
  resolve: {
    // Alias «@» → src/. Lo usan los componentes nuevos (y lo requiere shadcn/ui).
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    host: true, // escucha en 0.0.0.0 para ser accesible desde fuera del contenedor.
    port: 5173,
    // En Docker sobre Windows/Mac el bind mount no propaga eventos inotify;
    // el polling hace que Vite detecte los cambios y recargue (HMR) igual.
    watch: { usePolling: true, interval: 300 },
    proxy: {
      /*
       * Rutas servidas por Django (con DEBUG=true sirve /media, /static y /admin).
       *
       * Van como expresión regular —Vite trata la clave como regex si empieza con
       * `^`— y terminan en `(/|$)` a propósito. Con las claves simples el proxy
       * hace coincidencia por PREFIJO, así que `/admin` se llevaba también
       * `/administracion`, que es una ruta del frontend: la pantalla no cargaba
       * con F5 ni por link directo, el pedido iba a Django y devolvía un 404.
       */
      "^/api(/|$)": proxyTarget,
      "^/media(/|$)": proxyTarget,
      "^/static(/|$)": proxyTarget,
      "^/admin(/|$)": proxyTarget,
    },
  },
}));
