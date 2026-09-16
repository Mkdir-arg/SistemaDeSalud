"""PROTOTIPO DESCARTABLE: cupo de una persona/prestación en un año fijo.

Pregunta: ¿son coherentes reserva, consumo, liberación y carga externa tardía?
Sólo memoria, sin Django ni persistencia. No valida concurrencia ni permisos.
Q01 queda sin decidir: no convierte una reserva afectada por información tardía
en una promesa de cobertura inventada. No es el motor productivo de Cauce.

Desde la raíz: python backend/apps/finanzas/prototipo_cupo_cobertura.py --demo
Sin --demo inicia una consola interactiva. No calcula importes ni facturación.
Resultados, límites y decisión humana pendiente: ver
docs/plans/financiadores/validacion-preparacion.md.
"""

import argparse
import json
import sys


class CupoDemo:
    def __init__(self, usados_a=4):
        self.limites = {"A": 6, "B": 10}
        self.consumos = [{"financiador": "A", "origen": "previo", "cantidad": usados_a}]
        self.reservas = {}

    def balance(self, financiador):
        usados = sum(c["cantidad"] for c in self.consumos if c["financiador"] == financiador)
        reservados = sum(r["cantidad"] for r in self.reservas.values()
                         if r["financiador"] == financiador and r["estado"] == "reservada")
        limite = self.limites[financiador]
        return {"limite": limite, "consumidos": usados, "reservados": reservados,
                "disponibles": max(0, limite - usados - reservados),
                "exceso_con_reservas": max(0, usados + reservados - limite)}

    def estado(self):
        return {"alcance": "Una persona, radiografía, año 2026; datos ficticios",
                "cupos": {f: self.balance(f) for f in self.limites},
                "reservas": self.reservas, "consumos": self.consumos}

    def reservar(self, financiador, hospital):
        if self.balance(financiador)["disponibles"] < 1:
            return "Sin disponibilidad para otra reserva. Estado comercial pendiente de Q01/Q05."
        clave = f"R{len(self.reservas) + 1}"
        self.reservas[clave] = {"financiador": financiador, "hospital": hospital,
                                "cantidad": 1, "estado": "reservada", "antigua": False}
        return f"Reservada {clave}."

    def realizar(self, clave):
        reserva = self.reservas[clave]
        if reserva["estado"] == "consumida":
            return "Realización ya registrada; este reintento no agrega consumo."
        if reserva["estado"] != "reservada":
            return "Conflicto: la reserva ya fue liberada. Registrar evidencia tardía requiere resolución."
        if self.balance(reserva["financiador"])["exceso_con_reservas"]:
            return "Q01 PENDIENTE: consumo externo o cambio de límite afecta una reserva abierta."
        self.consumos.append({"financiador": reserva["financiador"], "origen": clave,
                              "cantidad": reserva["cantidad"]})
        reserva["estado"] = "consumida"
        return f"{clave} convertida en consumo."

    def liberar(self, clave, confirma_no_realizacion=False):
        reserva = self.reservas[clave]
        if reserva["estado"] == "consumida":
            return "Conflicto: una reserva consumida no se libera como no realizada."
        if reserva["estado"] == "liberada":
            return "Reserva ya liberada; este reintento no modifica el cupo."
        if not confirma_no_realizacion:
            return "Falta confirmar que la prestación no se realizó."
        reserva["estado"] = "liberada"
        return f"{clave} liberada con confirmación explícita de no realización."

    def marcar_antigua(self, clave):
        self.reservas[clave]["antigua"] = True
        return "Marcada para revisión; el tiempo no libera su cupo."

    def externo(self, financiador, cantidad):
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser positiva.")
        self.consumos.append({"financiador": financiador, "origen": "externo",
                              "cantidad": cantidad})
        return "Consumo externo agregado. Las realizaciones anteriores permanecen registradas."

    def cambiar_limite_plan(self, financiador, limite):
        if limite < 0:
            raise ValueError("El límite no puede ser negativo.")
        self.limites[financiador] = limite
        return "Nuevo límite en el simulador; conserva el acumulado. No modela afiliación del caso."


