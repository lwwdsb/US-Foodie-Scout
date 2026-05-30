export type PriceLevel = "$" | "$$" | "$$$" | "$$$$";

export type AuthenticityTag =
  | "华人必打卡"
  | "隐藏宝藏"
  | "网红店慎入"
  | "普通推荐"
  | "网络口碑";

export interface RestaurantCard {
  name: string;
  name_zh: string | null;
  address: string;
  lat: number;
  lng: number;
  google_score: number;
  xhs_score: number;
  price_level: PriceLevel;
  authenticity_tag: AuthenticityTag;
  cuisine_type: string;
  google_maps_url: string;
  xhs_post_count: number;
  photo_url: string | null;
  highlight: string | null;
  xhs_source?: "batch" | "web_search" | "none";
}

export type SSEChunk =
  | { type: "text"; content: string }
  | { type: "recommendations"; content: RestaurantCard[] }
  | { type: "done" }
  | { type: "error"; content: string };

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  recommendations?: RestaurantCard[];
  isStreaming?: boolean;
  timestamp: Date;
}

export type Language = "zh" | "en";

export const TAG_CONFIG: Record<
  AuthenticityTag,
  { emoji: string; color: string; label_zh: string; label_en: string }
> = {
  华人必打卡: {
    emoji: "🔥",
    color: "bg-red-100 text-red-700 border-red-200",
    label_zh: "华人必打卡",
    label_en: "Must Visit",
  },
  隐藏宝藏: {
    emoji: "💎",
    color: "bg-blue-100 text-blue-700 border-blue-200",
    label_zh: "隐藏宝藏",
    label_en: "Hidden Gem",
  },
  网红店慎入: {
    emoji: "⚠️",
    color: "bg-yellow-100 text-yellow-700 border-yellow-200",
    label_zh: "网红店慎入",
    label_en: "Tourist Trap",
  },
  普通推荐: {
    emoji: "⭐",
    color: "bg-gray-100 text-gray-600 border-gray-200",
    label_zh: "普通推荐",
    label_en: "General Pick",
  },
  网络口碑: {
    emoji: "🔍",
    color: "bg-purple-100 text-purple-700 border-purple-200",
    label_zh: "网络口碑",
    label_en: "Web Sentiment",
  },
};
