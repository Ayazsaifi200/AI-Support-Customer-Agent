"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { reasoningStore, useReasoningLogs } from "@/lib/reasoningStore";
import type { Customer, Order, PolicyRule, RefundRequest } from "@/lib/types";

export default function AdminDashboard() {
  const logs = useReasoningLogs();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [policy, setPolicy] = useState<PolicyRule[]>([]);
  const [refunds, setRefunds] = useState<RefundRequest[]>([]);
  const [live, setLive] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  const nameById = useMemo(
    () => Object.fromEntries(customers.map((c) => [c.id, c.name])),
    [customers]
  );

  useEffect(() => {
    api.customers().then(setCustomers).catch(() => {});
    api.orders().then(setOrders).catch(() => {});
    api.policy().then(setPolicy).catch(() => {});
    api.refundRequests().then(setRefunds).catch(() => {});
  }, []);

  // Realtime refund_requests via Supabase; fall back to polling.
  useEffect(() => {
    const sb = supabase;
    if (sb) {
      const channel = sb
        .channel("refund_requests_live")
        .on(
          "postgres_changes",
          { event: "INSERT", schema: "public", table: "refund_requests" },
          (payload) => {
            setRefunds((r) => [payload.new as RefundRequest, ...r]);
            setLive(true);
          }
        )
        .subscribe((status) => setLive(status === "SUBSCRIBED"));
      return () => {
        sb.removeChannel(channel);
      };
    }
    const id = setInterval(() => api.refundRequests().then(setRefunds).catch(() => {}), 4000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const approved = refunds.filter((r) => r.status === "approved").length;
  const denied = refunds.filter((r) => r.status === "denied").length;

  return (
    <div className="grid h-full grid-rows-[auto_1fr] gap-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Stat label="Customers" value={customers.length} />
        <Stat label="Orders" value={orders.length} />
        <Stat label="Policy Rules" value={policy.length} />
        <Stat label="Approved" value={approved} accent="text-emerald-500" />
        <Stat label="Denied" value={denied} accent="text-red-500" />
      </div>

      <div className="grid min-h-0 grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Reasoning logs */}
        <Panel
          title="Agent Reasoning Log"
          right={
            <button
              onClick={() => reasoningStore.clear()}
              className="text-xs text-zinc-400 hover:text-zinc-600"
            >
              clear
            </button>
          }
        >
          <div className="flex-1 space-y-1.5 overflow-y-auto p-3 font-mono text-xs">
            {logs.length === 0 && (
              <p className="mt-8 text-center text-zinc-400">
                No activity yet. Start a chat to see the agent reason in real time.
              </p>
            )}
            {logs.map((l) => (
              <LogLine key={l.id} log={l} />
            ))}
            <div ref={logEndRef} />
          </div>
        </Panel>

        {/* Refund requests */}
        <Panel
          title="Refund Decisions"
          right={
            <span className="flex items-center gap-1.5 text-xs text-zinc-400">
              <span
                className={`h-2 w-2 rounded-full ${live ? "bg-emerald-500" : "bg-zinc-400"}`}
              />
              {live ? "live" : "polling"}
            </span>
          }
        >
          <div className="flex-1 overflow-y-auto p-3">
            {refunds.length === 0 && (
              <p className="mt-8 text-center text-xs text-zinc-400">No refund decisions yet.</p>
            )}
            <ul className="space-y-2">
              {refunds.map((r) => (
                <li
                  key={r.id}
                  className="flex items-center justify-between rounded-lg border border-zinc-200 px-3 py-2 text-xs dark:border-zinc-800"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium">{nameById[r.customer_id] ?? r.customer_id}</p>
                    <p className="truncate text-zinc-600 dark:text-zinc-400">{r.reason ?? "—"}</p>
                  </div>
                  <span
                    className={`ml-3 shrink-0 rounded-full px-2 py-0.5 font-medium ${
                      r.status === "approved"
                        ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                        : "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300"
                    }`}
                  >
                    {r.status}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900">
      <p className="text-xs text-zinc-600 dark:text-zinc-400">{label}</p>
      <p className={`text-2xl font-semibold ${accent ?? ""}`}>{value}</p>
    </div>
  );
}

function Panel({
  title,
  right,
  children,
}: {
  title: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-0 flex-col rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-2.5 dark:border-zinc-800">
        <h3 className="text-sm font-semibold">{title}</h3>
        {right}
      </div>
      {children}
    </div>
  );
}

function LogLine({ log }: { log: ReturnType<typeof useReasoningLogs>[number] }) {
  if (log.type === "tool_call") {
    return (
      <div className="text-blue-600 dark:text-blue-400">
        <span className="text-zinc-400">▸ tool</span> {log.name}
        <span className="text-zinc-500"> {JSON.stringify(log.args)}</span>
      </div>
    );
  }
  if (log.type === "tool_result") {
    if (log.name === "—") {
      return <div className="text-zinc-500">• {log.output}</div>;
    }
    const text = log.output.length > 160 ? log.output.slice(0, 160) + "…" : log.output;
    return (
      <div className="text-zinc-600 dark:text-zinc-300">
        <span className="text-zinc-400">↳ {log.name}</span> {text}
      </div>
    );
  }
  if (log.type === "final") {
    return (
      <div className="text-emerald-600 dark:text-emerald-400">
        ✓ final{log.decision ? ` · refund ${log.decision}` : ""}: {log.reply.slice(0, 120)}
      </div>
    );
  }
  return <div className="text-red-500">⚠ {log.message}</div>;
}
