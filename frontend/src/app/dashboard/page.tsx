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

  return (
    <div className="mx-auto max-w-4xl p-6">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-bold">Your Clones</h1>
        <button
          onClick={() => setCreating(true)}
          className="rounded bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700"
        >
          + New Clone
        </button>
      </div>

      {creating && (
        <div className="mb-6 rounded-xl border bg-white p-4 shadow-sm">
          <h2 className="mb-3 font-semibold">Create a new clone</h2>
          <div className="flex gap-2">
            <input
              className="flex-1 rounded border px-3 py-2"
              placeholder="Clone name (e.g. Richard Feynman)"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createClone()}
              autoFocus
            />
            <button onClick={createClone} className="rounded bg-indigo-600 px-4 py-2 text-white">
              Create
            </button>
            <button onClick={() => setCreating(false)} className="rounded border px-4 py-2">
              Cancel
            </button>
          </div>
        </div>
      )}

      {clones.length === 0 && !creating ? (
        <div className="rounded-xl border-2 border-dashed border-gray-200 py-20 text-center">
          <p className="mb-2 text-xl font-medium text-gray-500">No clones yet</p>
          <p className="mb-6 text-gray-400">Create your first AI clone by uploading content about a person.</p>
          <button
            onClick={() => setCreating(true)}
            className="rounded bg-indigo-600 px-6 py-2 text-white hover:bg-indigo-700"
          >
            Create your first clone
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {clones.map((clone) => (
            <Link key={clone.id} href={`/clones/${clone.id}`}>
              <div className="cursor-pointer rounded-xl border bg-white p-5 shadow-sm hover:shadow-md transition">
                <div className="mb-2 flex items-start justify-between">
                  <h3 className="font-semibold text-lg">{clone.name}</h3>
                  {clone.identity_anchor?.confidence === "low" && (
                    <span className="rounded bg-yellow-100 px-2 py-0.5 text-xs text-yellow-700">
                      Limited data
                    </span>
                  )}
                </div>
                {clone.description && (
                  <p className="mb-3 text-sm text-gray-500">{clone.description}</p>
                )}
                <p className="text-xs text-gray-400">{clone.chunk_count} chunks indexed</p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
