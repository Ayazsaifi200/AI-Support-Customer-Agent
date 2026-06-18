"use client";

import { useSyncExternalStore } from "react";
import type { AgentEvent, ReasoningLog } from "./types";

/**
 * A tiny global pub/sub store for the live agent reasoning log.
 * Both the chat panel (producer) and the admin dashboard (consumer) share it,
 * so reasoning steps appear on the dashboard in real time.
 */
let logs: ReasoningLog[] = [];
const listeners = new Set<() => void>();

function emit() {
  for (const l of listeners) l();
}

let counter = 0;

export const reasoningStore = {
  add(event: AgentEvent, source = "chat") {
    const entry: ReasoningLog = { ...event, id: `${Date.now()}-${counter++}`, ts: Date.now() };
    void source;
    logs = [...logs, entry].slice(-200);
    emit();
  },
  marker(label: string) {
    reasoningStore.add({ type: "tool_result", name: "—", output: label });
  },
  clear() {
    logs = [];
    emit();
  },
  subscribe(cb: () => void) {
    listeners.add(cb);
    return () => listeners.delete(cb);
  },
  snapshot() {
    return logs;
  },
};

export function useReasoningLogs(): ReasoningLog[] {
  return useSyncExternalStore(
    reasoningStore.subscribe,
    reasoningStore.snapshot,
    () => logs
  );
}
