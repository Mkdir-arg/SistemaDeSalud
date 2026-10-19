# Demo de evaluación para la consultora y OSTEL

## Alcance aprobado

Preparar la demo publicada en https://cauce-web-production.up.railway.app/
para usar los módulos existentes sin configuración inicial. El usuario aprobó
el escenario propio de OSTEL y pidió vínculos con más de una institución.
Prefiere que los datos actuales convivan con la nueva carga.

## Decisión

Carga adicional exclusiva de `ENTORNO=demo`, con tres prestadores ficticios:
sanatorio con internación, centro ambulatorio y centro de diagnóstico. OSTEL
tiene un convenio por institución, precios propios por prestador y un padrón
único. Los límites se comparten por afiliado y prestación del catálogo común,
utilizando las reglas existentes del sistema. No se comparten historias
clínicas completas entre instituciones.

Planes, nombres de prestadores, personas, precios y condiciones son ejemplos;
no representan acuerdos ni condiciones reales de OSTEL.

## Criterios observables

- El evaluador puede cambiar entre OSTEL y los tres prestadores de prueba.
- Hay perfiles acotados de administración, autorizaciones, salud, cobranza y
  auditoría; también personal propio de cada institución.
- Agendas, flujos publicados, formularios, camas y stock están configurados.
- Existen afiliados familiares, legajos, prestaciones realizadas y trabajo
  pendiente para autorizaciones, cobertura, farmacia, traslados y finanzas.
- Un afiliado tiene actividad en dos instituciones; el cupo se comparte y los
  aranceles difieren. Sus fichas institucionales siguen separadas.
- La carga conserva los datos previos. Repetirla no duplica ni restablece
  contraseñas, permisos o trabajo modificado durante la evaluación.
- La guía identifica usuario, navegación, ejemplo y resultado esperado por tarea;
  distingue capacidad existente de futura y de integración externa no probada.

## Implementación y validación

Un comando de carga propio, sin migraciones ni dependencias de producción.
Transacción y bloqueo PostgreSQL; marcador de finalización y detección previa
de colisiones. Reutilizar servicios de negocio para crear atenciones,
autorizaciones, cupos, movimientos de stock y dinero. No ejecutar los seeds
destructivos existentes. No procesar colas globales de otros escenarios.

Verificar rechazo fuera de demo, rollback, convivencia, repetición sin cambios,
relación con tres instituciones y cálculo de cobertura entre prestadores.
La prueba integral exige PostgreSQL aislado autorizado. La carga y publicación
en Railway son un paso posterior a la revisión del resultado concreto.

## Riesgos

- La rama local y la revisión desplegada pueden diferir; verificar antes de publicar.
- Los ejemplos pendientes envejecen y pueden vencer; la guía debe explicarlo.
- Un usuario evaluador concentra roles sólo sobre las organizaciones ficticias.
  Su alcance no representa el perfil de un operador real de OSTEL.
- No prometer emisión fiscal, conciliación bancaria ni integraciones ARCA,
  ANSES, SSSalud o RENAPER reales a partir de datos ficticios.
