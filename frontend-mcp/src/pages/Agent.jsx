import { useRef, useState } from "react";
import { BASE, api, getToken } from "../api";
import Icon from "../icons";

// Friendly labels and a group for each backend tool.
const TOOL_INFO = {
  list_my_cohorts: ["Listed your cohorts", "cohort"],
  create_cohort: ["Created a cohort", "cohort"],
  reallocate_cohort: ["Re-ran allocation", "cohort"],
  admin_list_cohorts: ["Listed all cohorts", "cohort"],
  admin_get_cohort: ["Fetched a cohort", "cohort"],
  admin_set_status: ["Changed cohort status", "cohort"],
  admin_delete_cohort: ["Deleted a cohort", "cohort"],
  admin_list_trainers: ["Listed trainers", "trainer"],
  admin_override_trainer: ["Assigned a trainer", "trainer"],
  list_notifications: ["Read notifications", "mail"],
  read_mail: ["Read mail", "mail"],
  find_batch_requests: ["Searched mail for batch requests", "mail"],
  reply_to_admin: ["Replied to admin", "mail"],
  admin_send_mail: ["Sent mail", "mail"],
};

const SUGGESTIONS = [
  { group: "cohort", title: "Unassigned cohorts", text: "Show my cohorts that are still unassigned" },
  { group: "trainer", title: "Trainer capacity", text: "List trainers with their workload and availability" },
  { group: "mail", title: "Latest allocation mail", text: "Show the latest allocation notifications" },
  { group: "mail", title: "Batch requests", text: "Find batch requests in my unread mail and create them" },
];

// Applies one streamed event to the step list.
function applyEvent(steps, ev) {
  switch (ev.type) {
    case "thinking":
      return [...steps, { kind: "think", id: `t${ev.step}`, label: ev.step === 1 ? "Planning" : `Step ${ev.step}` }];
    case "note":
      return [...steps, { kind: "note", text: ev.text }];
    case "tool_call":
      return [...steps, { kind: "tool", id: ev.id, tool: ev.tool, args: ev.args, status: "running" }];
    case "tool_result":
      return steps.map((s) =>
        s.kind === "tool" && s.id === ev.id
          ? { ...s, status: ev.ok ? (ev.summary?.startsWith("waiting") ? "confirm" : "ok") : "fail", summary: ev.summary }
          : s
      );
    default:
      return steps;
  }
}

function Step({ step }) {
  if (step.kind === "note") return <p className="step-note">{step.text}</p>;
  if (step.kind === "think")
    return <div className="step-think"><span className="pulse" />{step.label}</div>;

  const [label, group] = TOOL_INFO[step.tool] || [step.tool, "cohort"];
  const argsText = Object.keys(step.args || {}).length ? JSON.stringify(step.args) : "";
  return (
    <div className={`step-card ${step.status}`}>
      <span className={`step-badge g-${group}`}>
        <Icon name={group === "mail" ? "mail" : "spark"} size={13} />
      </span>
      <div className="step-body">
        <div className="step-title">
          {label}
          <span className="step-state">
            {step.status === "running" && <span className="spinner" />}
            {step.status === "ok" && "Done"}
            {step.status === "fail" && "Failed"}
            {step.status === "confirm" && "Needs your OK"}
          </span>
        </div>
        {step.summary && <div className="step-summary">{step.summary}</div>}
        {argsText && <code className="step-args">{argsText}</code>}
      </div>
    </div>
  );
}

function Steps({ steps, live }) {
  if (!steps?.length && !live) return null;
  return (
    <div className="steps">
      {steps.map((s, i) => <Step key={s.id || i} step={s} />)}
      {live && <div className="step-think"><span className="pulse" />Working</div>}
    </div>
  );
}

function AgentReply({ text, steps }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  const toolCount = (steps || []).filter((s) => s.kind === "tool").length;
  return (
    <div className="reply-wrap">
      {toolCount > 0 && (
        <details className="steps-toggle">
          <summary>{toolCount} step{toolCount === 1 ? "" : "s"} taken</summary>
          <Steps steps={steps} />
        </details>
      )}
      <div className="reply-card">
        <div className="reply-head">
          <span className="reply-title"><span className="brand-dot sm"><Icon name="spark" size={12} /></span>Agent</span>
          <button className="ghost small-btn" onClick={copy}>{copied ? "Copied" : "Copy"}</button>
        </div>
        <div className="reply-text">{text}</div>
      </div>
    </div>
  );
}

