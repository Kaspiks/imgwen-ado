import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API_BASE } from "../lib/api";

type ProjectPayload = { id: number; project_name: string };

export function CreateProjectModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (open) {
      setName("");
      setError(null);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_name: trimmed }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error((body as { detail?: string })?.detail ?? res.statusText);
      }
      const project = (await res.json()) as ProjectPayload;

      await fetch(`${API_BASE}/projects/${project.id}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "Initial session" }),
      });

      onClose();
      navigate(`/workspace?projectId=${project.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create project");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-6 shadow-xl">
        <h2 className="text-lg font-bold text-zinc-900">New project</h2>
        <p className="mt-1 text-sm text-zinc-500">Give your project a name to get started.</p>

        <input
          ref={inputRef}
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !loading) void submit(); }}
          disabled={loading}
          placeholder="e.g. Summer campaign"
          className="mt-4 w-full rounded-xl border border-zinc-200 px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-accent/30 disabled:opacity-50"
        />

        {error && (
          <p className="mt-2 text-xs text-red-600">{error}</p>
        )}

        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="rounded-xl border border-zinc-200 bg-white px-4 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void submit()}
            disabled={loading || !name.trim()}
            className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-[#4f4ddb] disabled:opacity-40"
          >
            {loading ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
