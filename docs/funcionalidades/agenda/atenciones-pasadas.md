# Registro de atenciones pasadas

`POST /api/turnos/registrar-pasado/` registra una atención que ya ocurrió. Requiere capacidad `turnos` sobre la institución de la agenda y un paciente de esa institución. No reserva cupo, no bloquea horarios, no abre un caso y no sustituye una entrada de historia clínica. La fecha y hora deben ser anteriores al reloj del servidor; no hay límite de antigüedad. Se guarda autor, fecha de registro y motivo.

```json
{
  "agenda": 12,
  "ciudadano": 345,
  "inicio": "2026-09-01T10:30:00-03:00",
  "motivo_registro": "Carga de la atención documentada en soporte físico",
  "clave_operacion": "ef2f7128-d5e0-4d9a-9952-c20a36fbc663"
}
```

La clave UUID v4 identifica el intento. El primer pedido válido devuelve `201`; repetir la misma clave con los mismos datos devuelve `200` y el mismo turno. Reutilizarla con otros datos, o registrar el mismo paciente, agenda y horario con otra clave, devuelve `400`. El cliente conserva la clave cuando reintenta tras un error de red y crea otra si la persona cambia los datos. Las reservas futuras mantienen su endpoint y las reglas de cupos actuales.
