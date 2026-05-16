"use client";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { TAG_CONFIG } from "@/lib/types";
import type { RestaurantCard as TRestaurantCard, Language } from "@/lib/types";
import { t } from "@/lib/i18n";

interface Props {
  card: TRestaurantCard;
  lang: Language;
  index: number;
  isSelected?: boolean;
  onSelect?: (name: string) => void;
}

function ScoreBar({ score, color }: { score: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="text-xs font-semibold w-8 text-right">{Math.round(score)}</span>
    </div>
  );
}

export function RestaurantCard({ card, lang, index, isSelected, onSelect }: Props) {
  const tr = t(lang);
  const cfg = TAG_CONFIG[card.authenticity_tag];

  return (
    <div
      onClick={() => onSelect?.(card.name)}
      className={`rounded-xl border bg-white overflow-hidden transition-all cursor-pointer
        ${isSelected
          ? "border-blue-500 shadow-lg shadow-blue-100 ring-2 ring-blue-400 ring-offset-1"
          : "border-gray-200 shadow-sm hover:shadow-md hover:border-gray-300"
        }`}
    >
      {/* Photo */}
      {card.photo_url && (
        <div className="w-full h-32 overflow-hidden bg-gray-100">
          <img
            src={card.photo_url}
            alt={card.name}
            className="w-full h-full object-cover"
            onError={(e) => {
              const wrapper = e.currentTarget.parentElement;
              if (wrapper) wrapper.style.display = "none";
            }}
          />
        </div>
      )}

      {/* Header */}
      <div className="px-4 pt-3 pb-2 flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-gray-400 font-mono">#{index}</span>
            <h3 className="font-semibold text-gray-900 text-sm leading-tight">
              {card.name_zh ?? card.name}
            </h3>
          </div>
          {card.name_zh && (
            <p className="text-xs text-gray-400 mt-0.5">{card.name}</p>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {isSelected && (
            <span className="text-xs bg-blue-600 text-white px-1.5 py-0.5 rounded-md font-medium">
              📍
            </span>
          )}
          <Badge
            variant="outline"
            className={`text-xs whitespace-nowrap ${cfg.color}`}
          >
            {cfg.emoji} {lang === "zh" ? cfg.label_zh : cfg.label_en}
          </Badge>
        </div>
      </div>

      <Separator />

      {/* Scores */}
      <div className="px-4 py-2.5 space-y-1.5">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className="w-16 shrink-0">{tr.googleScore}</span>
          <ScoreBar score={card.google_score} color="bg-blue-400" />
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className="w-16 shrink-0">{tr.xhsScore}</span>
          <ScoreBar score={card.xhs_score} color="bg-rose-400" />
        </div>
      </div>

      {/* Meta */}
      <div className="px-4 pb-2 flex flex-wrap gap-1.5">
        <Badge variant="secondary" className="text-xs">{card.price_level}</Badge>
        <Badge variant="secondary" className="text-xs">{card.cuisine_type}</Badge>
        {card.xhs_post_count > 0 && (
          <Badge variant="secondary" className="text-xs">
            {lang === "zh" ? "小红书" : "XHS"} {card.xhs_post_count} {tr.posts}
          </Badge>
        )}
      </div>

      {card.highlight && (
        <div className="px-4 pb-2.5">
          <p className="text-xs text-gray-500 italic line-clamp-1">
            💬 {card.highlight}
          </p>
        </div>
      )}

      {/* Address + CTA */}
      <div className="px-4 pb-3 pt-1 border-t border-gray-100 flex items-center justify-between gap-2">
        <p className="text-xs text-gray-400 truncate">{card.address}</p>
        <a
          href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(card.name + " " + card.address)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 text-xs bg-blue-600 text-white px-2.5 py-1 rounded-lg hover:bg-blue-700 transition-colors"
        >
          {tr.navigate} →
        </a>
      </div>
    </div>
  );
}
