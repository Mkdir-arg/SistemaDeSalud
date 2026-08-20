"""Verificador end-to-end del circuito de demo, por HTTP con auth real por rol."""
import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000"
FALLOS = []
OKS = []


def pedir(metodo, ruta, token=None, cuerpo=None):
    url = BASE + ruta
    data = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(url, data=data, method=metodo)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = r.read().decode()
            return r.status, (json.loads(txt) if txt.strip().startswith(("{", "[")) else {"raw": txt[:200]})
    except urllib.error.HTTPError as e:
        txt = e.read().decode()
        try:
            return e.code, json.loads(txt)
        except Exception:
            return e.code, {"raw": txt[:300]}
    except Exception as e:
        return 0, {"error": str(e)}


def login(email, pwd="demo1234"):
    st, d = pedir("POST", "/api/auth/token/", cuerpo={"email": email, "password": pwd})
    return d.get("access") if st == 200 else None


def chk(nombre, cond, detalle=""):
    if cond:
        OKS.append(nombre)
        print(f"  OK    {nombre}")
    else:
        FALLOS.append((nombre, detalle))
        print(f"  FALLO {nombre}   {detalle}")


def seccion(t):
    print()
    print("=" * 74)
    print(t)
    print("=" * 74)


seccion("1. LOGIN POR ROL")
T = {}
for alias, email, pwd in [
    ("super", "admin@cauce.local", "admin1234"),
    ("adm", "guardia.adm@hospital.gob.ar", "demo1234"),
    ("enf", "guardia.enf@hospital.gob.ar", "demo1234"),
    ("med", "guardia.med@hospital.gob.ar", "demo1234"),
    ("jefe", "guardia.jefe@hospital.gob.ar", "demo1234"),
    ("cardio", "cardio.med@hospital.gob.ar", "demo1234"),
    ("lab", "lab.med@hospital.gob.ar", "demo1234"),
    ("intadm", "int.adm@hospital.gob.ar", "demo1234"),
    ("villamed", "villa.med@hospital.gob.ar", "demo1234"),
]:
    T[alias] = login(email, pwd)
    chk(f"login {alias:9} ({email})", T[alias] is not None)

seccion("2. TABLEROS, METRICAS Y PANTALLAS DE OPERACION")
for nombre, ruta, tok in [
    ("metricas institucion", "/api/instituciones/1/metricas/", T["super"]),
    ("tablero institucion", "/api/instituciones/1/tablero/", T["super"]),
    ("tablero de area", "/api/areas/1/tablero/", T["super"]),
    ("tablero de camas", "/api/camas/tablero/?institucion=1", T["super"]),
    ("tablero de red", "/api/redes/1/tablero/", T["super"]),
    ("camas en red", "/api/redes/1/camas/", T["super"]),
    ("destinos de traslado", "/api/traslados/destinos/?institucion=1", T["super"]),
    ("mis tareas (med)", "/api/mis-tareas/", T["med"]),
    ("resumen notificaciones", "/api/notificaciones/resumen/", T["med"]),
    ("alertas de farmacia", "/api/pedidos-stock/alertas/?institucion=1", T["super"]),
    ("mapa de flujos", "/api/flujos/mapa/?institucion=1", T["super"]),
    ("trazar lote", "/api/movimientos-stock/trazar-lote/?institucion=1", T["super"]),
    ("accesos de paciente", "/api/accesos-clinicos/de-paciente/?institucion=1", T["jefe"]),
    ("esquema OpenAPI", "/api/esquema/", T["super"]),
    ("Swagger UI", "/api/docs/", T["super"]),
]:
    st, d = pedir("GET", ruta, tok)
    chk(nombre, st == 200, f"st={st} {str(d)[:170]}")

seccion("3. CAPACIDADES EFECTIVAS POR ROL")
for alias in ("adm", "enf", "med", "jefe"):
    st, me = pedir("GET", "/api/usuarios/me/", T[alias])
    caps = sorted({c for v in (me.get("capacidades_por_institucion") or {}).values() for c in v})
    roles = me.get("roles_por_institucion") or {}
    chk(f"me/{alias}", st == 200 and bool(caps), f"st={st}")
    print(f"        {roles} -> {caps}")

