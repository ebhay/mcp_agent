import { useCallback, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";
import Icon from "./icons";
import Mail from "./pages/Mail";
import Agent from "./pages/Agent";
import "./App.css";

const NAV = [
  { id: "mail", label: "Mail", icon: "mail" },
  { id: "agent", label: "Agent", icon: "spark" },
];

export default function App() {
  const [user, setUser] = useState(null);
  const [users, setUsers] = useState([]);
  const [page, setPage] = useState("mail");
  const [unread, setUnread] = useState(0);
  const [bootError, setBootError] = useState("");

  const switchTo = useCallback(async (username) => {
    const data = await api("/api/auth/switch", { method: "POST", body: { username } });
    setToken(data.token);
    setUser(data.user);
    setPage("mail");
  }, []);

  useEffect(() => {
    async function boot() {
      const list = await api("/api/auth/users");
      setUsers(list);
      const existing = getToken() ? await api("/api/auth/me").catch(() => null) : null;
      if (existing) setUser(existing);
      else await switchTo("admin01");
    }
    boot().catch((err) => setBootError(err.message || "Cannot reach the backend"));
  }, [switchTo]);

  const refreshUnread = useCallback(() => {
    api("/api/mail/unread-count").then((d) => setUnread(d.count)).catch(() => {});
  }, []);

  useEffect(() => {
    if (user) refreshUnread();
  }, [user, refreshUnread]);

  if (!user && bootError)
    return (
      <div className="center">
        <div className="stack" style={{ maxWidth: 420, textAlign: "center" }}>
          <h2>Cannot reach the backend</h2>
          <p className="muted small">{bootError}. Start it with <code>uvicorn app.main:app --reload --port 8000</code> in backend, then reload.</p>
        </div>
      </div>
    );
  if (!user) return <div className="center muted">Loading…</div>;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-dot"><Icon name="spark" size={16} /></span>
          TrainMate
        </div>
        <nav>
          {NAV.map((item) => (
            <button key={item.id} className={page === item.id ? "nav active" : "nav"} onClick={() => setPage(item.id)}>
              <span className="nav-label"><Icon name={item.icon} />{item.label}</span>
              {item.id === "mail" && unread > 0 && <span className="badge">{unread}</span>}
            </button>
          ))}
        </nav>
        <div className="me">
          <label className="small muted">
            Switch user
            <select value={user.username} onChange={(e) => switchTo(e.target.value)}>
              {users.map((u) => (
                <option key={u.username} value={u.username}>
                  {u.name} · {u.role}
                </option>
              ))}
            </select>
          </label>
          <div className="me-name">
            <span className="avatar">{user.name.charAt(0)}</span>
            <div>
              <strong>{user.name}</strong>
              <div className="small muted">{user.role}</div>
            </div>
          </div>
        </div>
      </aside>

      <main className="main">
        {page === "mail" && <Mail key={user.username} user={user} onUnreadChange={refreshUnread} />}
        {page === "agent" && <Agent user={user} />}
      </main>
    </div>
  );
}
