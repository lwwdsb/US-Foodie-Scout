"use client";
import { useState } from "react";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { MapPanel } from "@/components/map/MapPanel";
import { LanguageToggle } from "@/components/layout/LanguageToggle";
import { useSession } from "@/hooks/useSession";
import { useChat } from "@/hooks/useChat";
import type { Language } from "@/lib/types";

type MobileTab = "chat" | "map";

export default function Home() {
  const [lang, setLang] = useState<Language>("zh");
  const [selectedCardName, setSelectedCardName] = useState<string | null>(null);
  const [mobileTab, setMobileTab] = useState<MobileTab>("chat");
  const { sessionId } = useSession();
  const { messages, isLoading, latestCards, sendMessage, clearChat } = useChat(sessionId);

  const handleCardSelect = (name: string) => {
    const next = selectedCardName === name ? null : name;
    setSelectedCardName(next);
    // Auto-switch to map on mobile so the user sees the pin immediately
    if (next) setMobileTab("map");
  };

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      {/* Top bar */}
      <header className="h-10 bg-white border-b border-gray-200 flex items-center justify-between px-4 shrink-0 z-10">
        <div className="flex items-center gap-2">
          <span className="text-base">🕵️</span>
          <span className="text-sm font-semibold text-gray-700">
            {lang === "zh" ? "北美华人美食侦探" : "US Foodie Scout"}
          </span>
          <span className="text-xs text-gray-400 hidden sm:inline">· SGV</span>
        </div>
        <LanguageToggle lang={lang} onChange={setLang} />
      </header>

      {/* Dual-pane layout */}
      <main className="flex-1 flex overflow-hidden min-h-0">
        {/* Chat — always rendered; hidden on mobile when map tab is active */}
        <div
          className={`w-full lg:w-[420px] lg:border-r border-gray-200 flex-col shrink-0
            ${mobileTab === "chat" ? "flex" : "hidden"} lg:flex`}
        >
          <ChatPanel
            messages={messages}
            isLoading={isLoading}
            lang={lang}
            onSend={sendMessage}
            onClear={clearChat}
            selectedCardName={selectedCardName}
            onCardSelect={handleCardSelect}
          />
        </div>

        {/* Map — always rendered; hidden on mobile when chat tab is active.
            Keeping it mounted avoids Leaflet re-initialization on every tab switch. */}
        <div
          className={`flex-1 ${mobileTab === "map" ? "flex" : "hidden"} lg:flex`}
        >
          <MapPanel
            cards={latestCards}
            lang={lang}
            selectedCardName={selectedCardName}
            onCardSelect={handleCardSelect}
            isVisible={mobileTab === "map"}
          />
        </div>
      </main>

      {/* Bottom tab bar — mobile only */}
      <nav className="lg:hidden flex border-t border-gray-200 bg-white shrink-0 safe-area-pb">
        <button
          onClick={() => setMobileTab("chat")}
          className={`flex-1 py-3 flex flex-col items-center gap-0.5 text-xs font-medium transition-colors
            ${mobileTab === "chat" ? "text-blue-600" : "text-gray-400 hover:text-gray-600"}`}
        >
          <span className="text-xl leading-none">💬</span>
          <span>{lang === "zh" ? "聊天" : "Chat"}</span>
        </button>

        <button
          onClick={() => setMobileTab("map")}
          className={`flex-1 py-3 flex flex-col items-center gap-0.5 text-xs font-medium transition-colors relative
            ${mobileTab === "map" ? "text-blue-600" : "text-gray-400 hover:text-gray-600"}`}
        >
          <span className="text-xl leading-none">🗺️</span>
          <span>{lang === "zh" ? "地图" : "Map"}</span>
          {/* Badge: how many restaurants are on the map */}
          {latestCards.length > 0 && (
            <span className="absolute top-2 right-[calc(50%-20px)] min-w-[18px] h-[18px] bg-blue-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1">
              {latestCards.length}
            </span>
          )}
        </button>
      </nav>
    </div>
  );
}
