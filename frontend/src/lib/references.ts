import { API_BASE, apiFetch } from "./api";

export type ReferenceLibraryItem = {
  point_id: string;
  image_url: string;
  description: string;
  tags: string[];
};

export type StyleTile = {
  id: string;
  tag: string;
  title: string;
  src: string;
  description: string;
  tokens: { k: string; v: string }[];
};

const DEFAULT_TAG = "Reference";

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

export function isReferenceImageUrl(url: string): boolean {
  const t = url.trim();
  return t.startsWith("http") || t.startsWith("data:image");
}

export function referenceTag(tags: string[]): string {
  const raw = tags.find((t) => t.trim())?.trim();
  if (!raw) return DEFAULT_TAG;
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

export function referenceTitle(description: string): string {
  const trimmed = description.trim();
  if (!trimmed) return "Untitled reference";
  const firstSentence = trimmed.split(/[.!?](?:\s|$)/)[0]?.trim();
  const candidate = firstSentence && firstSentence.length <= 72 ? firstSentence : trimmed;
  return candidate.length > 72 ? `${candidate.slice(0, 69)}…` : candidate;
}

export function referenceTokens(item: ReferenceLibraryItem): StyleTile["tokens"] {
  const tokens: StyleTile["tokens"] = [];
  for (const tag of item.tags.slice(0, 3)) {
    tokens.push({ k: "Tag", v: tag });
  }
  if (item.description.trim()) {
    tokens.push({ k: "Description", v: item.description.trim() });
  }
  if (tokens.length === 0) {
    tokens.push({ k: "Style", v: "Saved from workspace" });
  }
  return tokens;
}

export function libraryItemToTile(item: ReferenceLibraryItem): StyleTile {
  return {
    id: item.point_id,
    tag: referenceTag(item.tags),
    title: referenceTitle(item.description),
    src: item.image_url,
    description: item.description.trim() || "Saved style reference from your library.",
    tokens: referenceTokens(item),
  };
}

export async function fetchReferenceLibrary(): Promise<ReferenceLibraryItem[]> {
  const res = await apiFetch(`${API_BASE}/workflow/edit-flow/references`);
  if (!res.ok) throw new Error(await readError(res));
  const body = (await res.json()) as { references: ReferenceLibraryItem[] };
  return body.references ?? [];
}

export async function ingestReferenceToLibrary(
  imageUrl: string,
  tags: string[] = ["Uploaded"],
): Promise<ReferenceLibraryItem> {
  const res = await apiFetch(`${API_BASE}/workflow/edit-flow/references/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_url: imageUrl, description: "", tags }),
  });
  if (!res.ok) throw new Error(await readError(res));
  const body = (await res.json()) as { point_id: string; description: string };
  return {
    point_id: body.point_id,
    image_url: imageUrl,
    description: body.description,
    tags,
  };
}

/** Fire-and-forget ingest; logs to console on failure so session UX is not blocked. */
export function ingestReferenceToLibraryQuietly(imageUrl: string, tags: string[] = ["Uploaded"]): void {
  if (!isReferenceImageUrl(imageUrl)) return;
  void ingestReferenceToLibrary(imageUrl, tags).catch((err) => {
    console.warn("[reference library] auto-ingest failed:", err);
  });
}

export function ingestReferenceUrlsQuietly(urls: string[], tags: string[] = ["Session"]): void {
  const seen = new Set<string>();
  for (const url of urls) {
    const trimmed = url.trim();
    if (!isReferenceImageUrl(trimmed) || seen.has(trimmed)) continue;
    seen.add(trimmed);
    ingestReferenceToLibraryQuietly(trimmed, tags);
  }
}
