import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Card, Field, Input } from "../components/ui";
import { Logo } from "../components/Logo";
import { useAuth } from "../auth/AuthContext";
import { color } from "../theme";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@cauce.local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setCargando(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.status === 401 ? "Email o contraseña incorrectos." : "No se pudo iniciar sesión.");
    } finally {
      setCargando(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: color.canvas,
        padding: 24,
      }}
    >
      <Card style={{ width: 380, padding: 32 }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, marginBottom: 24 }}>
          <Logo size={52} />
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-.5px" }}>Cauce</div>
            <div style={{ fontSize: 13, color: color.slate500 }}>Del diagrama al expediente</div>
          </div>
        </div>

        <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Field label="Email">
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus required />
          </Field>
          <Field label="Contraseña">
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </Field>
          {error && (
            <div style={{ fontSize: 13, color: "#B42318", background: "#FCEBEB", padding: "8px 12px", borderRadius: 8 }}>
              {error}
            </div>
          )}
          <Button type="submit" disabled={cargando} style={{ width: "100%", marginTop: 4 }}>
            {cargando ? "Ingresando…" : "Ingresar"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
