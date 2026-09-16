# Plantillas de muestra para revisar

Archivos de diseño, **sin conexión con Cauce ni datos reales**. El importador de estas planillas todavía no existe en la aplicación.

- [Consumos — obra social A](consumos-obra-social-a-demo.xlsx): consultas y radiografías.
- [Consumos — mutual B](consumos-mutual-b-demo.xlsx): consultas y ecografías.
- [Padrón — obra social A](padron-obra-social-a-demo.xlsx): formato propuesto para altas/actualizaciones sin bajas.

Cada libro contiene instrucciones, una hoja de carga vacía, su referencia personalizada y ejemplos ficticios separados. Número de afiliado y documento son texto y conservan ceros iniciales. Los consumos tienen los cinco datos obligatorios D9/D12 y la referencia externa opcional D13.

Nombre, plan y vigente desde en el padrón siguen propuestos hasta Q03–Q05. Las 200 filas preparadas sólo muestran el formato; no fijan capacidad ni límites productivos. Las listas de Excel ayudan a completar, pero no prueban afiliación, autorización ni cobertura en una fecha.

La plantilla evita fórmulas, macros y enlaces externos. No contiene cálculos que requieran recalcularse. La compatibilidad visual con Excel/LibreOffice debe revisarse antes de adoptar el formato; la comprobación programática verifica estructura, tipos y referencias, no la experiencia de carga de un usuario real.

Regeneración desde la raíz del repositorio, con `openpyxl` disponible en el entorno de artefactos:

```powershell
python docs/plans/financiadores/crear_plantillas_demo.py
```

La dependencia ya estaba instalada en el entorno usado; no se agregó a `backend/requirements.txt`. Para el importador productivo se deberá cerrar Q07, incluyendo protección XML y límites de archivos.
