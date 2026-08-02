import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Destino del proxy hacia Django. En local apunta a 127.0.0.1:8000; dentro de
// Docker Compose se inyecta VITE_PROXY_TARGET=http://backend:8000.
const proxyTarget = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
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
});
