"use client";
import { useRef, useEffect, useState, type KeyboardEvent } from "react";
import { MessageBubble } from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";
import type { ChatMessage, Language } from "@/lib/types";
import { t } from "@/lib/i18n";

interface Props {
  messages: ChatMessage[];
  isLoading: boolean;
  lang: Language;
  onSend: (text: string, budget?: string, cuisine?: string) => void;
  onClear: () => void;
  selectedCardName?: string | null;
  onCardSelect?: (name: string) => void;
}

export function ChatPanel({ messages, isLoading, lang, onSend, onClear, selectedCardName, onCardSelect }: Props) {
  const tr = t(lang);
  const [input, setInput] = useState("");
  const [budget, setBudget] = useState("");
  const [cuisine, setCuisine] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || isLoading) return;
    onSend(text, budget || undefined, cuisine || undefined);
    setInput("");
  };

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // e.nativeEvent.isComposing: true while IME (Chinese/Japanese/Korean) is composing
    // a character — Enter during composition should confirm the word, not submit.
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="px-4 py-3 bg-white border-b border-gray-200 flex items-center justify-between shrink-0">
        <div>
          <h1 className="font-bold text-gray-900 text-base">{tr.appName}</h1>
          <p className="text-xs text-gray-400">{tr.tagline}</p>
        </div>
        <button
          onClick={onClear}
          className="text-xs text-gray-400 hover:text-gray-600 transition-colors px-2 py-1 rounded hover:bg-gray-100"
        >
          {tr.clearChat}
        </button>
      </div>

      {/* Messages — native scroll for reliability */}
      <div className="flex-1 overflow-y-auto px-4 py-4 min-h-0">
        <div className="space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-400 text-sm mt-12 space-y-2">
              <div className="text-4xl">🕵️</div>
              <p className="font-medium">{tr.appName}</p>
              <p className="text-xs">{tr.tagline}</p>
            </div>
          )}
          {messages.map((m) => (
            <MessageBubble
              key={m.id}
              message={m}
              lang={lang}
              selectedCardName={selectedCardName}
              onCardSelect={onCardSelect}
            />
          ))}
          {isLoading && <TypingIndicator lang={lang} />}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="px-4 py-3 bg-white border-t border-gray-200 space-y-2 shrink-0">
        {/* Budget + Cuisine selectors */}
        <div className="flex gap-2">
          <select
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
            className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white text-gray-600 flex-1 focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            {tr.budgetOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <input
            value={cuisine}
            onChange={(e) => setCuisine(e.target.value)}
            placeholder={lang === "zh" ? "菜系（选填）" : "Cuisine (optional)"}
            className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 flex-1 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </div>

        {/* Message input */}
        <div className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder={tr.placeholder}
            rows={2}
            disabled={isLoading}
            className="flex-1 resize-none text-sm border border-gray-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50 bg-white"
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="bg-blue-600 text-white text-sm px-4 py-2 rounded-xl hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0 h-[58px]"
          >
            {tr.send}
          </button>
        </div>
      </div>
    </div>
  );
}
