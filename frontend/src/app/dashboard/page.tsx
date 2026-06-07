"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import { useRouter } from "next/navigation";

interface Clone {
  id: string;
  name: string;
  description: string | null;
  chunk_count: number;
  identity_anchor: { confidence?: string } | null;
}

function avatarColor(name: string) {
  const colors = [
    "from-violet-600 to-purple-700",
    "from-blue-600 to-cyan-700",
    "from-emerald-600 to-teal-700",
    "from-rose-600 to-pink-700",
    "from-amber-600 to-orange-700",
    "from-indigo-600 to-blue-700",
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
}

export default function Dashboard() {
  const [clones, setClones] = useState<Clone[]>([]);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const router = useRouter();

  useEffect(() => {
    if (!api.getToken()) { router.push("/login"); return; }
    api.get("/clones").then((r) => r.json()).then(setClones);
  }, []);

  async function createClone() {
    if (!newName.trim()) return;
    const res = await api.post("/clones", { name: newName });
    if (res.ok) {
      const clone = await res.json();
      setClones((prev) => [...prev, clone]);
      setNewName("");
      setCreating(false);
    }
  }

  function signOut() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    router.push("/login");
  }

  return (
    <div className="min-h-screen bg-[#08080f]">
      {/* Navbar */}
      <header className="border-b border-zinc-800/60 bg-[#08080f]/80 backdrop-blur-md sticky top-0 z-10">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-600/20 ring-1 ring-violet-500/30">
              <svg className="h-4 w-4 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
              </svg>
            </div>
            <span className="font-semibold text-zinc-100 tracking-tight">CloneAI</span>
          </div>
          <button onClick={signOut} className="text-xs text-zinc-500 hover:text-zinc-300 transition">
            Sign out
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-10">
        {/* Page header */}
        <div className="mb-8 flex items-end justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">Your Clones</h1>
            <p className="mt-1 text-sm text-zinc-500">AI personas trained on real content</p>
          </div>
          <button
            onClick={() => setCreating(true)}
            className="flex items-center gap-1.5 rounded-xl bg-violet-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-violet-500"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            New Clone
          </button>
        </div>

        {/* Create form */}
        {creating && (
          <div className="mb-6 rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5 shadow-xl">
            <p className="mb-3 text-sm font-medium text-zinc-300">Name your clone</p>
            <div className="flex gap-2">
              <input
                className="flex-1 rounded-xl border border-zinc-700 bg-zinc-800/60 px-3 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 outline-none transition focus:border-violet-500 focus:ring-1 focus:ring-violet-500/50"
                placeholder="e.g. Richard Feynman, Steve Jobs, yourself…"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && createClone()}
                autoFocus
              />
              <button
                onClick={createClone}
                className="rounded-xl bg-violet-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-violet-500"
              >
                Create
              </button>
              <button
                onClick={() => { setCreating(false); setNewName(""); }}
                className="rounded-xl border border-zinc-700 px-4 py-2 text-sm text-zinc-400 transition hover:bg-zinc-800"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Empty state */}
        {clones.length === 0 && !creating ? (
          <div className="rounded-2xl border border-dashed border-zinc-800 py-24 text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-zinc-900 ring-1 ring-zinc-800">
              <svg className="h-6 w-6 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
              </svg>
            </div>
            <p className="mb-1 text-base font-medium text-zinc-400">No clones yet</p>
            <p className="mb-6 text-sm text-zinc-600">Upload content to train your first AI persona.</p>
            <button
              onClick={() => setCreating(true)}
              className="rounded-xl bg-violet-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-violet-500"
            >
              Create your first clone
            </button>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {clones.map((clone) => (
              <Link key={clone.id} href={`/clones/${clone.id}`}>
                <div className="group cursor-pointer rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5 transition hover:border-zinc-700 hover:bg-zinc-900/80">
                  <div className="mb-4 flex items-start justify-between">
                    <div className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${avatarColor(clone.name)} text-sm font-semibold text-white shadow-lg`}>
                      {clone.name.charAt(0).toUpperCase()}
                    </div>
                    {clone.identity_anchor?.confidence === "low" && (
                      <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-500 ring-1 ring-amber-500/20">
                        Low data
                      </span>
                    )}
                    {clone.identity_anchor?.confidence === "high" && (
                      <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-500 ring-1 ring-emerald-500/20">
                        Ready
                      </span>
                    )}
                  </div>
                  <h3 className="font-medium text-zinc-100 group-hover:text-white transition">{clone.name}</h3>
                  {clone.description && (
                    <p className="mt-1 text-xs text-zinc-500 line-clamp-2">{clone.description}</p>
                  )}
                  <p className="mt-3 text-xs text-zinc-600">
                    {clone.chunk_count === 0 ? "No content yet" : `${clone.chunk_count} chunks indexed`}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