seccion("4. CIRCUITO DE GUARDIA END-TO-END (motor real)")
st, fl = pedir("GET", "/api/flujos/?institucion=1", T["adm"])
flujos = fl.get("results", [])
print(f"  flujos visibles ({len(flujos)}): {[f.get('titulo') or f.get('nombre') or list(f)[:4] for f in flujos]}")

ingreso, ver_pub = None, None
for f in flujos:
    nom = (f.get("titulo") or f.get("nombre") or "").lower()
    if "ingreso" in nom or "guardia" in nom:
        ingreso = f
        break
chk("existe el flujo de ingreso a guardia", ingreso is not None)
if ingreso:
    for v in ingreso.get("versiones", []):
        if v.get("estado") == "publicada":
            ver_pub = v["id"]
    chk("tiene version publicada", ver_pub is not None, str(ingreso.get("versiones"))[:200])
    st, val = pedir("GET", f"/api/versiones-flujo/{ver_pub}/validar/", T["super"])
    chk("validar version publicada", st == 200 and not val.get("errores"),
        f"st={st} errores={str(val.get('errores'))[:250]}")

st, ci = pedir("GET", "/api/ciudadanos/?institucion=1", T["adm"])
pac = (ci.get("results") or [{}])[0].get("id")
chk("hay pacientes en el padron", pac is not None, f"st={st}")

caso_id = None
if ver_pub and pac:
    st, caso = pedir("POST", "/api/casos/", T["adm"],
                     {"institucion": 1, "version": ver_pub, "ciudadano": pac})
    caso_id = caso.get("id")
    chk("alta de caso", st in (200, 201) and caso_id, f"st={st} {str(caso)[:250]}")

if caso_id:
    st, d = pedir("POST", f"/api/casos/{caso_id}/iniciar/", T["adm"])
    chk("iniciar caso (motor)", st in (200, 201), f"st={st} {str(d)[:250]}")
    st, det = pedir("GET", f"/api/casos/{caso_id}/", T["adm"])
    print(f"        caso #{caso_id}: estado={det.get('estado')} nodo={det.get('nodo_actual')} "
          f"paso={det.get('nodo_actual_nombre') or det.get('paso_actual')} area={det.get('area_actual')}")
    chk("el caso quedo parado en un nodo de trabajo", det.get("nodo_actual") is not None, str(det)[:200])
    st, ev = pedir("GET", f"/api/casos/{caso_id}/eventos/", T["adm"])
    lista = ev if isinstance(ev, list) else ev.get("results", [])
    chk("trazabilidad con eventos", st == 200 and len(lista) > 0, f"st={st} n={len(lista)}")
    st, d = pedir("POST", f"/api/casos/{caso_id}/tomar/", T["adm"])
    chk("tomar caso", st in (200, 201), f"st={st} {str(d)[:200]}")
    st, d = pedir("POST", f"/api/casos/{caso_id}/priorizar/", T["jefe"], {"prioridad": "urgente"})
    chk("priorizar como urgente (jefe)", st in (200, 201), f"st={st} {str(d)[:200]}")

seccion("5. FILA / LLAMADO / BOXES (el corazon de la demo de guardia)")
st, itf = pedir("GET", "/api/items-fila/?institucion=1&atendido=false", T["med"])
pend = itf.get("count", 0)
chk("hay cola de espera con pacientes", pend > 0, f"count={pend}")
print(f"        items de fila pendientes: {pend}")
st, bx = pedir("GET", "/api/boxes/?institucion=1", T["med"])
boxes = bx.get("results", [])
chk("hay boxes configurados", len(boxes) > 0, f"n={len(boxes)}")
libre = next((b for b in boxes if not b.get("ocupado") and not b.get("caso")), None)
if libre:
    st, d = pedir("POST", f"/api/boxes/{libre['id']}/ocupar/", T["med"])
    chk("ocupar box", st in (200, 201), f"st={st} {str(d)[:200]}")
    st, d = pedir("POST", f"/api/boxes/{libre['id']}/liberar/", T["med"])
    chk("liberar box", st in (200, 201), f"st={st} {str(d)[:200]}")

