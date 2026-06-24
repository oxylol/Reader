import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../store/auth";

export default function Login() {
  const login = useAuth((s) => s.login);
  const user = useAuth((s) => s.user);
  const nav = useNavigate();
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) {
    nav("/", { replace: true });
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await login(username, password);
      nav("/", { replace: true });
    } catch {
      setErr("Invalid username or password");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <h1>InkVault</h1>
        <input
          className="input"
          placeholder="Username"
          value={username}
          autoCapitalize="none"
          autoCorrect="off"
          onChange={(e) => setU(e.target.value)}
        />
        <input
          className="input"
          placeholder="Password"
          type="password"
          value={password}
          onChange={(e) => setP(e.target.value)}
        />
        {err && <div style={{ color: "var(--danger)", fontSize: 13 }}>{err}</div>}
        <button className="btn block" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
