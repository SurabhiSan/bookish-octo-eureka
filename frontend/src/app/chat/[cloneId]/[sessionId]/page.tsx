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
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!api.getToken()) { router.push("/login"); return; }
    if (sessionId === "new") {
      api.get(`/clones/${cloneId}`).then((r) => r.json()).then(setClone);
      return;
    }
    api.get(`/clones/${cloneId}`).then((r) => r.json()).then(setClone);
    api.get(`/conversations/${sessionId}/messages`).then((r) => r.json()).then((msgs: Array<{role: string; content: string}>) => {
      setMessages(msgs.map((m) => ({ role: m.role as "user" | "assistant", content: m.content })));
    });
  }, [cloneId, sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [input]);

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
    <div className="flex h-screen flex-col bg-[#08080f]">
      {/* Header */}
      <header className="flex items-center gap-3 border-b border-zinc-800/60 bg-[#08080f]/80 px-4 py-3 backdrop-blur-md">
        <Link
          href={`/clones/${cloneId}`}
          className="flex items-center gap-1.5 rounded-lg p-1.5 text-zinc-500 transition hover:bg-zinc-800 hover:text-zinc-300"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
        </Link>

        {clone && (
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-600/20 text-xs font-semibold text-violet-300 ring-1 ring-violet-500/30">
              {clone.name.charAt(0).toUpperCase()}
            </div>
            <span className="text-sm font-medium text-zinc-200">{clone.name}</span>
          </div>
        )}

        {confidence === "low" && (
          <span className="ml-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-500 ring-1 ring-amber-500/20">
            Limited data
          </span>
        )}
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-600/10 ring-1 ring-violet-500/20">
                <svg className="h-6 w-6 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
                </svg>
              </div>
              <p className="text-base font-medium text-zinc-300">
                Start a conversation with {clone?.name || "this clone"}
              </p>
              <p className="mt-1 text-sm text-zinc-600">Ask anything you'd ask the real person.</p>
            </div>
          </div>
        )}

        <div className="mx-auto max-w-2xl space-y-5">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
              {/* Avatar */}
              <div className="flex-shrink-0">
                {msg.role === "assistant" ? (
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-600/20 text-xs font-semibold text-violet-300 ring-1 ring-violet-500/30">
                    {clone?.name?.charAt(0).toUpperCase() || "A"}
                  </div>
                ) : (
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-zinc-700 text-xs font-semibold text-zinc-300">
                    U
                  </div>
                )}
              </div>

              {/* Bubble */}
              <div className={`max-w-[80%] ${msg.role === "user" ? "items-end" : "items-start"} flex flex-col gap-1`}>
                <div
                  className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-violet-600 text-white"
                      : "border border-zinc-800 bg-zinc-900 text-zinc-200"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>
                {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                  <p className="px-1 text-xs text-zinc-600">
                    {msg.sources.length} source{msg.sources.length > 1 ? "s" : ""} retrieved
                  </p>
                )}
              </div>
            </div>
          ))}

          {/* Typing indicator */}
          {streaming && (
            <div className="flex gap-3">
              <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-violet-600/20 text-xs font-semibold text-violet-300 ring-1 ring-violet-500/30">
                {clone?.name?.charAt(0).toUpperCase() || "A"}
              </div>
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900 px-4 py-3">
                <div className="flex gap-1">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-500" style={{ animationDelay: "0ms" }} />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-500" style={{ animationDelay: "150ms" }} />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-500" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="border-t border-zinc-800/60 bg-[#08080f]/80 px-4 py-4 backdrop-blur-md">
        <div className="mx-auto flex max-w-2xl items-end gap-2">
          <div className="flex-1 rounded-2xl border border-zinc-700 bg-zinc-900/60 px-4 py-3 focus-within:border-violet-500 focus-within:ring-1 focus-within:ring-violet-500/50 transition">
            <textarea
              ref={textareaRef}
              className="w-full resize-none bg-transparent text-sm text-zinc-100 placeholder-zinc-500 outline-none"
              rows={1}
              placeholder={`Message ${clone?.name || "the clone"}…`}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
            />
          </div>
          <button
            onClick={sendMessage}
            disabled={streaming || !input.trim()}
            className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-violet-600 text-white transition hover:bg-violet-500 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
            </svg>
          </button>
        </div>
        <p className="mt-2 text-center text-xs text-zinc-700">Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  );
}
