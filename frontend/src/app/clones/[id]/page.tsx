"use client";
import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import Link from "next/link";

interface Document {
  id: string;
  filename: string;
  source_type: string;
  status: string;
  chunk_count: number;
  error: string | null;
}

const SOURCE_TYPES = ["journal", "email", "article", "note", "transcript", "tweet"];

const statusConfig: Record<string, { label: string; classes: string }> = {
  queued:     { label: "Queued",     classes: "bg-zinc-800 text-zinc-400 ring-zinc-700/50" },
  processing: { label: "Processing", classes: "bg-blue-500/10 text-blue-400 ring-blue-500/20" },
  indexed:    { label: "Indexed",    classes: "bg-emerald-500/10 text-emerald-400 ring-emerald-500/20" },
  failed:     { label: "Failed",     classes: "bg-red-500/10 text-red-400 ring-red-500/20" },
};

export default function CloneDetail() {
  const params = useParams();
  const router = useRouter();
  const cloneId = params.id as string;

  const [clone, setClone] = useState<{ name: string; chunk_count: number; identity_anchor: Record<string, unknown> | null } | null>(null);
  const [docs, setDocs] = useState<Document[]>([]);
  const [sourceType, setSourceType] = useState("article");
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const fetchDocs = useCallback(async () => {
    const res = await api.get(`/clones/${cloneId}/documents`);
    if (res.ok) setDocs(await res.json());
  }, [cloneId]);

  useEffect(() => {
    if (!api.getToken()) { router.push("/login"); return; }
    api.get(`/clones/${cloneId}`).then((r) => r.json()).then(setClone);
    fetchDocs();
  }, [cloneId, fetchDocs]);

  useEffect(() => {
    const pending = docs.some((d) => d.status === "queued" || d.status === "processing");
    if (!pending) return;
    const interval = setInterval(fetchDocs, 2000);
    return () => clearInterval(interval);
  }, [docs, fetchDocs]);

  async function uploadFile(file: File) {
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("source_type", sourceType);
    const res = await api.upload(`/clones/${cloneId}/documents`, fd);
    setUploading(false);
    if (res.ok) fetchDocs();
  }

  const confidence = (clone?.identity_anchor as Record<string, string> | null)?.confidence;

  return (
    <div className="min-h-screen bg-[#08080f]">
      {/* Navbar */}
      <header className="border-b border-zinc-800/60 bg-[#08080f]/80 backdrop-blur-md sticky top-0 z-10">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <Link href="/dashboard" className="flex items-center gap-1.5 text-sm text-zinc-500 transition hover:text-zinc-300">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
            </svg>
            Dashboard
          </Link>
          {clone && (
            <Link
              href={`/chat/${cloneId}/new`}
              className="flex items-center gap-1.5 rounded-xl bg-violet-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-violet-500"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
              </svg>
              Chat
            </Link>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-10">
        {/* Clone header */}
        {clone && (
          <div className="mb-8">
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">{clone.name}</h1>
            <p className="mt-1 text-sm text-zinc-500">
              {clone.chunk_count === 0 ? "No content indexed yet" : `${clone.chunk_count} chunks indexed`}
            </p>
          </div>
        )}

        {/* Low data warning */}
        {confidence === "low" && (
          <div className="mb-6 flex items-start gap-3 rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-3">
            <svg className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
            </svg>
            <p className="text-sm text-amber-400">
              Limited source material — fewer than 5 chunks indexed. Upload more content to improve response quality.
            </p>
          </div>
        )}

        {/* Upload section */}
        <div className="mb-6 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6">
          <h2 className="mb-4 text-sm font-semibold text-zinc-300">Upload Content</h2>

          {/* Source type pills */}
          <div className="mb-4 flex flex-wrap gap-2">
            {SOURCE_TYPES.map((t) => (
              <button
                key={t}
                onClick={() => setSourceType(t)}
                className={`rounded-full px-3 py-1 text-xs font-medium capitalize transition ${
                  sourceType === t
                    ? "bg-violet-600 text-white"
                    : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-300"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const file = e.dataTransfer.files[0];
              if (file) uploadFile(file);
            }}
            className={`rounded-xl border-2 border-dashed p-10 text-center transition ${
              dragOver
                ? "border-violet-500 bg-violet-500/5"
                : "border-zinc-800 hover:border-zinc-700"
            }`}
          >
            {uploading ? (
              <div className="flex items-center justify-center gap-2 text-sm text-zinc-400">
                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Uploading…
              </div>
            ) : (
              <>
                <svg className="mx-auto mb-3 h-8 w-8 text-zinc-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
                </svg>
                <p className="text-sm text-zinc-400 mb-1">Drop a file here, or{" "}
                  <label className="cursor-pointer text-violet-400 hover:text-violet-300 transition">
                    browse
                    <input
                      type="file"
                      className="hidden"
                      accept=".pdf,.docx,.txt,.md,.csv"
                      onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])}
                    />
                  </label>
                </p>
                <p className="text-xs text-zinc-600">PDF, DOCX, TXT, MD, CSV · max 50MB</p>
              </>
            )}
          </div>
        </div>

        {/* Documents list */}
        {docs.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-zinc-800 py-12 text-center text-sm text-zinc-600">
            No documents yet — upload content to train this clone.
          </div>
        ) : (
          <div className="space-y-2">
            <h2 className="mb-3 text-sm font-semibold text-zinc-400">Documents</h2>
            {docs.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between rounded-xl border border-zinc-800 bg-zinc-900/40 px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-zinc-200">{doc.filename}</p>
                  <p className="text-xs text-zinc-500 capitalize">{doc.source_type} · {doc.chunk_count} chunks</p>
                  {doc.error && <p className="text-xs text-red-400">{doc.error}</p>}
                </div>
                <span className={`ml-3 flex-shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${(statusConfig[doc.status] || statusConfig.queued).classes}`}>
                  {(statusConfig[doc.status] || { label: doc.status }).label}
                </span>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
