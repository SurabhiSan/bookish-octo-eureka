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

  // Poll for pending documents
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

  const statusColors: Record<string, string> = {
    queued: "bg-gray-100 text-gray-600",
    processing: "bg-blue-100 text-blue-700",
    indexed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
  };

  const confidence = (clone?.identity_anchor as Record<string, string> | null)?.confidence;

  return (
    <div className="mx-auto max-w-3xl p-6">
      <Link href="/dashboard" className="text-sm text-indigo-600 hover:underline">← Dashboard</Link>

      {clone && (
        <div className="mt-4 mb-6 flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold">{clone.name}</h1>
            <p className="text-sm text-gray-400 mt-1">{clone.chunk_count} chunks indexed</p>
          </div>
          <Link
            href={`/chat/${cloneId}/new`}
            className="rounded bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700"
          >
            Chat with clone
          </Link>
        </div>
      )}

      {confidence === "low" && (
        <div className="mb-4 rounded-lg bg-yellow-50 border border-yellow-200 px-4 py-3 text-sm text-yellow-800">
          ⚠ This clone has limited source material (fewer than 5 indexed chunks). Responses may be less accurate. Upload more content to improve quality.
        </div>
      )}

      <div className="mb-6 rounded-xl border bg-white p-5 shadow-sm">
        <h2 className="mb-3 font-semibold">Upload Document</h2>
        <div className="mb-3 flex gap-2 flex-wrap">
          {SOURCE_TYPES.map((t) => (
            <button
              key={t}
              onClick={() => setSourceType(t)}
              className={`rounded px-3 py-1 text-sm ${sourceType === t ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-600"}`}
            >
              {t}
            </button>
          ))}
        </div>
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const file = e.dataTransfer.files[0];
            if (file) uploadFile(file);
          }}
          className={`rounded-lg border-2 border-dashed p-8 text-center transition ${dragOver ? "border-indigo-400 bg-indigo-50" : "border-gray-200"}`}
        >
          {uploading ? (
            <p className="text-gray-500">Uploading…</p>
          ) : (
            <>
              <p className="text-gray-500 mb-2">Drop a file here, or</p>
              <label className="cursor-pointer text-indigo-600 underline">
                browse
                <input
                  type="file"
                  className="hidden"
                  accept=".pdf,.docx,.txt,.md,.csv"
                  onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])}
                />
              </label>
              <p className="mt-1 text-xs text-gray-400">PDF, DOCX, TXT, MD, CSV · max 50MB</p>
            </>
          )}
        </div>
      </div>

      {docs.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed border-gray-200 py-12 text-center text-gray-400">
          No documents yet. Upload content to train this clone.
        </div>
      ) : (
        <div className="space-y-2">
          {docs.map((doc) => (
            <div key={doc.id} className="flex items-center justify-between rounded-lg border bg-white px-4 py-3">
              <div>
                <p className="font-medium text-sm">{doc.filename}</p>
                <p className="text-xs text-gray-400">{doc.source_type} · {doc.chunk_count} chunks</p>
                {doc.error && <p className="text-xs text-red-500">{doc.error}</p>}
              </div>
              <span className={`rounded px-2 py-1 text-xs font-medium ${statusColors[doc.status] || ""}`}>
                {doc.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
