/** بحث الوجهة بالـ Geocoding — TAXO 2.0 «R29d» (`design/t2-new/rider/R29d-destination-search.dc.html`)، **في المظهرين
 *  والنسائيّ** — **مكمّلٌ للدبوس لا بديلٌ عنه** (القسم 11.3).
 *
 * لذلك زرُّ «حدّدها على الخريطة» ظاهرٌ دائماً بجانب النتائج، ولا يعتمد شيءٌ
 * هنا على نجاح البحث: عنوانٌ لم يُعثر عليه لا يمنع رحلة.
 *
 * **والأماكنُ المحفوظة والوجهاتُ الأخيرة تظهران قبل الكتابة وتختفيان بعدها**
 * (`FUTURE-FEATURES` بند 1 و2): من فتح الورقة ليذهب إلى بيته لا يكتب، ومن
 * بدأ يكتب لا يريد قائمةً تزاحم نتائجه.
 *
 * **والسلوكُ سلوكُ الورقة القائمة بعينه** (`DrawerT2` فوق `vaul` كما كانت): البحثُ بمهلته، والاختيارُ، والدبوس — **وما تغيّر
 * الوجهُ وحدَه**: ورقةُ R06–R09، وحقلُ R13 بأيقونته، والمحفوظُ والأخيرةُ صفوفاً في بطاقةٍ تحت عنوانٍ كـ R14.
 */

import { useEffect, useState } from "react";

import type { CountryCode, Coordinates } from "@/api/types";
import { searchPlaces, type Place } from "@/lib/geocode";
import { usePlaces } from "@/lib/places";
import { DrawerT2 } from "@/screens/t2/DrawerT2";
import { BlankT2, LoaderT2 } from "@/screens/t2/KitT2";
import { Icon } from "@/taxo2";

import "@/screens/t2/t2.css";
import "@/screens/t2/request.css";

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
    <DrawerT2 open={open} onOpenChange={onOpenChange} title="إلى أين؟">
      <label className="t2-dest-field">
        <Icon name="search" />
        <input
          autoFocus
          placeholder="ابحث عن عنوان أو معلم"
          aria-label="ابحث عن عنوان أو معلم"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        {searching ? <LoaderT2 small /> : null}
      </label>

      <button
        type="button"
        onClick={() => {
          onOpenChange(false);
          onPickOnMap();
        }}
        className="t2-dest-pin"
      >
        <Icon name="location_on" fill />
        <span className="t2-dest-pin-label">حدّدها على الخريطة بالدبوس</span>
        <Icon name="chevron_left" className="t2-chev" />
      </button>

      {!typing && places.length > 0 ? (
        <section>
          <div className="t2-group t2-dest-group">أماكن محفوظة</div>
          <div className="t2-list">
            {places.map((place) => (
              <button
                key={place.id}
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
                className="t2-dest-row"
              >
                <Icon name={placeIcon(place.icon)} fill className="mark" />
                <span className="t2-dest-main">
                  <span className="t2-dest-title">{place.label}</span>
                  {place.address ? <span className="t2-dest-sub">{place.address}</span> : null}
                </span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {!typing && recents.length > 0 ? (
        <section>
          <div className="t2-group t2-dest-group">وجهات أخيرة</div>
          <div className="t2-list">
            {recents.map((recent) => (
              <button
                key={recent.key}
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
                className="t2-dest-row"
              >
                <Icon name="schedule" />
                {/* سطرٌ واحدٌ كاملاً — تفكيكُ العنوان إلى مكانٍ ومنطقة
                    تخمينٌ يخطئ على ما لا يشبه المثال (البند 2) */}
                <span className="t2-dest-main">
                  <span className="t2-dest-title">{recent.address}</span>
                </span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {results.length > 0 ? (
        <div className="t2-list t2-dest-results">
          {results.map((place) => (
            <button
              key={place.id}
              type="button"
              onClick={() => {
                onPick(place);
                onOpenChange(false);
              }}
              className="t2-dest-row"
            >
              <Icon name="location_on" />
              <span className="t2-dest-main">
                <span className="t2-dest-title">{place.name}</span>
                {place.address ? <span className="t2-dest-sub">{place.address}</span> : null}
              </span>
            </button>
          ))}
        </div>
      ) : null}

      {!searching && query.trim().length >= 2 && results.length === 0 ? (
        <BlankT2 icon="search" title="لا نتائج لهذا البحث" hint="جرّب اسماً أقصر، أو حدّد الوجهة على الخريطة" />
      ) : null}

      {!token ? <p className="t2-note t2-dest-note">البحث بالعناوين غير متاح الآن — حدّد الوجهة على الخريطة.</p> : null}
    </DrawerT2>
  );
}

/** أيقونةُ المكان — و**المجهولُ نجمة** لا فراغ: نوعٌ جديد في الخلفية يظهر
 * بشكلٍ محايد بدل أن يختفي الصف. */
function placeIcon(icon: string): string {
  return icon === "home" ? "home" : icon === "work" ? "work" : "star";
}
