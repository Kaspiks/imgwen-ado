import { useEffect, useState } from "react";
import { API_BASE, apiFetch } from "../lib/api";

type ChatSessionSummary = {
  id: number;
  title: string | null;
  description: string | null;
  status: string;
  edit_sequence_number: number;
  created_at: string;
  original_image_url: string | null;
  edited_image_url: string | null;
};

type ProjectSessionsPayload = {
  project_id: number;
  project_name: string;
  sessions: ChatSessionSummary[];
};

export function EvolutionTimeline({
  projectId,
  className = "",
}: {
  projectId: number;
  className?: string;
}) {
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    apiFetch(`${API_BASE}/projects/${projectId}/sessions`)
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load history (${r.status})`);
        return r.json() as Promise<ProjectSessionsPayload>;
      })
      .then((data) => setSessions(data.sessions))
      .catch((e) => {
        setSessions([]);
        setError(e instanceof Error ? e.message : "Failed to load history");
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return (
      <div className={`flex min-h-[200px] items-center justify-center rounded-2xl border border-zinc-200/80 bg-white ${className}`}>
        <p className="text-sm text-zinc-400">Loading timeline…</p>
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className={`flex min-h-[200px] flex-col items-center justify-center gap-1 rounded-2xl border border-zinc-200/80 bg-white ${className}`}>
        <p className="text-sm text-zinc-400">No edit sessions for this project yet.</p>
        {error ? <p className="text-xs text-zinc-300">{error}</p> : null}
      </div>
    );
  }

  return (
    <div className={`rounded-2xl border border-zinc-200/80 bg-white px-8 py-10 ${className}`}>
      <ol className="relative ml-4">
        {/* vertical line */}
        <div className="absolute left-[7px] top-0 h-full w-0.5 bg-zinc-200" />

        {sessions.map((session, idx) => {
          const isLatest = idx === 0;
          const date = new Date(session.created_at);
          const dateStr = date.toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric",
          });

          const timeStr = date.toLocaleTimeString(undefined, {
            hour: "numeric",
            minute: "2-digit",
          });

          return (
            <li key={session.id} className="relative pb-10 pl-8 last:pb-0">
              {/* milestone circle */}
              <span
                className={`absolute left-0 top-1 flex h-4 w-4 items-center justify-center rounded-full border-2 ${
                  isLatest
                    ? "border-accent bg-accent shadow-[0_0_0_3px_rgba(94,92,230,0.18)]"
                    : "border-zinc-300 bg-white"
                }`}
              >
                {isLatest && <span className="h-1.5 w-1.5 rounded-full bg-white" />}
              </span>

              {/* header row */}
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-xs font-medium text-zinc-400">
                  {dateStr} · {timeStr}
                </p>
                <span className="inline-block rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-500">
                  Edit #{session.edit_sequence_number}
                </span>
                {session.edited_image_url ? (
                  <span className="inline-block rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-emerald-600">
                    Edit completed
                  </span>
                ) : (
                  <span className="inline-block rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-600">
                    No edit yet
                  </span>
                )}
              </div>

              <p className={`mt-0.5 text-sm font-semibold ${isLatest ? "text-accent" : "text-zinc-900"}`}>
                {session.title ?? `Edit #${session.edit_sequence_number}`}
              </p>

              {session.description ? (
                <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-zinc-500">
                  {session.description}
                </p>
              ) : null}

              {/* before / after thumbnails */}
              <div className="mt-3 flex flex-wrap items-end gap-3">
                {session.original_image_url && (
                  <figure className="flex flex-col gap-1">
                    <img
                      src={session.original_image_url}
                      alt="Base"
                      className="h-24 w-24 rounded-lg border border-zinc-200 object-cover"
                    />
                    <figcaption className="text-center text-[10px] uppercase tracking-wide text-zinc-400">
                      Base
                    </figcaption>
                  </figure>
                )}

                {session.original_image_url && session.edited_image_url && (
                  <span className="mb-8 text-zinc-300">→</span>
                )}

                {session.edited_image_url && (
                  <figure className="flex flex-col gap-1">
                    <a href={session.edited_image_url} target="_blank" rel="noreferrer">
                      <img
                        src={session.edited_image_url}
                        alt="Edit"
                        className="h-24 w-24 rounded-lg border border-accent/30 object-cover transition hover:ring-2 hover:ring-accent/40"
                      />
                    </a>
                    <figcaption className="text-center text-[10px] uppercase tracking-wide text-zinc-400">
                      Edit
                    </figcaption>
                  </figure>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
