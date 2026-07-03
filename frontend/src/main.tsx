import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  CheckCircle2,
  Database,
  Layers3,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Shield,
  Tag,
} from "lucide-react";
import "./styles.css";

type ClientName = "claude_code" | "hermes";
type MemoryType = "preference" | "fact" | "decision" | "correction";
type Scope = "private" | "shared";

type SearchItem = {
  id: string;
  score: number;
  collection: string;
  payload: {
    text?: string;
    type?: MemoryType;
    importance?: number;
    tags?: string[];
    created_at?: string;
    source?: string;
    scope?: Scope;
    target_id?: string;
  };
};

type HealthResponse = {
  client: ClientName;
  collection: string;
  queue: Record<string, number>;
  checks: Record<string, string>;
};

const memoryTypes: Array<MemoryType | "all"> = ["all", "fact", "preference", "decision", "correction"];
const clients: ClientName[] = ["claude_code", "hermes"];

function apiHeaders(token: string) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

function scoreLabel(score: number) {
  return Number.isFinite(score) ? score.toFixed(4) : "0.0000";
}

function tagList(value: string) {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function App() {
  const [client, setClient] = useState<ClientName>("claude_code");
  const [token, setToken] = useState(() => localStorage.getItem("memory_web_token") || "");
  const [query, setQuery] = useState("");
  const [memoryType, setMemoryType] = useState<MemoryType | "all">("all");
  const [includeShared, setIncludeShared] = useState(true);
  const [items, setItems] = useState<SearchItem[]>([]);
  const [selected, setSelected] = useState<SearchItem | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [draft, setDraft] = useState({
    text: "",
    type: "fact" as MemoryType,
    importance: 3,
    tags: "",
    scope: "private" as Scope,
  });
  const [correctionText, setCorrectionText] = useState("");

  const authEnabled = useMemo(() => token.trim().length > 0, [token]);

  useEffect(() => {
    localStorage.setItem("memory_web_token", token);
  }, [token]);

  async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(path, {
      ...options,
      headers: {
        ...apiHeaders(token),
        ...(options.headers || {}),
      },
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    return response.json() as Promise<T>;
  }

  async function runSearch(event?: FormEvent) {
    event?.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setNotice("");
    try {
      const params = new URLSearchParams({
        q: query.trim(),
        client,
        limit: "12",
        include_shared: String(includeShared),
      });
      if (memoryType !== "all") params.set("memory_type", memoryType);
      const data = await request<{ items: SearchItem[] }>(`/api/search?${params}`);
      setItems(data.items);
      setSelected(data.items[0] || null);
      setNotice(data.items.length ? `找到 ${data.items.length} 条记忆` : "没有匹配结果");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "搜索失败");
    } finally {
      setBusy(false);
    }
  }

  async function loadHealth() {
    setBusy(true);
    setNotice("");
    try {
      const data = await request<HealthResponse>(`/api/health?client=${client}`);
      setHealth(data);
      setNotice("健康检查完成");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "健康检查失败");
    } finally {
      setBusy(false);
    }
  }

  async function createMemory(event: FormEvent) {
    event.preventDefault();
    if (!draft.text.trim()) return;
    setBusy(true);
    setNotice("");
    try {
      await request("/api/memories", {
        method: "POST",
        body: JSON.stringify({
          client,
          text: draft.text.trim(),
          type: draft.type,
          importance: draft.importance,
          tags: tagList(draft.tags),
          scope: draft.scope,
          flush: true,
        }),
      });
      setDraft({ ...draft, text: "" });
      setNotice("已加入队列并尝试写入");
      if (query.trim()) await runSearch();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "写入失败");
    } finally {
      setBusy(false);
    }
  }

  async function createCorrection(event: FormEvent) {
    event.preventDefault();
    if (!selected || !correctionText.trim()) return;
    setBusy(true);
    setNotice("");
    try {
      await request("/api/memories", {
        method: "POST",
        body: JSON.stringify({
          client,
          text: correctionText.trim(),
          type: "correction",
          importance: 5,
          tags: ["correction"],
          scope: "private",
          target_id: String(selected.id),
          flush: true,
        }),
      });
      setCorrectionText("");
      setNotice("修正已写入");
      if (query.trim()) await runSearch();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "修正失败");
    } finally {
      setBusy(false);
    }
  }

  async function flushQueue() {
    setBusy(true);
    setNotice("");
    try {
      const data = await request<{ done: number; failed: number; queue: Record<string, number> }>("/api/flush", {
        method: "POST",
        body: JSON.stringify({ client, limit: 100 }),
      });
      setNotice(`队列处理完成：done=${data.done} failed=${data.failed}`);
      await loadHealth();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "队列处理失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Database size={24} />
          <div>
            <strong>Memory Web</strong>
            <span>Hermes / Claude Code</span>
          </div>
        </div>

        <section className="panel compact">
          <label>客户端</label>
          <div className="segmented">
            {clients.map((item) => (
              <button
                key={item}
                className={client === item ? "active" : ""}
                onClick={() => setClient(item)}
                type="button"
              >
                {item === "claude_code" ? "Claude" : "Hermes"}
              </button>
            ))}
          </div>
        </section>

        <section className="panel compact">
          <label htmlFor="token">访问 Token</label>
          <div className="token-row">
            <Shield size={17} />
            <input
              id="token"
              type="password"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="MEMORY_WEB_TOKEN"
            />
          </div>
          <small>{authEnabled ? "请求会携带 Bearer token" : "未填写 token"}</small>
        </section>

        <section className="panel compact">
          <button className="full icon-button" onClick={loadHealth} disabled={busy} type="button">
            <Activity size={17} />
            健康检查
          </button>
          <button className="full secondary icon-button" onClick={flushQueue} disabled={busy} type="button">
            <RefreshCw size={17} />
            处理队列
          </button>
        </section>

        {notice && <div className="notice">{notice}</div>}
      </aside>

      <section className="workspace">
        <form className="searchbar" onSubmit={runSearch}>
          <Search size={20} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索记忆、部署、偏好或决策" />
          <select value={memoryType} onChange={(event) => setMemoryType(event.target.value as MemoryType | "all")}>
            {memoryTypes.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <label className="check">
            <input type="checkbox" checked={includeShared} onChange={(event) => setIncludeShared(event.target.checked)} />
            Shared
          </label>
          <button className="icon-button" disabled={busy || !query.trim()} type="submit">
            <Search size={17} />
            搜索
          </button>
        </form>

        <div className="grid">
          <section className="results">
            <div className="section-title">
              <Layers3 size={18} />
              <h2>结果</h2>
            </div>
            <div className="result-list">
              {items.map((item) => (
                <button
                  className={`result-item ${selected?.id === item.id ? "selected" : ""}`}
                  key={`${item.collection}-${item.id}`}
                  onClick={() => setSelected(item)}
                  type="button"
                >
                  <span className="meta-line">
                    <b>{item.payload.type || "unknown"}</b>
                    <span>{scoreLabel(item.score)}</span>
                    <span>{item.collection}</span>
                  </span>
                  <span className="text-line">{item.payload.text || "(empty)"}</span>
                  <span className="tag-line">
                    {(item.payload.tags || []).slice(0, 4).map((tag) => (
                      <em key={tag}>{tag}</em>
                    ))}
                  </span>
                </button>
              ))}
              {!items.length && <div className="empty">输入关键词后搜索记忆</div>}
            </div>
          </section>

          <section className="detail">
            <div className="section-title">
              <Settings size={18} />
              <h2>详情</h2>
            </div>
            {selected ? (
              <div className="detail-body">
                <p>{selected.payload.text}</p>
                <dl>
                  <dt>ID</dt>
                  <dd>{selected.id}</dd>
                  <dt>Collection</dt>
                  <dd>{selected.collection}</dd>
                  <dt>Type</dt>
                  <dd>{selected.payload.type}</dd>
                  <dt>Importance</dt>
                  <dd>{selected.payload.importance}</dd>
                  <dt>Created</dt>
                  <dd>{selected.payload.created_at || "unknown"}</dd>
                </dl>
                <form className="correction" onSubmit={createCorrection}>
                  <textarea
                    value={correctionText}
                    onChange={(event) => setCorrectionText(event.target.value)}
                    placeholder="为选中的记忆追加 correction"
                  />
                  <button className="icon-button" disabled={busy || !correctionText.trim()} type="submit">
                    <CheckCircle2 size={17} />
                    写入修正
                  </button>
                </form>
              </div>
            ) : (
              <div className="empty">选择一条结果查看详情</div>
            )}
          </section>
        </div>

        <div className="bottom-grid">
          <form className="panel writer" onSubmit={createMemory}>
            <div className="section-title">
              <Plus size={18} />
              <h2>新增记忆</h2>
            </div>
            <textarea value={draft.text} onChange={(event) => setDraft({ ...draft, text: event.target.value })} placeholder="写入长期有用的信息，不要写 secret 值" />
            <div className="form-row">
              <select value={draft.type} onChange={(event) => setDraft({ ...draft, type: event.target.value as MemoryType })}>
                <option value="fact">fact</option>
                <option value="preference">preference</option>
                <option value="decision">decision</option>
                <option value="correction">correction</option>
              </select>
              <input
                type="number"
                min={1}
                max={5}
                value={draft.importance}
                onChange={(event) => setDraft({ ...draft, importance: Number(event.target.value) })}
              />
              <select value={draft.scope} onChange={(event) => setDraft({ ...draft, scope: event.target.value as Scope })}>
                <option value="private">private</option>
                <option value="shared">shared</option>
              </select>
            </div>
            <div className="tag-input">
              <Tag size={17} />
              <input value={draft.tags} onChange={(event) => setDraft({ ...draft, tags: event.target.value })} placeholder="tags: server,qdrant" />
            </div>
            <button className="icon-button" disabled={busy || !draft.text.trim()} type="submit">
              <Plus size={17} />
              写入
            </button>
          </form>

          <section className="panel health">
            <div className="section-title">
              <Activity size={18} />
              <h2>状态</h2>
            </div>
            {health ? (
              <dl>
                <dt>Client</dt>
                <dd>{health.client}</dd>
                <dt>Collection</dt>
                <dd>{health.collection}</dd>
                <dt>Queue</dt>
                <dd>{JSON.stringify(health.queue)}</dd>
                {Object.entries(health.checks).map(([key, value]) => (
                  <React.Fragment key={key}>
                    <dt>{key}</dt>
                    <dd>{value}</dd>
                  </React.Fragment>
                ))}
              </dl>
            ) : (
              <div className="empty">点击健康检查查看服务状态</div>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
