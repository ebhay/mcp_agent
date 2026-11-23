import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import Icon from "../icons";
import { FIELD_OPTIONS, TEMPLATE_FIELDS, buildFilledTemplate, isCohortTemplate, parseTemplate, validateCohortMail } from "../cohortTemplate";

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

function FormInput({ label, values, onSet, className, ...rest }) {
  const required = TEMPLATE_FIELDS.find((f) => f.label === label)?.required;
  return (
    <label className={className}>
      <span className="small muted">{label}{required && " *"}</span>
      <input {...rest} type={rest.type || "text"} value={values[label] || ""} onChange={(e) => onSet(label, e.target.value)} />
    </label>
  );
}

function FormSelect({ label, values, onSet }) {
  return (
    <label>
      <span className="small muted">{label}</span>
      <select value={values[label] || ""} onChange={(e) => onSet(label, e.target.value)}>
        <option value="">Default</option>
        {FIELD_OPTIONS[label].map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}

function CohortForm({ values, onChange, problems, onApply, onCancel }) {
  const onSet = (label, value) => onChange({ ...values, [label]: value });
  const hasCode = Boolean((values["Cohort Code"] || "").trim());

  return (
    <div className="cohort-form">
      <div className="wide small muted">Fill in the batch details. Fields marked * are required.</div>
      <FormInput label="Cohort Code" values={values} onSet={onSet} maxLength={30} placeholder="e.g. QEA26SD010" />
      <FormInput label="Trainees Count" values={values} onSet={onSet} type="number" min={1} max={500} placeholder="1 to 500" />
      <FormInput label="Required Skill(s)" values={values} onSet={onSet} placeholder="e.g. Java, Spring Boot, MySQL" className="wide" />
      <FormInput label="Start Date" values={values} onSet={onSet} type="date" />
      <FormInput label="End Date" values={values} onSet={onSet} type="date" />
      <FormSelect label="Service Line" values={values} onSet={onSet} />
      <FormSelect label="Stream" values={values} onSet={onSet} />
      <FormSelect label="Industry Vertical" values={values} onSet={onSet} />
      <FormSelect label="Training Location" values={values} onSet={onSet} />

      {problems.length > 0 && hasCode && (
        <ul className="problems wide">
          {problems.map((p) => <li key={p}>{p}</li>)}
        </ul>
      )}

      <div className="row end wide">
        <button type="button" className="ghost" onClick={onCancel}>Cancel</button>
        <button type="button" className="primary" disabled={problems.length > 0} onClick={onApply}>
          Fill message from form
        </button>
      </div>
    </div>
  );
}

function CohortFormatGuide() {
  return (
    <details className="format-guide">
      <summary>How to send a new cohort request</summary>
      <ol className="small">
        <li>Click <strong>New cohort template</strong> and fill in the values after each colon.</li>
        <li>Keep the label names exactly as they are. Leave an optional line empty to use the default.</li>
        <li>Send to a coach. The coach's agent reads unread mail and creates the batch.</li>
        <li>The coach replies with the cohort code and trainer, or with what is missing.</li>
      </ol>
      <table className="guide-table">
        <thead>
          <tr><th>Field</th><th>Required</th><th>Format and allowed values</th></tr>
        </thead>
        <tbody>
          {TEMPLATE_FIELDS.map((f) => (
            <tr key={f.label}>
              <td>{f.label}</td>
              <td>{f.required ? "Yes" : "No"}</td>
              <td>{f.hint}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

function Compose({ onSent, onCancel, isAdmin }) {
  const [recipients, setRecipients] = useState([]);
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // A filled-in cohort template is checked the same way the backend checks it, before sending.
  const values = parseTemplate(body);
  const templateProblems = isCohortTemplate(values) ? validateCohortMail(values) : [];

  const [formOpen, setFormOpen] = useState(false);
  const [formValues, setFormValues] = useState({});
  const formProblems = Object.values(formValues).some((v) => v) ? validateCohortMail(formValues) : [];

  function applyForm() {
    setBody(buildFilledTemplate(formValues));
    if (!subject.trim() || subject.startsWith("New batch request")) {
      setSubject(`New batch request - ${(formValues["Cohort Code"] || "").trim()}`.trimEnd());
    }
    setFormOpen(false);
  }

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
      <div className="row between">
        <span className="small muted">Message</span>
        {isAdmin && (
          <button type="button" className="ghost small-btn" onClick={() => setFormOpen((open) => !open)}>
            <Icon name="spark" size={14} />{formOpen ? "Hide cohort form" : "New cohort form"}
          </button>
        )}
      </div>
      <textarea placeholder="Write your message…" rows={12} maxLength={5000} value={body} onChange={(e) => setBody(e.target.value)} />

      {isAdmin && formOpen && (
        <CohortForm
          values={formValues}
          onChange={setFormValues}
          problems={formProblems}
          onApply={applyForm}
          onCancel={() => setFormOpen(false)}
        />
      )}

      {isAdmin && <CohortFormatGuide />}

      {templateProblems.length > 0 && (
        <ul className="problems">
          {templateProblems.map((p) => <li key={p}>{p}</li>)}
        </ul>
      )}

      <div className="row end">
        {error && <p className="error grow">{error}</p>}
        <button type="button" className="ghost" onClick={onCancel}>Discard</button>
        <button className="primary" disabled={busy || !to || !subject.trim() || !body.trim() || templateProblems.length > 0}>
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
        {composing && isAdmin && <Compose onSent={handleSent} onCancel={() => setComposing(false)} isAdmin={isAdmin} />}

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
