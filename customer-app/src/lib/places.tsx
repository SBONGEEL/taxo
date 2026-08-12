/** الأماكن المحفوظة والوجهات الأخيرة — مصدرٌ واحد لثلاث شاشات.
 *
 * تُقرأ في الرئيسية (اختصاران)، وفي ورقة البحث (قسمان)، وفي صفحة الأماكن.
 * ولو قرأت كلُّ شاشةٍ بنفسها لاختلفت القوائم بعد أول إضافة، ولنُودي الخادمُ
 * ثلاثَ مرات لفتحةٍ واحدة.
 *
 * **والوجهاتُ الأخيرة مشتقّةٌ من `GET /rides/me` بلا جدول** (`FUTURE-FEATURES`
 * بند 2): العنوانُ والإحداثيات في `RideOut` أصلاً. والتصميمُ يعرضها باسمِ
 * مكانٍ ومنطقةٍ منفصلتين (`دوار الداخلية` / `عمّان`) وهو تفكيكٌ لا يعطيه
 * العنوانُ المخزَّن كسلسلةٍ واحدة — **فتُعرض في سطرٍ واحدٍ كاملاً**، وهو ما
 * أجازه البند صراحةً. تفكيكُه في الواجهة تخمينٌ يخطئ على عناوين لا تشبه
 * المثال.
 *
 * **والمكرَّرُ يُطوى**: من ذهب إلى بيته عشر مرات لا يريد عشرة صفوف — والمفتاح
 * الإحداثيات مقرَّبةً، لا نصُّ العنوان: نفس النقطة قد يصفها Geocoding بنصّين.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

import { listPlaces, listMyRides } from "@/api/endpoints";
import type { Coordinates, SavedPlace } from "@/api/types";
import { useSession } from "@/lib/session";

export interface RecentDestination {
  key: string;
  address: string;
  point: Coordinates;
}

/** كم وجهةً أخيرة تُعرض — أربعةٌ كما في التصميم، وما فوقها لا يُقرأ. */
const RECENT_LIMIT = 4;

/** دقّةُ الطيّ: ~11 متراً. أقلُّ منها يفصل نقطتين في مبنى واحد. */
function pointKey(point: Coordinates): string {
  return `${point.lat.toFixed(4)},${point.lng.toFixed(4)}`;
}

interface PlacesState {
  places: SavedPlace[];
  recents: RecentDestination[];
  loading: boolean;
  refresh: () => Promise<void>;
}

const PlacesContext = createContext<PlacesState>({
  places: [],
  recents: [],
  loading: false,
  refresh: async () => undefined,
});

export function PlacesProvider({ children }: { children: ReactNode }) {
  const { user } = useSession();
  const [places, setPlaces] = useState<SavedPlace[]>([]);
  const [recents, setRecents] = useState<RecentDestination[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!user) {
      setPlaces([]);
      setRecents([]);
      return;
    }
    setLoading(true);
    try {
      // **لا يسقط أحدُهما بسقوط الآخر**: قائمةُ الأماكن لا علاقة لها بسجل
      // الرحلات، وفشلٌ في أحدهما لا يجوز أن يُفرغ الآخر من الشاشة
      const [saved_, rides] = await Promise.allSettled([
        listPlaces(),
        listMyRides(20, 0),
      ]);

      if (saved_.status === "fulfilled") setPlaces(saved_.value);

      if (rides.status === "fulfilled") {
        // **ما صار مكاناً محفوظاً يخرج من «الأخيرة»**: عرضُ الوجهة نفسها في
        // قسمين من ورقةٍ واحدة يجعل القائمة أطول بلا خيارٍ إضافي — والمحفوظُ
        // أعلى وأوضح لأن له اسماً
        const saved = new Set(
          (saved_.status === "fulfilled" ? saved_.value : []).map((place) =>
            pointKey({ lat: place.lat, lng: place.lng }),
          ),
        );
        const seen = new Set<string>();
        const found: RecentDestination[] = [];
        for (const { ride } of rides.value) {
          const key = pointKey(ride.dropoff);
          if (seen.has(key) || saved.has(key)) continue;
          seen.add(key);
          found.push({
            key,
            address: ride.dropoff_address ?? "نقطة على الخريطة",
            point: ride.dropoff,
          });
          if (found.length === RECENT_LIMIT) break;
        }
        setRecents(found);
      }
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<PlacesState>(
    () => ({ places, recents, loading, refresh }),
    [places, recents, loading, refresh],
  );

  return (
    <PlacesContext.Provider value={value}>{children}</PlacesContext.Provider>
  );
}

export function usePlaces() {
  return useContext(PlacesContext);
}
