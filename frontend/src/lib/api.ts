import type {
  AgentEvent,
  ChatMessage,
  Customer,
  Order,
  PolicyRule,
  RefundRequest,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  customers: () => getJSON<Customer[]>("/crm/customers"),
  orders: () => getJSON<Order[]>("/crm/orders"),
  policy: () => getJSON<PolicyRule[]>("/crm/policy"),
  refundRequests: () => getJSON<RefundRequest[]>("/crm/refund-requests"),

  /** Non-streaming chat. Returns reply + decision + tool calls. */
  async chat(message: string, customerId?: string, history: ChatMessage[] = []) {
    const res = await fetch(`${API_BASE}/agent/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, customer_id: customerId ?? null, history }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail ?? `${res.status} ${res.statusText}`);
    }
    return res.json() as Promise<{
      reply: string;
      decision: string | null;
      tool_calls: { name: string; args: Record<string, unknown> }[];
    }>;
  },

  /** Streaming chat over SSE. Calls onEvent for each reasoning step. */
  async chatStream(
    message: string,
    customerId: string | undefined,
    history: ChatMessage[],
    onEvent: (e: AgentEvent) => void,
    signal?: AbortSignal
  ): Promise<void> {
    const res = await fetch(`${API_BASE}/agent/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, customer_id: customerId ?? null, history }),
      signal,
    });
    if (!res.ok || !res.body) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail ?? `${res.status} ${res.statusText}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        try {
          onEvent(JSON.parse(line.slice(5).trim()) as AgentEvent);
        } catch {
          /* ignore malformed chunk */
        }
      }
    }
  },

  /** Speech-to-text only: send recorded audio, get the transcript text. */
  async transcribe(blob: Blob): Promise<string> {
    const form = new FormData();
    form.append("file", blob, "recording.webm");
    const res = await fetch(`${API_BASE}/voice/stt`, { method: "POST", body: form });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail ?? `${res.status} ${res.statusText}`);
    }
    const data = (await res.json()) as { text?: string };
    return data.text ?? "";
  },

  /** Text-to-speech: convert text into spoken audio, return a playable URL. */
  async tts(text: string, voiceId?: string): Promise<string> {
    const res = await fetch(`${API_BASE}/voice/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice_id: voiceId ?? null }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail ?? `${res.status} ${res.statusText}`);
    }
    const audio = await res.blob();
    return URL.createObjectURL(audio);
  },

  /** Voice turn: send recorded audio, get spoken reply + transcript/decision. */
  async voiceTalk(blob: Blob, customerId?: string) {
    const form = new FormData();
    form.append("file", blob, "recording.webm");
    if (customerId) form.append("customer_id", customerId);
    const res = await fetch(`${API_BASE}/voice/talk`, { method: "POST", body: form });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail ?? `${res.status} ${res.statusText}`);
    }
    const transcript = decodeURIComponent(res.headers.get("X-Transcript") ?? "");
    const reply = decodeURIComponent(res.headers.get("X-Reply") ?? "");
    const decision = res.headers.get("X-Decision") ?? "none";
    const audio = await res.blob();
    return { transcript, reply, decision, audioUrl: URL.createObjectURL(audio) };
  },
};

export { API_BASE };
