"""Los tres endpoints que el verificador llamaba sin sus parametros obligatorios."""
import json
import urllib.error
import urllib.request
import uuid

B = "http://localhost:8000"


def tok(email, pwd="demo1234"):
    r = urllib.request.Request(B + "/api/auth/token/",
                               data=json.dumps({"email": email, "password": pwd}).encode(),
                               method="POST")
    r.add_header("Content-Type", "application/json")
    return json.loads(urllib.request.urlopen(r).read())["access"]


def get(ruta, t):
    r = urllib.request.Request(B + ruta)
    r.add_header("Authorization", "Bearer " + t)
    try:
        with urllib.request.urlopen(r, timeout=40) as resp:
            crudo = resp.read()
            try:
                return resp.status, json.loads(crudo)
            except ValueError:
                return resp.status, {"binario": len(crudo)}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


def post_multipart(ruta, t, campos, archivo):
    """Sube un archivo de verdad: multipart/form-data armado a mano."""
    lim = "----cauce" + uuid.uuid4().hex
    cuerpo = b""
    for k, v in campos.items():
        cuerpo += (f"--{lim}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    nombre, tipo, datos = archivo
    cuerpo += (f"--{lim}\r\nContent-Disposition: form-data; name=\"archivo\"; "
               f"filename=\"{nombre}\"\r\nContent-Type: {tipo}\r\n\r\n").encode()
    cuerpo += datos + b"\r\n" + f"--{lim}--\r\n".encode()
    r = urllib.request.Request(B + ruta, data=cuerpo, method="POST")
    r.add_header("Content-Type", f"multipart/form-data; boundary={lim}")
    r.add_header("Authorization", "Bearer " + t)
    try:
        with urllib.request.urlopen(r, timeout=40) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


sup = tok("admin@cauce.local", "admin1234")
med = tok("guardia.med@hospital.gob.ar")
jefe = tok("guardia.jefe@hospital.gob.ar")
adm = tok("guardia.adm@hospital.gob.ar")

print("1. TRAZAR LOTE (con lote real)")
st, lotes = get("/api/lotes/?institucion=1", sup)
lote = (lotes.get("results") or [{}])[0]
st, d = get(f"/api/movimientos-stock/trazar-lote/?lote={lote.get('id')}", sup)
print(f"   lote #{lote.get('id')} ({lote.get('codigo') or lote.get('numero') or '?'}) -> HTTP {st}")
print(f"   {str(d)[:260]}")

print("\n2. ACCESOS DE UN PACIENTE (con paciente real)")
st, cs = get("/api/ciudadanos/?institucion=1", jefe)
pac = (cs.get("results") or [{}])[0]
st, d = get(f"/api/accesos-clinicos/de-paciente/?ciudadano={pac.get('id')}", jefe)
n = d.get("count") if isinstance(d, dict) else "?"
print(f"   paciente #{pac.get('id')} -> HTTP {st}, accesos registrados: {n}")

print("\n3. SUBIDA DE ARCHIVO CLINICO (multipart real)")
pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
st, d = post_multipart("/api/archivos/", med, {"institucion": "1"}, ("estudio.pdf", "application/pdf", pdf))
print(f"   medico con historia_clinica, PDF valido -> HTTP {st}")
print(f"   {str(d)[:300]}")
if st in (200, 201) and isinstance(d, dict) and d.get("ruta"):
    st2, _ = get("/api/archivos/descargar/" + d["ruta"], med)
    print(f"   descarga por endpoint protegido -> HTTP {st2}")
    st3, _ = get("/api/archivos/descargar/" + d["ruta"], None) if False else (None, None)
    # sin permiso: administrativo no tiene historia_clinica
    st4, _ = get("/api/archivos/descargar/" + d["ruta"], adm)
    print(f"   descarga por administrativo (sin historia_clinica) -> HTTP {st4} (debe ser 403)")

st, d = post_multipart("/api/archivos/", med, {"institucion": "1"},
                       ("virus.exe", "application/x-msdownload", b"MZ\x90\x00"))
print(f"   tipo no permitido (.exe) -> HTTP {st} (debe ser 400)")
st, d = post_multipart("/api/archivos/", adm, {"institucion": "1"},
                       ("estudio.pdf", "application/pdf", pdf))
print(f"   administrativo sin historia_clinica -> HTTP {st} (debe ser 403)")
st, d = post_multipart("/api/archivos/", med, {}, ("estudio.pdf", "application/pdf", pdf))
print(f"   sin institucion -> HTTP {st} (debe ser 400)")