seccion("6. AGENDA Y TURNOS")
st, ag = pedir("GET", "/api/agendas/?institucion=1", T["adm"])
agendas = ag.get("results", [])
chk("hay agendas configuradas", len(agendas) > 0, f"n={len(agendas)}")
if agendas:
    a = agendas[0]["id"]
    for nombre, ruta in [("grilla del dia", f"/api/agendas/{a}/dia/"),
                         ("grilla semanal", f"/api/agendas/{a}/semana/"),
                         ("proximos libres", f"/api/agendas/{a}/proximos-libres/")]:
        st, d = pedir("GET", ruta, T["adm"])
        chk(nombre, st == 200, f"st={st} {str(d)[:170]}")

seccion("7. BLINDAJES DE LA AUDITORIA (deben RECHAZAR)")
if caso_id:
    st, d = pedir("PATCH", f"/api/casos/{caso_id}/", T["adm"], {"estado": "cerrado"})
    chk("H14 PATCH generico de caso bloqueado", st in (400, 403, 405), f"st={st} {str(d)[:150]}")
    st, d = pedir("DELETE", f"/api/casos/{caso_id}/", T["adm"])
    chk("H14 DELETE de caso bloqueado", st in (400, 403, 405), f"st={st}")
st, d = pedir("POST", "/api/valores-campo/", T["adm"], {"caso": caso_id or 1, "campo": 1, "valor": "x"})
chk("H15 POST /valores-campo/ bloqueado", st in (403, 405), f"st={st}")
st, d = pedir("POST", "/api/eventos-caso/", T["adm"], {"caso": caso_id or 1, "titulo": "falso"})
chk("H16 POST /eventos-caso/ bloqueado", st in (403, 405), f"st={st}")
st, d = pedir("POST", "/api/items-fila/", T["adm"], {"caso": caso_id or 1, "nodo": 1})
chk("H17 POST /items-fila/ bloqueado", st in (403, 405), f"st={st}")
st, d = pedir("POST", "/api/instituciones/", T["adm"], {"nombre": "Hospital Pirata", "tipo": "x"})
chk("H9 alta de institucion exige gobierno_plataforma", st in (400, 403), f"st={st} {str(d)[:150]}")
st, d = pedir("POST", "/api/redes/", T["adm"], {"nombre": "Red Pirata", "instituciones": [1, 2]})
chk("H31 ABM de redes reservado a plataforma", st in (400, 403), f"st={st} {str(d)[:150]}")
st, d = pedir("POST", "/api/archivos/", T["adm"], {})
chk("H21 subida sin institucion/archivo rechazada", st in (400, 403), f"st={st} {str(d)[:150]}")
st, d = pedir("GET", "/media/uploads/algo.pdf", T["med"])
chk("H21 /media/uploads/ no sirve archivos clinicos", st in (403, 404), f"st={st}")
st, d = pedir("GET", "/api/casos/?institucion=2", T["adm"])
chk("scope: adm de HC no ve casos de Villa Real", d.get("count") == 0, f"count={d.get('count')}")
st, d = pedir("GET", "/api/casos/?institucion=1", T["villamed"])
chk("scope: medico de Villa Real no ve casos de HC", d.get("count") == 0, f"count={d.get('count')}")
st, d = pedir("GET", "/api/accesos-clinicos/?institucion=1", T["med"])
chk("auditoria no visible para medico asistencial", st in (403, 400), f"st={st}")
st, d = pedir("GET", "/api/accesos-clinicos/?institucion=1", T["jefe"])
chk("auditoria visible para jefe de area", st == 200, f"st={st}")

seccion("8. FHIR")
for nombre, ruta in [("metadata", "/fhir/metadata"), ("Patient", "/fhir/Patient?family=a"),
                     ("Encounter", "/fhir/Encounter"), ("Organization", "/fhir/Organization")]:
    st, d = pedir("GET", ruta, T["med"])
    chk(f"FHIR {nombre}", st == 200, f"st={st} {str(d)[:170]}")
st, d = pedir("GET", "/fhir/Patient?family=a")
chk("FHIR Patient sin token rechaza", st in (401, 403), f"st={st}")
st, d = pedir("GET", "/fhir/Patient/999999999", T["med"])
chk("FHIR id inexistente no da 500", st in (400, 404), f"st={st}")

seccion("RESUMEN")
print(f"OK: {len(OKS)}    FALLOS: {len(FALLOS)}")
if FALLOS:
    print()
    for n, d in FALLOS:
        print(f"  X {n}\n      {d}")
