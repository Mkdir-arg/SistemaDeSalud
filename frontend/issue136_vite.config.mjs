import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Sólo fixtures sintéticos y API interceptada. No lee .env ni proxea a Django.
export default defineConfig({
  envDir: false,
  plugins: [react(), tailwindcss(), { name: "issue136-html-ficticio", transformIndexHtml: { order: "pre", handler: (html) => html.replaceAll("%NOMBRE_SISTEMA%", "PLEXO").replaceAll("%FAVICON_SISTEMA%", "/favicon.ico") } }],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  cacheDir: join(tmpdir(), "salud-issue136-vite"),
  server: { host: "127.0.0.1", port: Number(process.env.ISSUE136_UI_PORT || 5196), strictPort: true },
});
