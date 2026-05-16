import type { Language } from "./types";

export const t = (lang: Language) => ({
  appName: lang === "zh" ? "北美华人美食侦探" : "US Foodie Scout",
  tagline:
    lang === "zh"
      ? "专为洛杉矶华人社区打造"
      : "Built for the LA Chinese Community",
  placeholder:
    lang === "zh"
      ? "推荐SGV正宗粤菜，人均100以内..."
      : "Find authentic dim sum in SGV, budget $$...",
  send: lang === "zh" ? "发送" : "Send",
  thinking: lang === "zh" ? "美食侦探正在搜索..." : "Scouting restaurants...",
  budget: lang === "zh" ? "预算" : "Budget",
  cuisine: lang === "zh" ? "菜系" : "Cuisine",
  googleScore: lang === "zh" ? "Google评分" : "Google",
  xhsScore: lang === "zh" ? "小红书" : "XHS",
  navigate: lang === "zh" ? "导航" : "Navigate",
  posts: lang === "zh" ? "篇笔记" : "posts",
  clearChat: lang === "zh" ? "清空对话" : "Clear Chat",
  mapTitle: lang === "zh" ? "餐厅地图" : "Restaurant Map",
  noResults: lang === "zh" ? "暂无推荐结果" : "No results yet",
  errorMsg: lang === "zh" ? "请求失败，请重试" : "Request failed, please retry",
  budgetOptions: [
    { value: "", label: lang === "zh" ? "不限预算" : "Any budget" },
    { value: "$", label: lang === "zh" ? "$ 人均50以内" : "$ Under $15" },
    { value: "$$", label: lang === "zh" ? "$$ 人均50-100" : "$$ $15–30" },
    { value: "$$$", label: lang === "zh" ? "$$$ 人均100-200" : "$$$ $30–60" },
    { value: "$$$$", label: lang === "zh" ? "$$$$ 人均200+" : "$$$$ $60+" },
  ],
});
