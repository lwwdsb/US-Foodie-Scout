"use client";
import { RestaurantCard } from "./RestaurantCard";
import type { ChatMessage, Language } from "@/lib/types";

interface Props {
  message: ChatMessage;
  lang: Language;
  selectedCardName?: string | null;
  onCardSelect?: (name: string) => void;
}

export function MessageBubble({ message, lang, selectedCardName, onCardSelect }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-2.5 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      {/* Avatar */}
      <div
        className={`w-7 h-7 rounded-full shrink-0 flex items-center justify-center text-xs ${
          isUser
            ? "bg-gradient-to-br from-blue-500 to-indigo-600 text-white"
            : "bg-gradient-to-br from-orange-400 to-rose-500 text-white"
        }`}
      >
        {isUser ? "你" : "🕵️"}
      </div>

      {/* Content */}
      <div className={`max-w-[85%] space-y-2 ${isUser ? "items-end" : "items-start"} flex flex-col`}>
        {/* Text bubble */}
        {message.content && (
          <div
            className={`px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
              isUser
                ? "bg-blue-600 text-white rounded-tr-sm"
                : "bg-white border border-gray-200 text-gray-800 rounded-tl-sm shadow-sm"
            }`}
          >
            {message.content}
            {message.isStreaming && (
              <span className="inline-block w-0.5 h-4 bg-current ml-0.5 animate-pulse" />
            )}
          </div>
        )}

        {/* Restaurant Cards */}
        {message.recommendations && message.recommendations.length > 0 && (
          <div className="w-full space-y-2">
            {message.recommendations.map((card, i) => (
              <RestaurantCard
                key={card.name}
                card={card}
                lang={lang}
                index={i + 1}
                isSelected={selectedCardName === card.name}
                onSelect={onCardSelect}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
