"use client";
import { useEffect, useRef, useState } from "react";
import type { RestaurantCard, Language } from "@/lib/types";
import { TAG_CONFIG } from "@/lib/types";
import { t } from "@/lib/i18n";

interface Props {
  cards: RestaurantCard[];
  lang: Language;
  selectedCardName?: string | null;
  onCardSelect?: (name: string) => void;
  isVisible?: boolean;
}

// SGV center coordinates
const SGV_CENTER: [number, number] = [34.0953, -118.1347];
const DEFAULT_ZOOM = 12;

export function MapPanel({ cards, lang, selectedCardName, onCardSelect, isVisible }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const leafletMapRef = useRef<import("leaflet").Map | null>(null);
  const markersRef = useRef<import("leaflet").Marker[]>([]);
  // name → marker lookup for flyTo
  const markerByNameRef = useRef<Map<string, import("leaflet").Marker>>(new Map());
  const initStartedRef = useRef(false);
  // true once Leaflet has created the map — triggers markers effect after deferred init
  const [mapReady, setMapReady] = useState(false);
  const tr = t(lang);

  useEffect(() => {
    if (!mapRef.current) return;
    const container = mapRef.current;

    const init = () => {
      if (container.offsetWidth === 0 || container.offsetHeight === 0) return;
      if (initStartedRef.current) return;   // sync guard — set before async
      initStartedRef.current = true;

      import("leaflet").then((L) => {
        // Check again after async — StrictMode double-invocation safety
        if (leafletMapRef.current) return;

        delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
        L.Icon.Default.mergeOptions({
          iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
          iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
          shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
        });

        const map = L.map(container, { zoomControl: true }).setView(SGV_CENTER, DEFAULT_ZOOM);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          maxZoom: 19,
        }).addTo(map);

        leafletMapRef.current = map;
        setMapReady(true);
        setTimeout(() => map.invalidateSize(), 150);
        setTimeout(() => map.invalidateSize(), 600);
      });
    };

    const ro = new ResizeObserver(() => {
      if (container.offsetHeight > 0) {
        ro.disconnect();
        init();
      }
    });
    ro.observe(container);
    init();

    return () => {
      ro.disconnect();
      if (leafletMapRef.current) {
        leafletMapRef.current.remove();
        leafletMapRef.current = null;
      }
      initStartedRef.current = false;
      setMapReady(false);
    };
  }, []);

  // Call invalidateSize whenever the map tab becomes visible again
  useEffect(() => {
    if (isVisible && leafletMapRef.current) {
      setTimeout(() => leafletMapRef.current?.invalidateSize(), 50);
    }
  }, [isVisible]);

  // Update markers when cards change — also re-runs when mapReady flips true,
  // so markers are populated even if cards arrived while the map was hidden.
  useEffect(() => {
    if (!mapReady || !leafletMapRef.current) return;

    import("leaflet").then((L) => {
      const map = leafletMapRef.current!;

      // Clear old markers
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      markerByNameRef.current.clear();

      if (cards.length === 0) {
        map.setView(SGV_CENTER, DEFAULT_ZOOM);
        return;
      }

      const bounds: [number, number][] = [];

      cards.forEach((card, i) => {
        const cfg = TAG_CONFIG[card.authenticity_tag];

        // Custom colored icon using div
        const icon = L.divIcon({
          className: "",
          html: `
            <div style="
              background: white;
              border: 2px solid #3b82f6;
              border-radius: 50% 50% 50% 0;
              transform: rotate(-45deg);
              width: 32px; height: 32px;
              display: flex; align-items: center; justify-content: center;
              box-shadow: 0 2px 6px rgba(0,0,0,0.25);
            ">
              <span style="transform: rotate(45deg); font-size: 14px;">${cfg.emoji}</span>
            </div>
            <div style="
              position: absolute; top: -8px; left: 50%; transform: translateX(-50%);
              background: #1d4ed8; color: white; border-radius: 10px;
              font-size: 10px; font-weight: bold; padding: 0 5px;
              white-space: nowrap;
            ">#${i + 1}</div>
          `,
          iconSize: [32, 40],
          iconAnchor: [16, 40],
          popupAnchor: [0, -42],
        });

        const marker = L.marker([card.lat, card.lng], { icon })
          .addTo(map)
          .bindPopup(`
            <div style="min-width: 180px; font-family: system-ui;">
              <strong style="font-size: 13px;">${card.name_zh ?? card.name}</strong>
              <div style="margin-top: 4px; font-size: 11px; color: #6b7280;">${card.address}</div>
              <div style="margin-top: 6px; display: flex; gap: 8px; font-size: 11px;">
                <span>🔵 Google <b>${Math.round(card.google_score)}</b></span>
                <span>🌸 小红书 <b>${Math.round(card.xhs_score)}</b></span>
              </div>
              <div style="margin-top: 6px;">
                <span style="font-size: 11px; padding: 2px 6px; border-radius: 9999px; background: #fee2e2; color: #b91c1c;">
                  ${cfg.emoji} ${cfg.label_zh}
                </span>
              </div>
              <a href="${card.google_maps_url}" target="_blank" style="
                display: block; margin-top: 8px; text-align: center;
                background: #2563eb; color: white; border-radius: 6px;
                padding: 4px 8px; font-size: 11px; text-decoration: none;
              ">导航 →</a>
            </div>
          `);

        markersRef.current.push(marker);
        markerByNameRef.current.set(card.name, marker);
        bounds.push([card.lat, card.lng]);
      });

      // Fit map to show all markers
      if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
      }
    });
  }, [cards, mapReady]);

  // Fly to selected card and open its popup
  useEffect(() => {
    if (!leafletMapRef.current) return;
    const map = leafletMapRef.current;

    if (!selectedCardName) {
      // Deselected — fit all markers back
      if (markersRef.current.length > 0) {
        const bounds = markersRef.current.map((m) => m.getLatLng());
        if (bounds.length > 0) map.fitBounds(bounds.map((b) => [b.lat, b.lng] as [number, number]), { padding: [40, 40], maxZoom: 15 });
      }
      return;
    }

    const marker = markerByNameRef.current.get(selectedCardName);
    if (marker) {
      map.flyTo(marker.getLatLng(), 16, { duration: 0.8 });
      setTimeout(() => marker.openPopup(), 850);
    }
  }, [selectedCardName]);

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
      {/* Map wrapper: relative parent so absolute child fills it correctly */}
      <div className="relative flex-1 w-full">
        <div ref={mapRef} className="absolute inset-0" />
      </div>
    </div>
  );
}
