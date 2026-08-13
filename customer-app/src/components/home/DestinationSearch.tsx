/** بحث الوجهة بالـ Geocoding — **مكمّلٌ للدبوس لا بديلٌ عنه** (القسم 11.3).
 *
 * لذلك زرُّ «حدّدها على الخريطة» ظاهرٌ دائماً بجانب النتائج، ولا يعتمد شيءٌ
 * هنا على نجاح البحث: عنوانٌ لم يُعثر عليه لا يمنع رحلة.
 *
 * **والأماكنُ المحفوظة والوجهاتُ الأخيرة تظهران قبل الكتابة وتختفيان بعدها**
 * (`FUTURE-FEATURES` بند 1 و2): من فتح الورقة ليذهب إلى بيته لا يكتب، ومن
 * بدأ يكتب لا يريد قائمةً تزاحم نتائجه.
 */

import { Briefcase, Clock, House, Loader2, MapPin, Navigation, Search, Star } from "lucide-react";
import { useEffect, useState } from "react";

import type { CountryCode, Coordinates } from "@/api/types";
import { DrawerSheet } from "@/components/ui/Sheet";
import { EmptyState } from "@/components/ui/Feedback";
import { searchPlaces, type Place } from "@/lib/geocode";
import { usePlaces } from "@/lib/places";

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
  const { places, recents } = usePlaces();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Place[]>([]);
  const [searching, setSearching] = useState(false);
  const typing = query.trim().length >= 2;

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
      <div className="space-y-16 pb-24">
        <div className="relative">
          <Search className="pointer-events-none absolute inset-y-0 start-12 my-auto size-20 text-muted" />
          <input
            autoFocus
            className="field ps-44"
            placeholder="ابحث عن عنوان أو معلم"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          {searching ? (
            <Loader2 className="absolute inset-y-0 end-12 my-auto size-20 animate-spin text-muted" />
          ) : null}
        </div>

        <button
          type="button"
          onClick={() => {
            onOpenChange(false);
            onPickOnMap();
          }}
          className="pressable flex w-full items-center gap-12 rounded-12 border border-line bg-surface px-16 py-12 text-start transition hover:bg-surface-2"
        >
          <Navigation className="size-20 text-brand" />
          <span className="font-medium text-ink">حدّدها على الخريطة بالدبوس</span>
        </button>

        {!typing && places.length > 0 ? (
          <section>
            <p className="mb-8 text-12 text-muted">أماكن محفوظة</p>
            <ul className="space-y-4">
              {places.map((place) => (
                <li key={place.id}>
                  <button
                    type="button"
                    onClick={() => {
                      onPick({
                        id: `place:${place.id}`,
                        name: place.label,
                        address: place.address ?? "",
                        coordinates: { lat: place.lat, lng: place.lng },
                      });
                      onOpenChange(false);
                    }}
                    className="pressable flex w-full items-start gap-12 rounded-12 px-12 py-12 text-start transition hover:bg-surface-2"
                  >
                    <PlaceIconMark icon={place.icon} />
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-ink">
                        {place.label}
                      </span>
                      {place.address ? (
                        <span className="block truncate text-14 text-muted">
                          {place.address}
                        </span>
                      ) : null}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {!typing && recents.length > 0 ? (
          <section>
            <p className="mb-8 text-12 text-muted">وجهات أخيرة</p>
            <ul className="space-y-4">
              {recents.map((recent) => (
                <li key={recent.key}>
                  <button
                    type="button"
                    onClick={() => {
                      onPick({
                        id: `recent:${recent.key}`,
                        name: recent.address,
                        address: "",
                        coordinates: recent.point,
                      });
                      onOpenChange(false);
                    }}
                    className="pressable flex w-full items-start gap-12 rounded-12 px-12 py-12 text-start transition hover:bg-surface-2"
                  >
                    <Clock className="mt-2 size-20 shrink-0 text-muted" />
                    {/* سطرٌ واحدٌ كاملاً — تفكيكُ العنوان إلى مكانٍ ومنطقة
                        تخمينٌ يخطئ على ما لا يشبه المثال (البند 2) */}
                    <span className="min-w-0 truncate font-medium text-ink">
                      {recent.address}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <ul className="space-y-4">
          {results.map((place) => (
            <li key={place.id}>
              <button
                type="button"
                onClick={() => {
                  onPick(place);
                  onOpenChange(false);
                }}
                className="pressable flex w-full items-start gap-12 rounded-12 px-12 py-12 text-start transition hover:bg-surface-2"
              >
                <MapPin className="mt-2 size-20 shrink-0 text-muted" />
                <span className="min-w-0">
                  <span className="block truncate font-medium text-ink">{place.name}</span>
                  {place.address ? (
                    <span className="block truncate text-14 text-muted">{place.address}</span>
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
          <p className="text-14 text-muted">
            البحث بالعناوين غير متاح الآن — حدّد الوجهة على الخريطة.
          </p>
        ) : null}
      </div>
    </DrawerSheet>
  );
}

/** أيقونةُ المكان — و**المجهولُ نجمة** لا فراغ: نوعٌ جديد في الخلفية يظهر
 * بشكلٍ محايد بدل أن يختفي الصف. */
function PlaceIconMark({ icon }: { icon: string }) {
  const Mark = icon === "home" ? House : icon === "work" ? Briefcase : Star;
  return <Mark className="mt-2 size-20 shrink-0 text-brand" />;
}
