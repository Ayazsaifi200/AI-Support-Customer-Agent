"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { reasoningStore } from "@/lib/reasoningStore";
import type { ChatMessage, Customer } from "@/lib/types";
import VoiceRecorder from "./VoiceRecorder";

interface UIMessage extends ChatMessage {
  decision?: string | null;
  audioUrl?: string;
  pending?: boolean;
}

const DECISION_STYLES: Record<string, string> = {
  approved: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  denied: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
};

export default function ChatPanel() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState<string>("");
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    api.customers().then(setCustomers).catch(() => setCustomers([]));
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  function history(): ChatMessage[] {
    return messages
      .filter((m) => !m.pending)
      .map((m) => ({ role: m.role, content: m.content }));
  }

  /** Speak text via ElevenLabs TTS and auto-play it. */
  async function speak(text: string): Promise<string | undefined> {
    const clean = text.trim();
    if (!clean) return undefined;
    try {
      const url = await api.tts(clean);
      audioRef.current?.pause();
      const audio = new Audio(url);
      audioRef.current = audio;
      setSpeaking(true);
      audio.onended = () => setSpeaking(false);
      audio.onerror = () => setSpeaking(false);
      void audio.play().catch(() => setSpeaking(false));
      return url;
    } catch (err) {
      setSpeaking(false);
      reasoningStore.marker(`⚠️ Voice reply failed: ${(err as Error).message}`);
      return undefined;
    }
  }

  /** Core turn: send a message through the agent; optionally speak the reply. */
  async function submitMessage(text: string, withVoice = false) {
    const clean = text.trim();
    if (!clean || busy) return;
    setBusy(true);
    reasoningStore.marker(`User: "${clean}"`);

    const hist = history();
    setMessages((m) => [
      ...m,
      { role: "user", content: clean },
      { role: "assistant", content: "", pending: true },
    ]);

    let reply = "";
    let decision: string | null = null;
    try {
      await api.chatStream(clean, customerId || undefined, hist, (e) => {
        reasoningStore.add(e);
        if (e.type === "final") {
          reply = e.reply;
          decision = e.decision;
        } else if (e.type === "error") {
          reply = `⚠️ ${e.message}`;
        }
      });
    } catch (err) {
      reply = `⚠️ ${(err as Error).message}`;
    }

    const finalReply = reply || "(no response)";
    setMessages((m) => {
      const copy = [...m];
      copy[copy.length - 1] = {
        role: "assistant",
        content: finalReply,
        decision,
      };
      return copy;
    });
    setBusy(false);

    if (withVoice && reply && !reply.startsWith("⚠️")) {
      const audioUrl = await speak(reply);
      if (audioUrl) {
        setMessages((m) => {
          const copy = [...m];
          for (let i = copy.length - 1; i >= 0; i--) {
            if (copy[i].role === "assistant") {
              copy[i] = { ...copy[i], audioUrl };
              break;
            }
          }
          return copy;
        });
      }
    }
  }

  async function sendText() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    await submitMessage(text, false);
  }

  async function transcribeVoice(blob: Blob) {
    if (busy || transcribing) return;
    setTranscribing(true);
    let text = "";
    try {
      text = (await api.transcribe(blob)).trim();
    } catch (err) {
      reasoningStore.marker(`⚠️ Transcription failed: ${(err as Error).message}`);
    } finally {
      setTranscribing(false);
    }
    if (text) {
      // Full spoken loop: STT -> agent -> TTS (spoken reply auto-plays).
      await submitMessage(text, true);
    } else {
      inputRef.current?.focus();
    }
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-center justify-between gap-3 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
        <div>
          <h2 className="text-sm font-semibold">Customer Support</h2>
          <p className="text-xs text-zinc-600 dark:text-zinc-400">Refund assistant</p>
        </div>
        <select
          value={customerId}
          onChange={(e) => setCustomerId(e.target.value)}
          className="max-w-[55%] rounded-md border border-zinc-300 bg-white px-2 py-1 text-xs text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        >
          <option value="">Guest (no customer)</option>
          {customers.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} · {c.tier}
            </option>
          ))}
        </select>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="mt-10 text-center text-sm text-zinc-600 dark:text-zinc-300">
            Ask about a refund. Try: <br />
            <span className="text-zinc-500 dark:text-zinc-400">
              &ldquo;I want a refund for my order, it arrived damaged.&rdquo;
            </span>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${
                m.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-100"
              }`}
            >
              {m.pending ? (
                <span className="inline-flex gap-1">
                  <Dot /> <Dot /> <Dot />
                </span>
              ) : (
                <span className="whitespace-pre-wrap">{m.content}</span>
              )}
              {m.decision && m.decision !== "none" && (
                <span
                  className={`mt-2 block w-fit rounded-full px-2 py-0.5 text-xs font-medium ${
                    DECISION_STYLES[m.decision] ?? "bg-zinc-200 text-zinc-600"
                  }`}
                >
                  Refund {m.decision}
                </span>
              )}
              {m.audioUrl && (
                <audio controls src={m.audioUrl} className="mt-2 h-8 w-full" />
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 border-t border-zinc-200 p-3 dark:border-zinc-800">
        <VoiceRecorder onRecorded={transcribeVoice} disabled={busy || transcribing} />
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendText()}
          placeholder={
            transcribing
              ? "Transcribing your voice…"
              : speaking
              ? "Speaking the reply…"
              : "Type or use the mic…"
          }
          disabled={busy}
          className="flex-1 rounded-full border border-zinc-300 bg-transparent px-4 py-2 text-sm text-zinc-900 outline-none placeholder:text-zinc-500 focus:border-blue-500 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-100 dark:placeholder:text-zinc-400"
        />
        <button
          onClick={sendText}
          disabled={busy || !input.trim()}
          className="rounded-full bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          Send
        </button>
      </div>
    </div>
  );
}

function Dot() {
  return <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400" />;
}