def mostrar(demo, accion, resultado):
    print(json.dumps({"accion": accion, "resultado": resultado, "estado": demo.estado()},
                     ensure_ascii=False))


def ejecutar_demo():
    demo = CupoDemo(usados_a=5)
    mostrar(demo, "1. Hospital H1 confirma el último uso", demo.reservar("A", "H1"))
    mostrar(demo, "2. Hospital H2 intenta después", demo.reservar("A", "H2"))
    mostrar(demo, "3. Reserva antigua", demo.marcar_antigua("R1"))
    mostrar(demo, "4. Intentar liberar sin confirmar", demo.liberar("R1"))
    mostrar(demo, "5. Confirmar no realización y liberar", demo.liberar("R1", True))
    mostrar(demo, "6. H2 obtiene el uso liberado", demo.reservar("A", "H2"))
    mostrar(demo, "7. Registrar realización", demo.realizar("R2"))
    mostrar(demo, "8. Repetir realización", demo.realizar("R2"))

    demo = CupoDemo()
    mostrar(demo, "9. Cambio de plan A a límite 10", demo.cambiar_limite_plan("A", 10))
    mostrar(demo, "10. Consultar otro financiador B", "B conserva sus diez usos propios.")
    mostrar(demo, "11. Volver a consultar A", "A conserva cuatro consumos; el cambio no los borra.")

    demo = CupoDemo(usados_a=5)
    mostrar(demo, "12. Confirmar antes de carga externa tardía", demo.reservar("A", "H1"))
    mostrar(demo, "13. Carga externa tardía", demo.externo("A", 1))
    mostrar(demo, "14. Intentar resolver el compromiso afectado", demo.realizar("R1"))

    demo = CupoDemo(usados_a=5)
    demo.reservar("A", "H1")
    mostrar(demo, "15. Realización antes del aviso tardío", demo.realizar("R1"))
    mostrar(demo, "16. Carga tardía después de realizada", demo.externo("A", 1))


def consola():
    demo = CupoDemo()
    mensaje = "Prototipo en memoria. Salir descarta todos los cambios."
    while True:
        print("\033[2J\033[H", end="")
        print("PROTOTIPO DE CUPO — NO ES EL SISTEMA PRODUCTIVO")
        print(json.dumps(demo.estado(), ensure_ascii=False, indent=2))
        print("\n" + mensaje)
        print("reservar A H1 | realizar R1 | antiguo R1 | liberar R1 si")
        print("externo A 1 | limite A 10 | reiniciar | salir")
        try:
            partes = input("> ").split()
            if not partes:
                continue
            accion = partes[0]
            if accion == "salir":
                return
            if accion == "reservar":
                mensaje = demo.reservar(partes[1], partes[2])
            elif accion == "realizar":
                mensaje = demo.realizar(partes[1])
            elif accion == "antiguo":
                mensaje = demo.marcar_antigua(partes[1])
            elif accion == "liberar":
                mensaje = demo.liberar(partes[1], len(partes) > 2 and partes[2] == "si")
            elif accion == "externo":
                mensaje = demo.externo(partes[1], int(partes[2]))
            elif accion == "limite":
                mensaje = demo.cambiar_limite_plan(partes[1], int(partes[2]))
            elif accion == "reiniciar":
                demo, mensaje = CupoDemo(), "Estado reiniciado."
            else:
                mensaje = "Elegí uno de los comandos mostrados."
        except (KeyError, ValueError, IndexError) as error:
            mensaje = f"Revisá el comando: {error}"
        except (EOFError, KeyboardInterrupt):
            return


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Recorrido reproducible sin interacción")
    argumentos = parser.parse_args()
    ejecutar_demo() if argumentos.demo else consola()