function MailReport({ report }) {
  return (
    <div className="reply-card">
      <div className="reply-head">
        <span className="reply-title"><Icon name="mail" size={14} />Mail workflow</span>
        <span className="pill">{report.length} action{report.length === 1 ? "" : "s"}</span>
      </div>
      <div className="report">
        {report.length === 0 && <p className="muted small">No new batch requests or unassigned cohorts.</p>}
        {report.map((r, i) => (
          <div key={i} className="report-row">
            <span className={`action ${r.action === "failed" ? "fail" : "ok"}`}>{r.action.replace("_", " ")}</span>
            <span className="small">
              {[r.cohortCode, r.status, r.outcome, r.error].filter(Boolean).join(" · ")}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Agent({ user }) {
  const canUse = user?.role === "coach" || user?.role === "admin";
  const isCoach = user?.role === "coach";
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [liveSteps, setLiveSteps] = useState([]);
  const [error, setError] = useState("");
  const [mailReport, setMailReport] = useState(null);
  const threadRef = useRef(null);

  function scroll() {
    requestAnimationFrame(() => threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" }));
  }

  async function send(text) {
    const content = text.trim();
    if (!content || busy || !canUse) return;
    const next = [...messages, { role: "user", content }];
    setMessages(next);
    setInput("");
    setBusy(true);
    setError("");
    setLiveSteps([]);
    scroll();

    let steps = [];
    let reply = null;
    try {
      const res = await fetch(`${BASE}/api/agent/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ messages: next.map(({ role, content }) => ({ role, content })) }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Request failed (${res.status})`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf("\n")) >= 0) {
          const line = buffer.slice(0, idx).trim();
          buffer = buffer.slice(idx + 1);
          if (!line) continue;
          const ev = JSON.parse(line);
          if (ev.type === "reply") reply = ev.text;
          else if (ev.type === "error") throw new Error(ev.message);
          steps = applyEvent(steps, ev);
          setLiveSteps(steps);
          scroll();
        }
      }
      setMessages([...next, { role: "assistant", content: reply ?? "", steps }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLiveSteps([]);
      setBusy(false);
      scroll();
    }
  }

  async function runMail() {
    if (busy || !isCoach) return;
    setBusy(true);
    setError("");
    setMailReport(null);
    try {
      const data = await api("/api/agent/run-mail", { method: "POST" });
      setMailReport(data.report);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const status = busy ? "Working" : messages.length || mailReport ? "Ready" : "Idle";
  const empty = messages.length === 0 && !mailReport && !busy;

  return (
    <div className="agent">
      <header className="agent-head">
        <div className="agent-title">
          <span className="brand-dot"><Icon name="spark" size={16} /></span>
          <div>
            <h2>Workflow Agent</h2>
            <p className="muted small">Ask in plain words. It calls the right TrainMate endpoints and shows each step.</p>
          </div>
        </div>
        <div className="row">
          <span className={`status status-${status.toLowerCase()}`}><span className="status-dot" />{status}</span>
          {isCoach && (
            <button className="small-btn" disabled={busy} onClick={runMail}>
              <Icon name="mail" size={14} />Mail workflow
            </button>
          )}
          {(messages.length > 0 || mailReport) && (
            <button className="ghost small-btn" disabled={busy} onClick={() => { setMessages([]); setError(""); setMailReport(null); }}>
              New chat
            </button>
          )}
        </div>
      </header>

      {!canUse && <div className="notice">The agent works for the coach and admin accounts. Switch user to use it.</div>}

      <div className="thread" ref={threadRef}>
        {empty && (
          <div className="hero">
            <h3>What should the agent do?</h3>
            <p className="muted small">Pick a starting point or describe your own. Changes that delete, cancel or reassign ask you first.</p>
            <div className="suggest-grid">
              {SUGGESTIONS.map((s) => (
                <button key={s.title} className={`suggest g-${s.group}`} disabled={!canUse} onClick={() => send(s.text)}>
                  <span className="suggest-title">{s.title}</span>
                  <span className="small muted">{s.text}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {mailReport && <div className="msg agent"><MailReport report={mailReport} /></div>}

        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="msg user"><div className="bubble-user">{m.content}</div></div>
          ) : (
            <div key={i} className="msg agent"><AgentReply text={m.content} steps={m.steps} /></div>
          )
        )}

        {busy && (
          <div className="msg agent">
            <div className="live-card">
              <div className="live-head"><span className="pulse" />Working on it</div>
              <Steps steps={liveSteps} live />
            </div>
          </div>
        )}
        {error && <div className="error-card">{error}</div>}
      </div>

      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <textarea
          rows={1}
          disabled={!canUse}
          placeholder={canUse ? "Ask the agent… (Enter to send, Shift+Enter for a new line)" : "Switch to coach or admin to use the agent"}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
        />
        <button className="primary send-btn" disabled={busy || !input.trim() || !canUse} aria-label="Send">
          <Icon name="send" size={16} />
        </button>
      </form>
    </div>
  );
}
