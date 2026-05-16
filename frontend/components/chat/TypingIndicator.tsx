"use client";
import type { Language } from "@/lib/types";
import { t } from "@/lib/i18n";

export function TypingIndicator({ lang }: { lang: Language }) {
  return (
    <div className="flex items-center gap-3 px-1">
      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-orange-400 to-rose-500 flex items-center justify-center text-white text-xs shrink-0">
        🕵️
      </div>
      <div className="flex items-center gap-1.5 bg-white border border-gray-200 rounded-2xl px-3 py-2.5 shadow-sm">
        <span className="text-xs text-gray-500">{t(lang).thinking}</span>
        <span className="flex gap-0.5 ml-1">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-1.5 h-1.5 bg-orange-400 rounded-full animate-bounce"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </span>
      </div>
    </div>
  );
}
