import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";

type ChatSessionItem = {
  id: number;
  title: string | null;
  description: string | null;
  status: string;
  edit_sequence_number: number;
  created_at: string;
};

type ProjectSessionsPayload = {
  project_id: number;
  project_name: string;
  sessions: ChatSessionItem[];
};

const MOCK_SESSIONS: Record<number, ChatSessionItem[]> = {
  1: [
    {
      id: 5,
      title: "Final colour grading",
      description: "Warmed highlights +10%, desaturated greens to match brand palette.",
      status: "active",
      edit_sequence_number: 4,
      created_at: "2026-05-18T14:30:00Z",
    },
    {
      id: 4,
      title: "Background swap — studio white",
      description: "Replaced outdoor backdrop with clean studio white for hero banner.",
      status: "closed",
      edit_sequence_number: 3,
      created_at: "2026-05-15T11:00:00Z",
    },
    {
      id: 3,
      title: "Texture and lighting refinement",
      description: "Adjusted fabric texture sharpness and softened key light falloff.",
      status: "closed",
      edit_sequence_number: 2,
      created_at: "2026-05-10T09:15:00Z",
    },
    {
      id: 2,
      title: "Silhouette cleanup",
      description: "Removed stray flyaway hairs and refined garment outline.",
      status: "closed",
      edit_sequence_number: 1,
      created_at: "2026-05-06T16:45:00Z",
    },
    {
      id: 1,
      title: "Initial concept upload",
      description: "Uploaded raw photo set and locked palette direction with client.",
      status: "closed",
      edit_sequence_number: 0,
      created_at: "2026-05-01T10:00:00Z",
    },
  ],
};

export function EvolutionTimeline({
  projectId,
  className = "",
}: {
  projectId: number;
  className?: string;
}) {
  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/projects/${projectId}/sessions`)
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load sessions (${r.status})`);
        return r.json() as Promise<ProjectSessionsPayload>;
      })
      .then((data) => setSessions(data.sessions))
      .catch(() => setSessions(MOCK_SESSIONS[projectId] ?? []))
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return (
      <div className={`flex min-h-[200px] items-center justify-center rounded-2xl border border-zinc-200/80 bg-white ${className}`}>
        <p className="text-sm text-zinc-400">Loading timeline…</p>
      </div>
    );
  }

  if (sessions.length === 0 && !loading) {
    return (
      <div className={`flex min-h-[200px] items-center justify-center rounded-2xl border border-zinc-200/80 bg-white ${className}`}>
        <p className="text-sm text-zinc-400">No sessions yet</p>
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

          return (
            <li key={session.id} className="relative pb-10 pl-8 last:pb-0">
              {/* milestone circle */}
              <span
                className={`absolute left-0 top-0.5 flex h-4 w-4 items-center justify-center rounded-full border-2 ${
                  isLatest
                    ? "border-accent bg-accent shadow-[0_0_0_3px_rgba(94,92,230,0.18)]"
                    : "border-zinc-300 bg-white"
                }`}
              >
                {isLatest && (
                  <span className="h-1.5 w-1.5 rounded-full bg-white" />
                )}
              </span>

              {/* content */}
              <p className="text-xs font-medium text-zinc-400">{dateStr}</p>
              <p className={`mt-0.5 text-sm font-semibold ${isLatest ? "text-accent" : "text-zinc-900"}`}>
                {session.title ?? `Session #${session.id}`}
              </p>
              {session.description && (
                <p className="mt-1 text-xs leading-relaxed text-zinc-500">
                  {session.description}
                </p>
              )}
              <span className={`mt-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
                session.status === "active"
                  ? "bg-emerald-50 text-emerald-600"
                  : session.status === "closed"
                    ? "bg-zinc-100 text-zinc-500"
                    : "bg-amber-50 text-amber-600"
              }`}>
                {session.status}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
