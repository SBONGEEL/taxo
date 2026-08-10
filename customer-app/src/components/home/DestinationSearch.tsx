/** بحث الوجهة بالـ Geocoding — **مكمّلٌ للدبوس لا بديلٌ عنه** (القسم 11.3).
 *
 * لذلك زرُّ «حدّدها على الخريطة» ظاهرٌ دائماً بجانب النتائج، ولا يعتمد شيءٌ
 * هنا على نجاح البحث: عنوانٌ لم يُعثر عليه لا يمنع رحلة.
 */

import { Loader2, MapPin, Navigation, Search } from "lucide-react";
import { useEffect, useState } from "react";

import type { CountryCode, Coordinates } from "@/api/types";
import { DrawerSheet } from "@/components/ui/Sheet";
import { EmptyState } from "@/components/ui/Feedback";
import { searchPlaces, type Place } from "@/lib/geocode";

const DEBOUNCE_MS = 350;

export function DestinationSearch({
  open,
  onOpenChange,
  token,
  country,
  near,
  onPick,
  onPickOnMap,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  token: string | null;
  country: CountryCode;
  near: Coordinates | null;
  onPick: (place: Place) => void;
  onPickOnMap: () => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Place[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setResults([]);
      return;
    }
  }, [open]);

  useEffect(() => {
    if (!token || query.trim().length < 2) {
      setResults([]);
      return;
    }

    const controller = new AbortController();
    setSearching(true);
    const timer = window.setTimeout(async () => {
      const found = await searchPlaces(
        token,
        query,
        country,
        near ?? undefined,
        controller.signal,
      );
      setResults(found);
      setSearching(false);
    }, DEBOUNCE_MS);

    return () => {
      controller.abort();
      window.clearTimeout(timer);
      setSearching(false);
    };
  }, [query, token, country, near]);

  return (
    <DrawerSheet open={open} onOpenChange={onOpenChange} title="إلى أين؟">
      <div className="space-y-4 pb-6">
        <div className="relative">
          <Search className="pointer-events-none absolute inset-y-0 start-3 my-auto size-5 text-muted" />
          <input
            autoFocus
            className="field ps-11"
            placeholder="ابحث عن عنوان أو معلم"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          {searching ? (
            <Loader2 className="absolute inset-y-0 end-3 my-auto size-5 animate-spin text-muted" />
          ) : null}
        </div>

        <button
          type="button"
          onClick={() => {
            onOpenChange(false);
            onPickOnMap();
          }}
          className="flex w-full items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3 text-start transition hover:bg-line/30"
        >
          <Navigation className="size-5 text-brand" />
          <span className="font-medium text-ink">حدّدها على الخريطة بالدبوس</span>
        </button>

        <ul className="space-y-1">
          {results.map((place) => (
            <li key={place.id}>
              <button
                type="button"
                onClick={() => {
                  onPick(place);
                  onOpenChange(false);
                }}
                className="flex w-full items-start gap-3 rounded-xl px-3 py-3 text-start transition hover:bg-line/30"
              >
                <MapPin className="mt-0.5 size-5 shrink-0 text-muted" />
                <span className="min-w-0">
                  <span className="block truncate font-medium text-ink">{place.name}</span>
                  {place.address ? (
                    <span className="block truncate text-sm text-muted">{place.address}</span>
                  ) : null}
                </span>
              </button>
            </li>
          ))}
        </ul>

        {!searching && query.trim().length >= 2 && results.length === 0 ? (
          <EmptyState
            title="لا نتائج لهذا البحث"
            hint="جرّب اسماً أقصر، أو حدّد الوجهة على الخريطة"
          />
        ) : null}

        {!token ? (
          <p className="text-sm text-muted">
            البحث بالعناوين غير متاح الآن — حدّد الوجهة على الخريطة.
          </p>
        ) : null}
      </div>
    </DrawerSheet>
  );
}
