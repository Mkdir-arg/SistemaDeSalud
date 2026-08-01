import { expect, test } from "@playwright/test";

import { fallosDeContraste } from "./apoyo";

/**
 * La TV de la sala de espera. Es pública (sin login) y es la única pantalla que
 * queda fuera del sistema de temas a propósito: ver el comentario de cabecera de
 * `PantallaLlamados.jsx`.
 *
 * Se la mide igual el contraste: es la pantalla que MÁS lejos se lee —una TV
 * a varios metros— así que es donde menos se puede fallar.
 */
test.describe("Pantalla de llamados", () => {
  /** Toma un nodo con fila y le pide (o genera) su token de pantalla. */
  async function token(request) {
    const auth = await request.post("http://127.0.0.1:8000/api/auth/token/", {
      data: { email: "admin@cauce.local", password: "admin1234" },
    });
    const { access } = await auth.json();
    const nodos = await request.get(
      "http://127.0.0.1:8000/api/nodos/?tipo=atencion&page_size=100",
      { headers: { Authorization: `Bearer ${access}` } },
    );
    const lista = (await nodos.json()).results;
    const sala = lista.find((n) => n.config?.con_fila) || lista[0];
    const r = await request.post(`http://127.0.0.1:8000/api/nodos/${sala.id}/pantalla/`, {
      headers: { Authorization: `Bearer ${access}` },
    });
    return (await r.json()).token;
  }

  test("se ve sin login y muestra el estado de la sala", async ({ page, request }) => {
    const t = await token(request);
    await page.goto(`/pantalla/${t}`);
    // Sin sesión: no debe redirigir al login.
    await expect(page).toHaveURL(new RegExp(`/pantalla/${t}`));
    await expect(page.getByText(/Aguarde a ser llamado|LLAMANDO|URGENTE/).first()).toBeVisible();
  });

  test("el botón del timbre dice qué hace y en qué estado está", async ({ page, request }) => {
    const t = await token(request);
    await page.goto(`/pantalla/${t}`);
    const boton = page.getByRole("button", { name: /timbre/i });
    await expect(boton).toBeVisible();
    await expect(boton).toHaveAttribute("aria-pressed", "false");
    await boton.click();
    await expect(boton).toHaveAttribute("aria-pressed", "true");
  });

  test("sin fallos de contraste AA a distancia de TV", async ({ page, request }) => {
    const t = await token(request);
    // 1920x1080: el tamaño real de una TV de sala.
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`/pantalla/${t}`);
    await page.waitForTimeout(1500);
    const fallos = await fallosDeContraste(page);
    expect(fallos, JSON.stringify(fallos, null, 2)).toEqual([]);
  });
});
