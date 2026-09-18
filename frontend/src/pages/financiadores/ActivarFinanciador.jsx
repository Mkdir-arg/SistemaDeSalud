import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import { errorFinanciador } from "@/api/financiadores";
import { Ayuda, Button, Card, Field, Input } from "@/components/ui";
import { Logo } from "@/components/Logo";

export default function ActivarFinanciador() {
  const [params] = useSearchParams();
  const uid = params.get("uid");
  const token = params.get("token");
  const [password, setPassword] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [completo, setCompleto] = useState(false);
  async function activar(e) {
    e.preventDefault(); setError("");
    if (password !== confirmacion) { setError("Las contraseñas no coinciden."); return; }
    setOcupado(true);
    try { await api.post("/financiadores/activar/", { uid, token, password }); setPassword(""); setConfirmacion(""); setCompleto(true); }
    catch (err) { setError(errorFinanciador(err)); }
    finally { setOcupado(false); }
  }
  return <main className="flex min-h-screen items-center justify-center bg-fondo p-4"><Card className="w-full max-w-[480px] space-y-5 p-6"><div className="flex items-center gap-3"><Logo size={40} /><div><p className="font-bold">I-Core Salud</p><p className="text-sm text-texto-debil">Portal de financiadores</p></div></div><div className="flex items-center gap-2"><h1 className="text-xl font-bold">Activá tu acceso</h1><Ayuda>Elegí tu contraseña. El enlace permite activar el acceso una sola vez.</Ayuda></div>{completo ? <><p role="status">Tu contraseña se guardó. Ya podés iniciar sesión.</p><Link className="font-semibold text-accent hover:underline" to="/login">Ir a iniciar sesión</Link></> : !uid || !token ? <p role="alert">El enlace está incompleto. Solicitá un nuevo enlace al administrador de tu financiador.</p> : <form className="space-y-4" onSubmit={activar}>{error && <p role="alert" className="rounded-md bg-badge-error-bg p-3 text-sm text-badge-error-fg">{error}</p>}<Field label="Nueva contraseña"><Input type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required disabled={ocupado} /></Field><Field label="Confirmar contraseña"><Input type="password" autoComplete="new-password" value={confirmacion} onChange={(e) => setConfirmacion(e.target.value)} minLength={8} required disabled={ocupado} /></Field><Button className="w-full" disabled={ocupado}>{ocupado ? "Activando…" : "Activar acceso"}</Button></form>}</Card></main>;
}
