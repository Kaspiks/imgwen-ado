import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Card } from "../components/Card";
import { ChatReferencePicker } from "../components/ChatReferencePicker";
import { CreateProjectModal } from "../components/CreateProjectModal";
import { MOCKUPS } from "../mockups";
import { API_BASE } from "../lib/api";
import {
  ingestReferenceToLibrary,
  ingestReferenceToLibraryQuietly,
  ingestReferenceUrlsQuietly,
} from "../lib/references";

const API = API_BASE;

type ProjectItem = {
  id: number;
  project_name: string;
  status: string;
  creation_date: string;
  total_edits: number;
};

const STATUS_STYLE: Record<string, string> = {
  active: "bg-emerald-50 text-emerald-700",
  draft: "bg-zinc-100 text-zinc-600",
  archived: "bg-amber-50 text-amber-700",
};

function ProjectPicker() {
  const [, setSearchParams] = useSearchParams();
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    fetch(`${API}/projects`)
      .then((r) => (r.ok ? (r.json() as Promise<{ projects: ProjectItem[] }>) : Promise.reject()))
      .then((d) => setProjects(d.projects))
      .catch(() => setProjects([]))
      .finally(() => setLoading(false));
  }, []);

  const pick = (id: number) => setSearchParams({ projectId: String(id) });

  return (
    <div className="flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center bg-[#f4f4f7] px-4">
      <div className="w-full max-w-lg">
        <h1 className="text-2xl font-bold text-zinc-900">Select a project</h1>
        <p className="mt-1 text-sm text-zinc-500">Pick an existing project or create a new one to start editing.</p>

        <div className="mt-6 flex flex-col gap-3">
          {loading && (
            <p className="py-8 text-center text-sm text-zinc-400">Loading projects…</p>
          )}

          {!loading && projects.length === 0 && (
            <p className="py-8 text-center text-sm text-zinc-400">No projects yet. Create your first one below.</p>
          )}

          {projects.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => pick(p.id)}
              className="flex items-center justify-between rounded-2xl border border-zinc-200 bg-white px-5 py-4 text-left shadow-sm transition hover:border-accent/40 hover:shadow-md"
            >
              <div className="min-w-0">
                <p className="truncate font-semibold text-zinc-900">{p.project_name}</p>
                <p className="mt-0.5 text-xs text-zinc-400">
                  {new Date(p.creation_date).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                  {p.total_edits > 0 && <> · {p.total_edits} edit{p.total_edits !== 1 && "s"}</>}
                </p>
              </div>
              <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${STATUS_STYLE[p.status] ?? "bg-zinc-100 text-zinc-600"}`}>
                {p.status}
              </span>
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="mt-4 w-full rounded-2xl border-2 border-dashed border-zinc-300 bg-white py-4 text-sm font-semibold text-zinc-600 transition hover:border-accent hover:text-accent"
        >
          + Create new project
        </button>
      </div>

      <CreateProjectModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  );
}

type ChatMsg = { id: number; role: string; content: string; reference_urls?: string[] };

type SessionPayload = {
  id: number;
  phase: string;
  base_image_url: string;
  reference_urls: string[];
  messages: ChatMsg[];
  last_edit_result?: {
    edited_image_urls?: string[];
    warnings?: string[];
    plan?: Record<string, unknown>;
  } | null;
};

async function readError(res: Response): Promise<string> {
  try {
    const j = (await res.json()) as { detail?: unknown };
    if (typeof j.detail === "string") return j.detail;
    if (Array.isArray(j.detail)) return JSON.stringify(j.detail);
    return res.statusText;
  } catch {
    return res.statusText;
  }
}

function isBaseImagePayload(s: string): boolean {
  const t = s.trim();
  return t.startsWith("http") || t.startsWith("data:image");
}

function formatUpstreamError(raw: string): string {
  if (raw.includes("QWEN_VISION_MODEL") || raw.includes("MaaS workspace")) {
    return raw;
  }
  if (raw.includes("Model not exist") || raw.includes("InvalidParameter")) {
    return `${raw}\n\nTip: On a dedicated MaaS gateway, set QWEN_VISION_MODEL (and related QWEN_* ids) in .env to the exact deployment names from the Alibaba console — they often differ from public DashScope names like qwen-vl-max.`;
  }
  return raw;
}

/** Public sample image (Alibaba doc CDN) so you can click Start without hunting a URL first. */
const SAMPLE_BASE_IMAGE =
  "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250925/thtclx/input1.png";

export function WorkspacePage() {
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get("projectId");
  const preloadedRef = searchParams.get("ref");

  if (!projectId) return <ProjectPicker />;
  return <WorkspaceEditor projectId={projectId} preloadedRef={preloadedRef} />;
}

function WorkspaceEditor({
  projectId,
  preloadedRef,
}: {
  projectId: string;
  preloadedRef: string | null;
}) {
  const [, setSearchParams] = useSearchParams();
  const [baseImageUrl, setBaseImageUrl] = useState(SAMPLE_BASE_IMAGE);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [phase, setPhase] = useState<string>("");
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [refAUrl, setRefAUrl] = useState("");
  const [refBUrl, setRefBUrl] = useState("");
  const [refAEmbedded, setRefAEmbedded] = useState<string | null>(null);
  const [refBEmbedded, setRefBEmbedded] = useState<string | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editUrls, setEditUrls] = useState<string[]>([]);
  const [requestedRefs, setRequestedRefs] = useState(false);
  const [savedRefUrls, setSavedRefUrls] = useState<string[]>([]);
  const [selectedRefUrls, setSelectedRefUrls] = useState<string[]>([]);
  const [apiStatus, setApiStatus] = useState<"checking" | "ok" | "error">("checking");
  const [libraryMsg, setLibraryMsg] = useState<{ slot: "a" | "b"; text: string } | null>(null);
  const [projectName, setProjectName] = useState<string | null>(null);

  const baseFileRef = useRef<HTMLInputElement>(null);
  const refAFileRef = useRef<HTMLInputElement>(null);
  const refBFileRef = useRef<HTMLInputElement>(null);
  const chatInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/health`)
      .then((r) => {
        if (!cancelled) setApiStatus(r.ok ? "ok" : "error");
      })
      .catch(() => {
        if (!cancelled) setApiStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Fetch the project name so the header shows which project is open.
  useEffect(() => {
    let cancelled = false;
    setProjectName(null);
    fetch(`${API}/projects/${projectId}`)
      .then((r) => (r.ok ? (r.json() as Promise<ProjectItem>) : null))
      .then((p) => {
        if (!cancelled && p) setProjectName(p.project_name);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  // Restore the most recent session for this project on mount.
  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/workflow/edit-flow/sessions?project_id=${projectId}`)
      .then((r) => (r.ok ? (r.json() as Promise<SessionPayload>) : null))
      .then((s) => {
        if (!cancelled && s) {
          setSessionId(s.id);
          setPhase(s.phase);
          setMessages(s.messages);
          setBaseImageUrl(s.base_image_url);
          const r = s.reference_urls || [];
          setSavedRefUrls(r);
          setSelectedRefUrls(r);
          if (r[0]?.startsWith("data:image")) {
            setRefAEmbedded(r[0]);
            setRefAUrl("");
          } else {
            setRefAEmbedded(null);
            setRefAUrl(r[0] ?? "");
          }
          if (r[1]?.startsWith("data:image")) {
            setRefBEmbedded(r[1]);
            setRefBUrl("");
          } else {
            setRefBEmbedded(null);
            setRefBUrl(r[1] ?? "");
          }
          if (s.last_edit_result?.edited_image_urls?.length) {
            setEditUrls(s.last_edit_result.edited_image_urls);
          }
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const uploadImageFile = async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${API}/workflow/edit-flow/upload`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await readError(res));
    const j = (await res.json()) as { url: string };
    return j.url;
  };

  const syncSession = useCallback(async (id: number) => {
    const res = await fetch(`${API}/workflow/edit-flow/sessions/${id}`);
    if (!res.ok) throw new Error(await readError(res));
    const s = (await res.json()) as SessionPayload;
    setPhase(s.phase);
    setMessages(s.messages);
    setBaseImageUrl(s.base_image_url);
    const r = s.reference_urls || [];
    setSavedRefUrls(r);
    setSelectedRefUrls(r);
    if (r[0]?.startsWith("data:image")) {
      setRefAEmbedded(r[0]);
      setRefAUrl("");
    } else {
      setRefAEmbedded(null);
      setRefAUrl(r[0] ?? "");
    }
    if (r[1]?.startsWith("data:image")) {
      setRefBEmbedded(r[1]);
      setRefBUrl("");
    } else {
      setRefBEmbedded(null);
      setRefBUrl(r[1] ?? "");
    }
    if (s.last_edit_result?.edited_image_urls?.length) {
      setEditUrls(s.last_edit_result.edited_image_urls);
    }
  }, []);

  const onPickBaseFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || sessionId !== null) return;
    setError(null);
    setLoading(true);
    try {
      const url = await uploadImageFile(file);
      setBaseImageUrl(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const onPickRefFile = async (slot: "a" | "b", e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError(null);
    setLoading(true);
    try {
      const url = await uploadImageFile(file);
      if (slot === "a") {
        setRefAEmbedded(url);
        setRefAUrl("");
      } else {
        setRefBEmbedded(url);
        setRefBUrl("");
      }
      ingestReferenceToLibraryQuietly(url, ["Uploaded"]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const startSession = async () => {
    setError(null);
    setLoading(true);
    setEditUrls([]);
    setRequestedRefs(false);
    setSavedRefUrls([]);
    setSelectedRefUrls([]);
    try {
      const payload: Record<string, string | number> = {
        base_image_url: baseImageUrl.trim(),
        project_id: Number(projectId),
      };
      if (preloadedRef) {
        let refUrl = preloadedRef;
        if (!refUrl.startsWith("http") && !refUrl.startsWith("data:image")) {
          const blob = await fetch(refUrl).then((r) => r.blob());
          const file = new File([blob], "reference.png", { type: blob.type });
          refUrl = await uploadImageFile(file);
        }
        payload.preloaded_reference_url = refUrl;
      }
      const res = await fetch(`${API}/workflow/edit-flow/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(formatUpstreamError(await readError(res)));
      const s = (await res.json()) as SessionPayload;
      setSessionId(s.id);
      setPhase(s.phase);
      setMessages(s.messages);
      if (s.reference_urls?.length) {
        setSavedRefUrls(s.reference_urls);
        setSelectedRefUrls(s.reference_urls);
        setRefAUrl(s.reference_urls[0]);
      }
      if (preloadedRef) {
        setSearchParams({}, { replace: true });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start session");
    } finally {
      setLoading(false);
    }
  };

  const sendChatMessage = async (text: string) => {
    if (!sessionId || !text.trim()) return;
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${API}/workflow/edit-flow/sessions/${sessionId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text.trim() }),
      });
      if (!res.ok) throw new Error(formatUpstreamError(await readError(res)));
      const body = (await res.json()) as {
        assistant_message: string;
        phase: string;
        requested_references: boolean;
      };
      setPhase(body.phase);
      if (body.requested_references) setRequestedRefs(true);
      await syncSession(sessionId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Chat failed");
    } finally {
      setLoading(false);
    }
  };

  const sendChat = async () => {
    if (!chatInput.trim()) return;
    const text = chatInput.trim();
    setChatInput("");
    await sendChatMessage(text);
  };

  const sendPlannerFeedback = async (agree: boolean) => {
    const msg = agree
      ? "I agree with the planner reasoning and the edit outcome."
      : "I disagree with the planner reasoning or the edit outcome.";
    await sendChatMessage(msg);
    if (!agree) {
      setChatInput("I disagree because: ");
      requestAnimationFrame(() => chatInputRef.current?.focus());
    }
  };

  const chatReferenceUrls = useMemo(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const m of messages) {
      for (const u of m.reference_urls || []) {
        if ((u.startsWith("http") || u.startsWith("data:image")) && !seen.has(u)) {
          seen.add(u);
          out.push(u);
        }
      }
    }
    return out;
  }, [messages]);

  const toggleRefSelection = (url: string) => {
    setSelectedRefUrls((prev) => {
      if (prev.includes(url)) return prev.filter((u) => u !== url);
      if (prev.length >= 2) return prev;
      return [...prev, url];
    });
  };

  const selectionDirty = useMemo(() => {
    if (selectedRefUrls.length !== savedRefUrls.length) return true;
    const saved = new Set(savedRefUrls);
    return selectedRefUrls.some((u) => !saved.has(u));
  }, [selectedRefUrls, savedRefUrls]);

  const applySelectedReferences = async (urls: string[]) => {
    if (!sessionId) return;
    setError(null);
    setLoading(true);
    const normalized = urls.filter((u) => u.startsWith("http") || u.startsWith("data:image")).slice(0, 2);
    try {
      const res = await fetch(`${API}/workflow/edit-flow/sessions/${sessionId}/references`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls: normalized }),
      });
      if (!res.ok) throw new Error(await readError(res));
      await syncSession(sessionId);
      ingestReferenceUrlsQuietly(normalized, ["Session"]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save references");
    } finally {
      setLoading(false);
    }
  };

  const clearSelectedReferences = async () => {
    setSelectedRefUrls([]);
    await applySelectedReferences([]);
  };

  const saveReferences = async () => {
    await applySelectedReferences(
      [refAEmbedded || refAUrl.trim(), refBEmbedded || refBUrl.trim()].filter(
        (u) => u.startsWith("http") || u.startsWith("data:image"),
      ),
    );
  };

  const saveRefToLibrary = async (slot: "a" | "b") => {
    const url = slot === "a" ? refAEmbedded || refAUrl.trim() : refBEmbedded || refBUrl.trim();
    if (!url) return;
    setLibraryMsg(null);
    setLoading(true);
    try {
      const item = await ingestReferenceToLibrary(url, ["Saved"]);
      setLibraryMsg({ slot, text: `Saved to library: "${item.description.slice(0, 80)}"` });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save to library");
    } finally {
      setLoading(false);
    }
  };

  const runEdit = async () => {
    if (!sessionId) return;
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${API}/workflow/edit-flow/sessions/${sessionId}/run-edit`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(formatUpstreamError(await readError(res)));
      const body = (await res.json()) as { edited_image_urls: string[] };
      setEditUrls(body.edited_image_urls || []);
      setPhase("edit_completed");
      await syncSession(sessionId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Edit pipeline failed");
    } finally {
      setLoading(false);
    }
  };

  const previewSrc = baseImageUrl || MOCKUPS.workspace;
  const baseIsEmbedded = baseImageUrl.trim().startsWith("data:image");
  const canStart = isBaseImagePayload(baseImageUrl) && sessionId === null;

  return (
    <div className="grid min-h-[calc(100vh-4rem)] flex-1 grid-cols-1 gap-0 border-zinc-200/80 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:border-l">
      <input
        ref={baseFileRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        className="hidden"
        onChange={(e) => void onPickBaseFile(e)}
      />
      <input
        ref={refAFileRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        className="hidden"
        onChange={(e) => void onPickRefFile("a", e)}
      />
      <input
        ref={refBFileRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        className="hidden"
        onChange={(e) => void onPickRefFile("b", e)}
      />

      <section className="flex flex-col border-b border-zinc-200/80 bg-white lg:border-b-0 lg:border-r">
        <div className="border-b border-zinc-100 px-5 py-4">
          <h1 className="text-lg font-bold text-zinc-900">Edit flow</h1>
          <p className="text-xs text-zinc-500">
            Chat with the reasoning model, add references when asked, then run the image-edit pipeline.
          </p>
          {apiStatus === "checking" ? (
            <p className="mt-2 text-[11px] text-zinc-400">Checking API…</p>
          ) : apiStatus === "ok" ? (
            <p className="mt-2 text-[11px] font-medium text-emerald-700">API reachable at {API}</p>
          ) : (
            <p className="mt-2 text-[11px] font-medium text-red-700">
              Cannot reach {API}/health — run the FastAPI backend. With{" "}
              <code className="rounded bg-red-100 px-1">npm run dev</code> the Vite proxy forwards{" "}
              <code className="rounded bg-red-100 px-1">/api</code>; with Docker open port 3000 after{" "}
              <code className="rounded bg-red-100 px-1">docker compose up</code>.
            </p>
          )}
          {phase ? (
            <p className="mt-1 text-[11px] font-medium uppercase tracking-wide text-zinc-400">
              Phase: {phase.replace(/_/g, " ")}
            </p>
          ) : null}
        </div>

        <div className="border-b border-zinc-100 px-5 py-3">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
            Base image
          </label>
          <p className="mb-2 text-[11px] text-zinc-400">
            Paste an HTTPS URL, or upload a file (sent to the model as embedded data — no public hosting
            needed). Max 2MB, JPEG/PNG/WebP/GIF.
          </p>
          <div className="mb-2 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={loading || sessionId !== null}
              onClick={() => baseFileRef.current?.click()}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs font-semibold text-zinc-800 hover:bg-zinc-50 disabled:opacity-40"
            >
              Upload file…
            </button>
            {baseIsEmbedded ? (
              <button
                type="button"
                disabled={loading || sessionId !== null}
                onClick={() => setBaseImageUrl(SAMPLE_BASE_IMAGE)}
                className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs font-semibold text-zinc-600 hover:bg-zinc-50 disabled:opacity-40"
              >
                Use sample URL instead
              </button>
            ) : null}
          </div>
          {baseIsEmbedded ? (
            <p className="mb-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-900">
              Using uploaded image (embedded). Start session when ready.
            </p>
          ) : (
            <input
              type="url"
              value={baseImageUrl}
              onChange={(e) => setBaseImageUrl(e.target.value)}
              disabled={sessionId !== null}
              placeholder="https://…"
              className="mb-2 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent/30 disabled:bg-zinc-50"
            />
          )}
          {preloadedRef && !sessionId ? (
            <p className="mb-2 rounded-lg border border-accent/20 bg-accent/5 px-3 py-2 text-xs text-accent">
              Style reference will be pre-loaded into the session on start.
            </p>
          ) : null}
          <div className="flex gap-2">
            <button
              type="button"
              disabled={loading || !canStart}
              onClick={() => void startSession()}
              className="shrink-0 rounded-lg bg-zinc-900 px-3 py-2 text-sm font-semibold text-white hover:bg-zinc-800 disabled:opacity-40"
            >
              Start
            </button>
          </div>
        </div>

        {error ? (
          <div className="mx-5 mt-3 whitespace-pre-wrap rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
            {error}
          </div>
        ) : null}

        {requestedRefs || phase === "awaiting_references" ? (
          <div className="border-b border-amber-100 bg-amber-50/80 px-5 py-3">
            <p className="mb-2 text-xs font-semibold text-amber-900">
              {chatReferenceUrls.length > 0
                ? "Or upload your own references (max 2)"
                : "References for image-edit model (max 2)"}
            </p>
            {chatReferenceUrls.length > 0 ? (
              <p className="mb-2 text-[11px] text-amber-800/90">
                Generated options appear in the chat above — select the ones you want, then click Use
                selected.
              </p>
            ) : (
              <p className="mb-2 text-[11px] text-amber-800/90">HTTPS URL or upload a file for each slot.</p>
            )}
            <div className="mb-2 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={loading}
                onClick={() => refAFileRef.current?.click()}
                className="rounded-lg border border-amber-300 bg-white px-2 py-1 text-[11px] font-semibold text-amber-900 hover:bg-amber-50"
              >
                Upload ref 1
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={() => refBFileRef.current?.click()}
                className="rounded-lg border border-amber-300 bg-white px-2 py-1 text-[11px] font-semibold text-amber-900 hover:bg-amber-50"
              >
                Upload ref 2
              </button>
            </div>
            <input
              type="url"
              value={refAUrl}
              onChange={(e) => {
                setRefAUrl(e.target.value);
                setRefAEmbedded(null);
              }}
              placeholder="Reference 1 HTTPS URL (or upload above)"
              className="mb-2 w-full rounded-lg border border-amber-200/80 bg-white px-3 py-2 text-sm outline-none"
            />
            {refAEmbedded ? (
              <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-amber-900">
                <span>Ref 1: embedded file attached.</span>
                <button type="button" className="font-semibold underline" onClick={() => setRefAEmbedded(null)}>
                  Remove
                </button>
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => void saveRefToLibrary("a")}
                  className="rounded border border-amber-400 bg-white px-2 py-0.5 font-semibold hover:bg-amber-50 disabled:opacity-40"
                >
                  Save to library
                </button>
              </div>
            ) : refAUrl.trim() ? (
              <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-amber-900">
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => void saveRefToLibrary("a")}
                  className="rounded border border-amber-400 bg-white px-2 py-0.5 font-semibold hover:bg-amber-50 disabled:opacity-40"
                >
                  Save ref 1 URL to library
                </button>
              </div>
            ) : null}
            {libraryMsg?.slot === "a" ? (
              <p className="mb-2 rounded bg-emerald-50 px-2 py-1 text-[11px] text-emerald-800">
                {libraryMsg.text}
              </p>
            ) : null}
            <input
              type="url"
              value={refBUrl}
              onChange={(e) => {
                setRefBUrl(e.target.value);
                setRefBEmbedded(null);
              }}
              placeholder="Reference 2 HTTPS URL (optional)"
              className="mb-2 w-full rounded-lg border border-amber-200/80 bg-white px-3 py-2 text-sm outline-none"
            />
            {refBEmbedded ? (
              <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-amber-900">
                <span>Ref 2: embedded file attached.</span>
                <button type="button" className="font-semibold underline" onClick={() => setRefBEmbedded(null)}>
                  Remove
                </button>
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => void saveRefToLibrary("b")}
                  className="rounded border border-amber-400 bg-white px-2 py-0.5 font-semibold hover:bg-amber-50 disabled:opacity-40"
                >
                  Save to library
                </button>
              </div>
            ) : refBUrl.trim() ? (
              <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-amber-900">
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => void saveRefToLibrary("b")}
                  className="rounded border border-amber-400 bg-white px-2 py-0.5 font-semibold hover:bg-amber-50 disabled:opacity-40"
                >
                  Save ref 2 URL to library
                </button>
              </div>
            ) : null}
            {libraryMsg?.slot === "b" ? (
              <p className="mb-2 rounded bg-emerald-50 px-2 py-1 text-[11px] text-emerald-800">
                {libraryMsg.text}
              </p>
            ) : null}
            <button
              type="button"
              disabled={loading || !sessionId}
              onClick={() => void saveReferences()}
              className="rounded-lg bg-amber-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-800 disabled:opacity-40"
            >
              Save references
            </button>
          </div>
        ) : null}

        <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-5">
          {messages.length === 0 ? (
            <p className="text-sm text-zinc-400">Start a session, then describe what you want changed.</p>
          ) : null}
          {messages.map((m) => {
            if (m.role === "reasoning") {
              return (
                <div key={m.id} className="mr-auto max-w-[95%] space-y-1">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-violet-600">
                    Planner reasoning (thinking)
                  </p>
                  <div className="whitespace-pre-wrap rounded-2xl border border-violet-200 bg-violet-50/90 px-4 py-3 text-sm leading-relaxed text-violet-950">
                    {m.content}
                  </div>
                </div>
              );
            }
            return (
              <div
                key={m.id}
                className={`max-w-[90%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  m.role === "user"
                    ? "ml-auto bg-accent text-white"
                    : "mr-auto border border-zinc-200 bg-zinc-50 text-zinc-800"
                }`}
              >
                {m.content.trim() ? <p className="whitespace-pre-wrap">{m.content}</p> : null}
                {m.role === "assistant" && (m.reference_urls?.length ?? 0) > 0 ? (
                  <ChatReferencePicker
                    urls={m.reference_urls ?? []}
                    selected={selectedRefUrls}
                    saved={savedRefUrls}
                    disabled={loading}
                    onToggle={toggleRefSelection}
                  />
                ) : null}
              </div>
            );
          })}
          {chatReferenceUrls.length > 0 && phase !== "edit_completed" ? (
            <div className="mr-auto max-w-[90%] rounded-2xl border border-zinc-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-xs text-zinc-600">
                {selectedRefUrls.length === 0
                  ? "No references selected — the edit will run without style references."
                  : `${selectedRefUrls.length} reference${selectedRefUrls.length === 1 ? "" : "s"} selected for the edit.`}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={loading || !sessionId || !selectionDirty}
                  onClick={() => void applySelectedReferences(selectedRefUrls)}
                  className="rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#4f4ddb] disabled:opacity-40"
                >
                  Use selected ({selectedRefUrls.length}/2)
                </button>
                {savedRefUrls.length > 0 ? (
                  <button
                    type="button"
                    disabled={loading || !sessionId}
                    onClick={() => void clearSelectedReferences()}
                    className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-40"
                  >
                    Clear references
                  </button>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>

        <div className="border-t border-zinc-100 p-4">
          <div className="mb-2 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={loading || !sessionId || phase === "edit_completed"}
              onClick={() => void runEdit()}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-800 hover:bg-zinc-50 disabled:opacity-40"
            >
              Run image edit
            </button>
          </div>
          {phase === "edit_completed" && sessionId ? (
            <div className="mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-violet-200 bg-violet-50/60 px-3 py-2">
              <span className="text-xs font-medium text-violet-900">Planner and result</span>
              <button
                type="button"
                disabled={loading}
                onClick={() => void sendPlannerFeedback(true)}
                className="rounded-lg bg-violet-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-violet-800 disabled:opacity-40"
              >
                Agree
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={() => void sendPlannerFeedback(false)}
                className="rounded-lg border border-violet-400 bg-white px-3 py-1.5 text-xs font-semibold text-violet-900 hover:bg-violet-100 disabled:opacity-40"
              >
                Disagree
              </button>
              <span className="text-[11px] text-violet-800/90">
                Sends a short message to the assistant; Disagree opens the text box to add detail.
              </span>
            </div>
          ) : null}
          <div className="flex gap-2 rounded-xl border border-zinc-200 bg-zinc-50 p-2">
            <input
              ref={chatInputRef}
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void sendChat();
                }
              }}
              disabled={loading || !sessionId}
              placeholder="Message the reasoning agent…"
              className="min-w-0 flex-1 bg-transparent px-2 text-sm outline-none disabled:opacity-50"
            />
            <button
              type="button"
              disabled={loading || !sessionId || !chatInput.trim()}
              onClick={() => void sendChat()}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-[#4f4ddb] disabled:opacity-40"
            >
              Send
            </button>
          </div>
        </div>
      </section>

      <section className="flex flex-col bg-[#f4f4f7] p-5">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-bold text-zinc-900">Image workspace</h2>
          <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-zinc-600 shadow-sm">
            {projectName ?? `Project #${projectId}`} · {sessionId ? `Session #${sessionId}` : "No session"}
          </span>
        </div>
        <Card className="mb-4 overflow-hidden p-0">
          <img src={previewSrc} alt="Active frame" className="max-h-[340px] w-full object-contain bg-zinc-100" />
        </Card>

        <div className="mb-4">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">References &amp; assets</p>
            {sessionId && (
              <button
                type="button"
                disabled={loading}
                onClick={() => refAFileRef.current?.click()}
                className="rounded-lg border border-zinc-300 bg-white px-2.5 py-1 text-[11px] font-semibold text-zinc-700 shadow-sm hover:bg-zinc-50 disabled:opacity-40"
              >
                + Upload reference
              </button>
            )}
          </div>
          {(() => {
            const pendingRef = preloadedRef && !sessionId ? [preloadedRef] : [];
            const visibleRefs = savedRefUrls.length > 0 ? savedRefUrls : pendingRef;
            const isPending = visibleRefs === pendingRef && pendingRef.length > 0;
            if (visibleRefs.length > 0) {
              return (
                <div className="flex flex-wrap gap-2">
                  {visibleRefs.map((url, i) => (
                    <div
                      key={`ref-thumb-${i}-${url.slice(0, 32)}`}
                      className={`group relative h-20 w-24 overflow-hidden rounded-xl border bg-white shadow-sm ${
                        isPending ? "border-accent/40 ring-1 ring-accent/20" : "border-zinc-200"
                      }`}
                    >
                      <img
                        src={url}
                        alt={`Reference ${i + 1}`}
                        className="h-full w-full object-cover"
                      />
                      <span className={`absolute bottom-0 left-0 right-0 px-1.5 pb-1 pt-3 text-[10px] font-medium text-white ${
                        isPending ? "bg-gradient-to-t from-accent/70 to-transparent" : "bg-gradient-to-t from-black/50 to-transparent"
                      }`}>
                        {isPending ? "Pending" : `Ref ${i + 1}`}
                      </span>
                    </div>
                  ))}
                </div>
              );
            }
            return (
              <p className="rounded-xl border border-dashed border-zinc-300 bg-white/60 px-4 py-5 text-center text-xs text-zinc-400">
                {sessionId
                  ? "No references added yet. Upload or select references from the chat."
                  : "Start a session to add references."}
              </p>
            );
          })()}
        </div>

        {editUrls.length > 0 ? (
          <div className="mb-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">Edited outputs</p>
            <div className="grid gap-3 sm:grid-cols-2">
              {editUrls.map((u, i) => (
                <a
                  key={`${i}-${u.slice(0, 48)}`}
                  href={u}
                  target="_blank"
                  rel="noreferrer"
                  className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm"
                >
                  <img src={u} alt={`Edit ${i + 1}`} className="aspect-square w-full object-cover" />
                  <span className="block truncate px-2 py-1.5 text-[10px] text-zinc-500">Open full size</span>
                </a>
              ))}
            </div>
          </div>
        ) : null}

        <div className="border-t border-dashed border-zinc-200 px-5 py-3">
          <p className="text-[11px] leading-relaxed text-zinc-500">
            <span className="font-semibold text-zinc-700">Other pages</span> (Projects, Style exploration) are UI
            mockups only.{" "}
            <Link to="/workspace" className="font-semibold text-accent hover:underline">
              Assistant
            </Link>{" "}
            here is where the live reasoning + edit API runs.
          </p>
        </div>
      </section>
    </div>
  );
}
