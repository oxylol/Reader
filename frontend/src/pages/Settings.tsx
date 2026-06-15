import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../store/auth";

function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const u = ["KB", "MB", "GB", "TB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(1)} ${u[i]}`;
}

export default function Settings() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();

  const { data: prefs } = useQuery({ queryKey: ["prefs"], queryFn: api.prefs });
  const updatePrefs = useMutation({
    mutationFn: api.updatePrefs,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prefs"] }),
  });

  return (
    <>
      <header className="topbar">
        <h1>Settings</h1>
      </header>
      <div className="content">
        <div className="muted">Signed in as {user?.username}</div>

        <div className="section-title">Reader defaults</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Field label="Default mode">
            <div className="seg">
              {["auto", "paged", "webtoon"].map((m) => (
                <button
                  key={m}
                  className={prefs?.reading_mode === m ? "on" : ""}
                  onClick={() => updatePrefs.mutate({ reading_mode: m })}
                >
                  {m}
                </button>
              ))}
            </div>
          </Field>
          <Field label="Fit">
            <div className="seg">
              {["width", "height", "original"].map((f) => (
                <button
                  key={f}
                  className={prefs?.fit === f ? "on" : ""}
                  onClick={() => updatePrefs.mutate({ fit: f })}
                >
                  {f}
                </button>
              ))}
            </div>
          </Field>
          <Field label="Paged direction">
            <div className="seg">
              <button className={!prefs?.rtl ? "on" : ""} onClick={() => updatePrefs.mutate({ rtl: false })}>
                LTR
              </button>
              <button className={prefs?.rtl ? "on" : ""} onClick={() => updatePrefs.mutate({ rtl: true })}>
                RTL
              </button>
            </div>
          </Field>
          <Field label="Theme">
            <div className="seg">
              <button className={prefs?.theme === "dark" ? "on" : ""} onClick={() => updatePrefs.mutate({ theme: "dark" })}>
                Dark
              </button>
              <button className={prefs?.theme === "light" ? "on" : ""} onClick={() => updatePrefs.mutate({ theme: "light" })}>
                Light
              </button>
            </div>
          </Field>
        </div>

        {user?.is_admin && <AdminPanel />}

        <button
          className="btn danger block"
          style={{ marginTop: 24 }}
          onClick={() => {
            logout();
            nav("/login");
          }}
        >
          Log out
        </button>
      </div>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="reader-row" style={{ justifyContent: "space-between" }}>
      <span>{label}</span>
      {children}
    </div>
  );
}

function AdminPanel() {
  const qc = useQueryClient();
  const { data: storage } = useQuery({ queryKey: ["storage"], queryFn: api.storage });
  const { data: jobs } = useQuery({
    queryKey: ["jobs"],
    queryFn: api.jobs,
    refetchInterval: 4000,
  });
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: api.listUsers });

  const prune = useMutation({
    mutationFn: (id: number) => api.pruneSeries(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["storage"] }),
  });

  const [nu, setNu] = useState("");
  const [np, setNp] = useState("");
  const [admin, setAdmin] = useState(false);
  const createUser = useMutation({
    mutationFn: () => api.createUser(nu, np, admin),
    onSuccess: () => {
      setNu("");
      setNp("");
      qc.invalidateQueries({ queryKey: ["users"] });
    },
  });
  const delUser = useMutation({
    mutationFn: (id: number) => api.deleteUser(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  return (
    <>
      <div className="section-title">Storage</div>
      {storage && (
        <>
          <div className="muted" style={{ marginBottom: 8 }}>
            {bytes(storage.total_bytes)} across {storage.series_count} series ·{" "}
            {storage.chapter_count} chapters
          </div>
          {storage.series.map((s) => (
            <div className="list-row" key={s.series_id}>
              <div className="grow">
                <div>{s.title}</div>
                <div className="muted">
                  {bytes(s.size_bytes)} · {s.chapter_count} ch
                </div>
              </div>
              <button
                className="chip exclude"
                onClick={() => prune.mutate(s.series_id)}
              >
                Prune
              </button>
            </div>
          ))}
        </>
      )}

      <div className="section-title">Download jobs</div>
      {jobs?.slice(0, 8).map((j) => (
        <div className="list-row" key={j.id}>
          <div className="grow">
            <div>Series #{j.series_id}</div>
            <div className="muted">{j.state} · {j.message}</div>
          </div>
          {(j.state === "running" || j.state === "queued") && (
            <button className="chip" onClick={() => api.cancelJob(j.id)}>
              Cancel
            </button>
          )}
        </div>
      ))}
      {jobs && jobs.length === 0 && <div className="muted">No jobs yet.</div>}

      <div className="section-title">Users</div>
      {users?.map((u) => (
        <div className="list-row" key={u.id}>
          <div className="grow">
            {u.username} {u.is_admin && <span className="tag">admin</span>}
          </div>
          {u.id !== useAuth.getState().user?.id && (
            <button className="chip exclude" onClick={() => delUser.mutate(u.id)}>
              Delete
            </button>
          )}
        </div>
      ))}
      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
        <input className="input" placeholder="New username" value={nu} onChange={(e) => setNu(e.target.value)} />
        <input className="input" placeholder="Password" type="password" value={np} onChange={(e) => setNp(e.target.value)} />
        <label className="reader-row">
          <input type="checkbox" checked={admin} onChange={(e) => setAdmin(e.target.checked)} /> Admin
        </label>
        <button className="btn" disabled={!nu || !np} onClick={() => createUser.mutate()}>
          Add user
        </button>
      </div>
    </>
  );
}
