"use client";

import { useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import AdminDashboard from "@/components/AdminDashboard";

type Tab = "chat" | "admin";

export default function Home() {
  const [tab, setTab] = useState<Tab>("chat");

  return (
    <div className="flex h-screen flex-col bg-zinc-50 dark:bg-zinc-950">
      <header className="flex items-center justify-between border-b border-zinc-200 bg-white px-6 py-3 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white">
            ✦
          </span>
          <div>
            <h1 className="text-sm font-semibold leading-tight">AI Customer Support Agent</h1>
            <p className="text-xs text-zinc-600 dark:text-zinc-400">Refund automation · LangGraph + ElevenLabs</p>
          </div>
        </div>
        <nav className="flex gap-1 rounded-lg bg-zinc-100 p-1 dark:bg-zinc-800">
          <TabButton active={tab === "chat"} onClick={() => setTab("chat")}>
            Customer Chat
          </TabButton>
          <TabButton active={tab === "admin"} onClick={() => setTab("admin")}>
            Admin Dashboard
          </TabButton>
        </nav>
      </header>

      <main className="min-h-0 flex-1 p-4">
        {tab === "chat" ? (
          <div className="mx-auto h-full max-w-2xl">
            <ChatPanel />
          </div>
        ) : (
          <AdminDashboard />
        )}
      </main>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
        active
          ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-white"
          : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-300 dark:hover:text-white"
      }`}
    >
      {children}
    </button>
  );
}
