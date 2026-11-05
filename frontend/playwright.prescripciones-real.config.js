import { defineConfig } from "@playwright/test";
import base from "./playwright.importacion-real.config.js";

// Escenario y servidores propios preparados explícitamente; no iniciar importación.
export default defineConfig({ ...base, webServer: undefined, use: { ...base.use, actionTimeout: 15000 }, testMatch: ["prescripciones-autorizacion-real.spec.js"] });
