import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import Icon from "../icons";

// Backend sends UTC ISO strings; always display in India time.
function formatDate(iso) {
  return new Date(iso).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }) + " IST";
}

function Avatar({ name }) {
  return <span className="avatar">{name.charAt(0)}</span>;
}

function Compose({ onSent, onCancel }) {
  const [recipients, setRecipients] = useState([]);
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/mail/recipients").then((list) => {
      const coaches = list.filter((u) => u.role === "coach");
      const options = coaches.length ? coaches : list;
      setRecipients(options);
      setTo((options[0] || {}).username || "");
    });
  }, []);

  async function send(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onSent(await api("/api/mail", { method: "POST", body: { to_username: to, subject, body } }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="compose" onSubmit={send}>
      <div className="reader-head">
        <h2>New message</h2>
        <span className="small muted">Internal mail</span>
      </div>
      <label>
        <span className="small muted">To</span>
        <select value={to} onChange={(e) => setTo(e.target.value)}>
          {recipients.map((u) => (
            <option key={u.username} value={u.username}>{u.name} · {u.role}</option>
          ))}
        </select>
      </label>
      <label>
        <span className="small muted">Subject</span>
        <input placeholder="e.g. Batch schedule update" maxLength={150} value={subject} onChange={(e) => setSubject(e.target.value)} />
      </label>
      <label>
        <span className="small muted">Message</span>
        <textarea placeholder="Write your message…" rows={10} maxLength={5000} value={body} onChange={(e) => setBody(e.target.value)} />
      </label>
      <div className="row end">
        {error && <p className="error grow">{error}</p>}
        <button type="button" className="ghost" onClick={onCancel}>Discard</button>
        <button className="primary" disabled={busy || !to || !subject.trim() || !body.trim()}>
          <Icon name="send" size={15} />{busy ? "Sending…" : "Send"}
        </button>
      </div>
    </form>
  );
}

export default function Mail({ user, onUnreadChange }) {
  const isAdmin = user.role === "admin";
  const [folder, setFolder] = useState("inbox");
  const [messages, setMessages] = useState([]);
  const [selected, setSelected] = useState(null);
  const [composing, setComposing] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setMessages(await api(`/api/mail/${folder}`));
      if (folder === "inbox") onUnreadChange?.();
    } finally {
      setLoading(false);
    }
  }, [folder, onUnreadChange]);

  useEffect(() => {
    load();
  }, [load]);

  function switchFolder(next) {
    setSelected(null);
    setComposing(false);
    setFolder(next);
  }

  async function open(item) {
    setComposing(false);
    const full = await api(`/api/mail/${item.id}`);
    setSelected(full);
    setMessages((list) => list.map((m) => (m.id === full.id ? { ...m, is_read: true } : m)));
    onUnreadChange?.();
  }

  function handleSent(sent) {
    setComposing(false);
    setFolder("sent");
    setSelected(sent);
  }

  return (
    <div className="mail">
      <aside className="mail-list">
        <div className="row between">
          <div className="tabs">
            <button className={folder === "inbox" ? "tab active" : "tab"} onClick={() => switchFolder("inbox")}>
              <Icon name="inbox" size={15} />Inbox
            </button>
            <button className={folder === "sent" ? "tab active" : "tab"} onClick={() => switchFolder("sent")}>
              <Icon name="sent" size={15} />Sent
            </button>
          </div>
          {isAdmin && (
            <button className="primary small-btn" onClick={() => { setComposing(true); setSelected(null); }}>
              <Icon name="pen" size={14} />Compose
            </button>
          )}
        </div>

        {loading && <p className="muted small empty">Loading…</p>}
        {!loading && messages.length === 0 && (
          <div className="empty muted">
            <Icon name="inbox" size={28} />
            <p className="small">No messages in {folder} yet.</p>
          </div>
        )}

        <ul>
          {messages.map((m) => {
            const other = folder === "inbox" ? m.from_name : m.to_name;
            const unread = !m.is_read && folder === "inbox";
            return (
              <li key={m.id}>
                <button className={`mail-item ${selected?.id === m.id ? "selected" : ""} ${unread ? "unread" : ""}`} onClick={() => open(m)}>
                  <div className="row between grow-row">
                    <span className="row small">
                      <Avatar name={other} />
                      <span className="muted">{folder === "inbox" ? "From" : "To"} {other}</span>
                    </span>
                    {unread && <span className="dot" />}
                  </div>
                  <strong>{m.subject}</strong>
                  <span className="preview">{m.body}</span>
                  <span className="small muted">{formatDate(m.created_at)}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </aside>

      <section className="mail-reader">
        {composing && isAdmin && <Compose onSent={handleSent} onCancel={() => setComposing(false)} />}

        {!composing && selected && (
          <article className="message">
            <div className="reader-head">
              <h2>{selected.subject}</h2>
            </div>
            <div className="meta row">
              <Avatar name={selected.from_name} />
              <div>
                <strong>{selected.from_name}</strong>
                <div className="small muted">to {selected.to_name} · {formatDate(selected.created_at)}</div>
              </div>
            </div>
            <div className="body">{selected.body}</div>
          </article>
        )}

        {!composing && !selected && (
          <div className="empty muted reader-empty">
            <Icon name="mail" size={36} />
            <p>Select a message to read it.</p>
          </div>
        )}
      </section>
    </div>
  );
}
