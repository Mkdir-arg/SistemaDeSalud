import assert from "node:assert/strict";
import test from "node:test";

import { duracionMinutos } from "./format.js";

test("duracionMinutos redondea antes de partir en horas y omite el resto en cero", () => {
  const casos = [
    [null, "—"],
    [-3, "—"],
    [17.9, "18 min"],
    [59.6, "1 h"],
    [119.6, "2 h"],
    [126, "2 h 6 min"],
    [44621.5, "30 d 23 h"],
    [2880, "2 d"],
  ];
  for (const [valor, esperado] of casos) assert.equal(duracionMinutos(valor), esperado, `valor ${valor}`);
});
