"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import Link from "next/link";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
}

export default function ChatPage() {
  const params = useParams();
  const router = useRouter();
  const cloneId = params.cloneId as string;
  const sessionId = params.sessionId as string;

  const [clone, setClone] = useState<{ name: string; identity_anchor?: Record<string, unknown> } | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [showSources, setShowSources] = useState<string[] | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!api.getToken()) { router.push("/login"); return; }
    if (sessionId === "new") return;

    api.get(`/clones/${cloneId}`).then((r) => r.json()).then(setClone);
    api.get(`/conversations/${sessionId}/messages`).then((r) => r.json()).then((msgs: Array<{role: string; content: string}>) => {
      setMessages(msgs.map((m) => ({ role: m.role as "user" | "assistant", content: m.content })));
    });
  }, [cloneId, sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage() {
    if (!input.trim() || streaming) return;
    const userText = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userText }]);
    setStreaming(true);

    let convId = sessionId;
    if (sessionId === "new") {
      const res = await api.post("/conversations", { clone_id: cloneId });
      const conv = await res.json();
      convId = conv.id;
      router.replace(`/chat/${cloneId}/${convId}`);
    }

    const token = api.getToken();
    const response = await fetch(api.streamUrl(`/conversations/${convId}/messages`), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ content: userText }),
    });

    const reader = response.body?.getReader();
    if (!reader) { setStreaming(false); return; }

    let assistantText = "";
    let sources: string[] = [];
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const lines = decoder.decode(value).split("\n");
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6);
        if (data === "[DONE]") break;
        try {
          const event = JSON.parse(data);
          if (event.type === "token") {
            assistantText += event.text;
            setMessages((prev) => [
              ...prev.slice(0, -1),
              { role: "assistant", content: assistantText, sources },
            ]);
          } else if (event.type === "sources") {
            sources = event.chunk_ids || [];
          }
        } catch {}
      }
    }
    setStreaming(false);
  }

  const confidence = (clone?.identity_anchor as Record<string, string> | null)?.confidence;

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 border-b bg-white px-6 py-3">
        <Link href={`/clones/${cloneId}`} className="text-sm text-indigo-600 hover:underline">
          ← {clone?.name || "Clone"}
        </Link>
        {confidence === "low" && (
          <span className="rounded bg-yellow-100 px-2 py-0.5 text-xs text-yellow-700">Limited data — responses may vary</span>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-gray-400">
            <div className="text-center">
              <p className="text-lg mb-2">Start a conversation with {clone?.name}</p>
              <p className="text-sm">Ask anything you'd ask the real person.</p>
            </div>
          </div>
        )}
        <div className="mx-auto max-w-2xl space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
                  msg.role === "user"
                    ? "bg-indigo-600 text-white"
                    : "bg-white border text-gray-800 shadow-sm"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
                {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                  <button
                    onClick={() => setShowSources(showSources ? null : msg.sources!)}
                    className="mt-2 text-xs text-indigo-400 hover:text-indigo-600"
                  >
                    {showSources ? "Hide sources" : `${msg.sources.length} sources`}
                  </button>
                )}
              </div>
            </div>
          ))}
          {streaming && (
            <div className="flex justify-start">
              <div className="rounded-2xl border bg-white px-4 py-3 shadow-sm">
                <span className="animate-pulse text-gray-400 text-sm">●●●</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Sources drawer */}
      {showSources && showSources.length > 0 && (
        <div className="border-t bg-gray-50 px-4 py-3">
          <p className="text-xs font-medium text-gray-500 mb-1">Retrieved sources ({showSources.length})</p>
          <div className="flex flex-wrap gap-1">
            {showSources.map((id) => (
              <span key={id} className="rounded bg-gray-200 px-2 py-0.5 text-xs font-mono text-gray-600">
                {id.slice(0, 8)}…
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t bg-white px-4 py-3">
        <div className="mx-auto flex max-w-2xl gap-2">
          <textarea
            className="flex-1 resize-none rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            rows={1}
            placeholder={`Ask ${clone?.name || "the clone"} anything…`}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
          />
          <button
            onClick={sendMessage}
            disabled={streaming || !input.trim()}
            className="rounded-xl bg-indigo-600 px-4 py-2 text-white disabled:opacity-40 hover:bg-indigo-700"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
