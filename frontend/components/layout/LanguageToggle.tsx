"use client";
import type { Language } from "@/lib/types";

interface Props {
  lang: Language;
  onChange: (lang: Language) => void;
}

export function LanguageToggle({ lang, onChange }: Props) {
  return (
    <div className="flex items-center gap-0.5 bg-gray-100 rounded-lg p-0.5 text-xs">
      {(["zh", "en"] as Language[]).map((l) => (
        <button
          key={l}
          onClick={() => onChange(l)}
          className={`px-2.5 py-1 rounded-md font-medium transition-all ${
            lang === l
              ? "bg-white text-gray-900 shadow-sm"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          {l === "zh" ? "中文" : "EN"}
        </button>
      ))}
    </div>
  );
}
