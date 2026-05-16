"use client";
import { useState, useCallback, useRef } from "react";
import { v4 as uuidv4 } from "uuid";
import { streamChat, clearSession } from "@/lib/api";
import type { ChatMessage, RestaurantCard } from "@/lib/types";

export function useChat(sessionId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [latestCards, setLatestCards] = useState<RestaurantCard[]>([]);
  const isLoadingRef = useRef(false);

  const sendMessage = useCallback(
    async (text: string, budget?: string, cuisine?: string) => {
      if (!text.trim() || !sessionId || isLoadingRef.current) return;

      const userMsg: ChatMessage = {
        id: uuidv4(),
        role: "user",
        content: text,
        timestamp: new Date(),
      };

      const assistantId = uuidv4();
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        isStreaming: true,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      isLoadingRef.current = true;
      setIsLoading(true);

      try {
        for await (const chunk of streamChat({
          message: text,
          sessionId,
          budget,
          cuisine,
        })) {
          if (chunk.type === "text") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: m.content + chunk.content }
                  : m
              )
            );
          } else if (chunk.type === "recommendations") {
            setLatestCards(chunk.content);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, recommendations: chunk.content }
                  : m
              )
            );
          } else if (chunk.type === "done") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, isStreaming: false } : m
              )
            );
          } else if (chunk.type === "error") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: `⚠️ ${chunk.content}`, isStreaming: false }
                  : m
              )
            );
          }
        }
      } finally {
        isLoadingRef.current = false;
        setIsLoading(false);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, isStreaming: false } : m
          )
        );
      }
    },
    [sessionId]
  );

  const clearChat = useCallback(async () => {
    setMessages([]);
    setLatestCards([]);
    if (sessionId) await clearSession(sessionId);
  }, [sessionId]);

  return { messages, isLoading, latestCards, sendMessage, clearChat };
}
