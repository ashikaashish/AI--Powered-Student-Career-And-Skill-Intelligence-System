import { useEffect, useRef, useState } from "react";
import { Send, Bot, Trash2 } from "lucide-react";
import client from "../api/client";
import { Layout, PageHeader } from "../components/Layout";

const STARTER_SUGGESTIONS = [
  "What career is best for me?",
  "What should I learn next?",
  "Show me a roadmap",
  "Which courses should I take?",
  "How am I doing?",
  "What are the highest paying careers?",
  "Resume tips",
  "What can you do?",
];

const WELCOME = {
  sender: "bot",
  text: "Hi! I'm your AI Career Assistant. I can suggest careers, find your skill gaps, build a roadmap, recommend courses, compare roles and more. What would you like to know?",
};

export default function Chatbot() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [suggestions, setSuggestions] = useState(STARTER_SUGGESTIONS);
  const endRef = useRef(null);

  useEffect(() => {
    client
      .get("/chatbot/history")
      .then((res) => {
        setMessages(res.data.length ? res.data.map((m) => ({ sender: m.sender, text: m.message })) : [WELCOME]);
      })
      .catch(() => setMessages([WELCOME]));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const send = async (text) => {
    const message = (text ?? input).trim();
    if (!message || sending) return;
    setMessages((m) => [...m, { sender: "user", text: message }]);
    setInput("");
    setSending(true);
    try {
      const res = await client.post("/chatbot/message", { message });
      setMessages((m) => [...m, { sender: "bot", text: res.data.reply }]);
      setSuggestions(res.data.suggestions?.length ? res.data.suggestions : STARTER_SUGGESTIONS);
    } catch {
      setMessages((m) => [...m, { sender: "bot", text: "Sorry, I couldn't reach the server. Please try again." }]);
    } finally {
      setSending(false);
    }
  };

  const clearChat = async () => {
    if (!window.confirm("Clear this conversation?")) return;
    try {
      await client.post("/chatbot/clear");
    } catch {
      /* keep the local reset even if the request fails */
    }
    setMessages([WELCOME]);
    setSuggestions(STARTER_SUGGESTIONS);
  };

  return (
    <Layout>
      <PageHeader title="AI Career Assistant" subtitle="Ask me anything about careers, skills, and learning!" />

      <div className="bg-white rounded-3xl border border-slate-100 shadow-card flex flex-col h-[70vh]">
        <div className="px-6 pt-4 flex justify-end">
          <button
            onClick={clearChat}
            className="text-xs text-slate-400 hover:text-red-500 flex items-center gap-1"
            title="Clear conversation"
          >
            <Trash2 size={13} /> Clear chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 pb-4 pt-2 space-y-4">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.sender === "user" ? "justify-end" : "justify-start"}`}>
              {m.sender === "bot" && (
                <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center mr-2 shrink-0">
                  <Bot size={16} className="text-primary-600" />
                </div>
              )}
              <div
                className={`max-w-[75%] px-4 py-2.5 rounded-3xl text-sm whitespace-pre-line ${
                  m.sender === "user"
                    ? "bg-primary-600 text-white rounded-br-sm"
                    : "bg-slate-50 text-slate-700 rounded-bl-sm"
                }`}
              >
                {m.text}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex justify-start">
              <div className="bg-slate-50 text-slate-400 text-sm px-4 py-2.5 rounded-3xl rounded-bl-sm">
                Thinking...
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        <div className="px-6 pb-3 flex flex-wrap gap-2">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              disabled={sending}
              className="text-xs font-medium bg-primary-50 text-primary-700 px-3 py-1.5 rounded-full hover:bg-primary-100 disabled:opacity-60"
            >
              {s}
            </button>
          ))}
        </div>

        <div className="p-4 border-t border-slate-100 flex items-center gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Type your message..."
            maxLength={500}
            className="flex-1 rounded-full border border-slate-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <button
            onClick={() => send()}
            disabled={sending}
            className="w-10 h-10 rounded-full bg-primary-600 hover:bg-primary-700 text-white flex items-center justify-center shrink-0 disabled:opacity-60"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </Layout>
  );
}