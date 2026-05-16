import type { SSEChunk } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const STREAM_TIMEOUT_MS = 90_000;

export async function* streamChat(params: {
  message: string;
  sessionId: string;
  budget?: string;
  cuisine?: string;
}): AsyncGenerator<SSEChunk> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), STREAM_TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: params.message,
        session_id: params.sessionId,
        budget: params.budget || null,
        cuisine: params.cuisine || null,
      }),
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    const msg = (err as Error).name === "AbortError" ? "请求超时，请重试" : "网络错误，请检查连接";
    yield { type: "error", content: msg };
    return;
  }

  if (!res.ok) {
    clearTimeout(timer);
    yield { type: "error", content: `HTTP ${res.status}` };
    return;
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const raw = line.slice(5).trim();
        if (!raw) continue;
        try {
          yield JSON.parse(raw) as SSEChunk;
        } catch {
          // malformed chunk — skip
        }
      }
    }
  } finally {
    clearTimeout(timer);
    reader.cancel().catch(() => undefined);
  }
}

export async function clearSession(sessionId: string) {
  await fetch(`${API_BASE}/session/${sessionId}`, { method: "DELETE" });
}
