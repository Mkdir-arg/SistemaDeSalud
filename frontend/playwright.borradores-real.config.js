import { defineConfig } from "@playwright/test";
import base from "./playwright.importacion-real.config.js";
export default defineConfig({ ...base, use: { ...base.use, actionTimeout: 15000 }, testMatch: ["borradores-derechos-real.spec.js"] });
