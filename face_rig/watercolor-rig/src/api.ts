// Read API base URL from environment variable, default to localhost for development
export const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export type FrameInfo = {
  t: number;
  file: string;
};

export type Timeline = {
  path_id: string;
  expr_start: string;
  expr_end: string;
  pose: string;
  frames: FrameInfo[];
};

export async function fetchTimelines(): Promise<string[]> {
  try {
    const res = await fetch(`${API_BASE}/timelines`);
    if (!res.ok) throw new Error("No /timelines endpoint");
    return res.json();
  } catch {
    // optional endpoint: fall back to empty list
    return [];
  }
}

export async function fetchTimeline(pathId: string): Promise<Timeline> {
  const res = await fetch(`${API_BASE}/timeline/${encodeURIComponent(pathId)}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed to load timeline: ${res.status} ${text}`);
  }
  return res.json();
}

export async function regenerateFrame(
  pathId: string,
  t: number,
  anchorStartT?: number,
  anchorEndT?: number
): Promise<FrameInfo> {
  const params = new URLSearchParams();
  if (anchorStartT !== undefined) params.set("anchor_start_t", String(anchorStartT));
  if (anchorEndT !== undefined) params.set("anchor_end_t", String(anchorEndT));

  const url = params.toString()
    ? `${API_BASE}/timeline/${encodeURIComponent(pathId)}/regenerate?${params}`
    : `${API_BASE}/timeline/${encodeURIComponent(pathId)}/regenerate`;

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ t }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Regenerate failed: ${res.status} ${text}`);
  }
  return res.json();
}

