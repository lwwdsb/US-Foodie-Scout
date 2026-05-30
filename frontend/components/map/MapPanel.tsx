"use client";
import { useState, useEffect } from "react";
import {
  APIProvider,
  Map,
  AdvancedMarker,
  InfoWindow,
  useMap,
} from "@vis.gl/react-google-maps";
import type { RestaurantCard, Language } from "@/lib/types";
import { TAG_CONFIG } from "@/lib/types";
import { t } from "@/lib/i18n";

const SGV_CENTER = { lat: 34.0953, lng: -118.1347 };
const MAPS_KEY = process.env.NEXT_PUBLIC_GOOGLE_MAPS_KEY ?? "";
const MAP_ID = process.env.NEXT_PUBLIC_GOOGLE_MAPS_ID ?? "DEMO_MAP_ID";

// Must live inside <Map> to call useMap()
function MapController({
  cards,
  selectedCardName,
}: {
  cards: RestaurantCard[];
  selectedCardName?: string | null;
}) {
  const map = useMap();

  // Fit bounds whenever cards change
  useEffect(() => {
    if (!map) return;
    if (cards.length === 0) {
      map.setCenter(SGV_CENTER);
      map.setZoom(12);
      return;
    }
    const bounds = new window.google.maps.LatLngBounds();
    cards.forEach((c) => bounds.extend({ lat: c.lat, lng: c.lng }));
    map.fitBounds(bounds, 60);
  }, [map, cards]);

  // Pan + zoom when a card is selected from the list
  useEffect(() => {
    if (!map || !selectedCardName) return;
    const card = cards.find((c) => c.name === selectedCardName);
    if (card) {
      map.panTo({ lat: card.lat, lng: card.lng });
      map.setZoom(16);
    }
  }, [map, selectedCardName, cards]);

  return null;
}

interface Props {
  cards: RestaurantCard[];
  lang: Language;
  selectedCardName?: string | null;
  onCardSelect?: (name: string) => void;
  isVisible?: boolean;
}

export function MapPanel({ cards, lang, selectedCardName, onCardSelect }: Props) {
  const tr = t(lang);
  const [activeCard, setActiveCard] = useState<RestaurantCard | null>(null);

  // Sync external card selection → open its info window
  useEffect(() => {
    setActiveCard(
      selectedCardName ? (cards.find((c) => c.name === selectedCardName) ?? null) : null
    );
  }, [selectedCardName, cards]);

  return (
    <div className="flex flex-col h-full w-full bg-white">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 shrink-0 flex items-center justify-between">
        <h2 className="font-semibold text-gray-800 text-sm">{tr.mapTitle}</h2>
        {cards.length > 0 && (
          <span className="text-xs text-gray-400">
            {lang === "zh" ? `共 ${cards.length} 家餐厅` : `${cards.length} restaurants`}
          </span>
        )}
      </div>

      {/* Map */}
      <div className="relative flex-1 w-full">
        <APIProvider apiKey={MAPS_KEY}>
          <div className="absolute inset-0">
            <Map
              defaultCenter={SGV_CENTER}
              defaultZoom={12}
              mapId={MAP_ID}
              gestureHandling="greedy"
              disableDefaultUI={false}
              style={{ width: "100%", height: "100%" }}
            >
              <MapController cards={cards} selectedCardName={selectedCardName} />

              {cards.map((card, i) => {
                const cfg = TAG_CONFIG[card.authenticity_tag];
                const isActive = activeCard?.name === card.name;

                return (
                  <AdvancedMarker
                    key={card.name}
                    position={{ lat: card.lat, lng: card.lng }}
                    onClick={() => {
                      const next = isActive ? null : card;
                      setActiveCard(next);
                      if (next) onCardSelect?.(card.name);
                    }}
                  >
                    {/* Custom pin: 32×48 container, pin tip at bottom-center */}
                    <div style={{ position: "relative", width: 32, height: 48, cursor: "pointer" }}>
                      {/* Number badge at top */}
                      <div style={{
                        position: "absolute", top: 0, left: "50%",
                        transform: "translateX(-50%)",
                        background: isActive ? "#dc2626" : "#1d4ed8",
                        color: "white", borderRadius: 10,
                        fontSize: 10, fontWeight: "bold",
                        padding: "0 5px", lineHeight: "16px",
                        whiteSpace: "nowrap", zIndex: 1,
                      }}>
                        #{i + 1}
                      </div>
                      {/* Diamond pin body at bottom */}
                      <div style={{
                        position: "absolute", bottom: 0, left: 0,
                        width: 32, height: 32,
                        background: "white",
                        border: `2.5px solid ${isActive ? "#dc2626" : "#3b82f6"}`,
                        borderRadius: "50% 50% 50% 0",
                        transform: "rotate(-45deg)",
                        boxShadow: "0 2px 8px rgba(0,0,0,0.25)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                      }}>
                        <span style={{ transform: "rotate(45deg)", fontSize: 14 }}>
                          {cfg.emoji}
                        </span>
                      </div>
                    </div>
                  </AdvancedMarker>
                );
              })}

              {activeCard && (
                <InfoWindow
                  position={{ lat: activeCard.lat, lng: activeCard.lng }}
                  onCloseClick={() => setActiveCard(null)}
                >
                  <div style={{ minWidth: 180, fontFamily: "system-ui", padding: "2px 4px" }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#111827" }}>
                      {activeCard.name_zh ?? activeCard.name}
                    </div>
                    {activeCard.name_zh && (
                      <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>
                        {activeCard.name}
                      </div>
                    )}
                    <div style={{ fontSize: 11, color: "#6b7280", marginTop: 4 }}>
                      {activeCard.address}
                    </div>
                    <div style={{ marginTop: 6, display: "flex", gap: 8, fontSize: 11 }}>
                      <span>🔵 Google <b>{Math.round(activeCard.google_score)}</b></span>
                      {activeCard.xhs_source !== "web_search" && (
                        <span>🌸 小红书 <b>{Math.round(activeCard.xhs_score)}</b></span>
                      )}
                    </div>
                    <div style={{ marginTop: 6 }}>
                      <span style={{
                        fontSize: 11, padding: "2px 6px", borderRadius: 9999,
                        background: "#fee2e2", color: "#b91c1c",
                      }}>
                        {TAG_CONFIG[activeCard.authenticity_tag].emoji}{" "}
                        {TAG_CONFIG[activeCard.authenticity_tag].label_zh}
                      </span>
                    </div>
                    <a
                      href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
                        activeCard.name + " " + activeCard.address
                      )}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: "block", marginTop: 8, textAlign: "center",
                        background: "#2563eb", color: "white", borderRadius: 6,
                        padding: "4px 8px", fontSize: 11, textDecoration: "none",
                      }}
                    >
                      导航 →
                    </a>
                  </div>
                </InfoWindow>
              )}
            </Map>
          </div>
        </APIProvider>
      </div>
    </div>
  );
}
