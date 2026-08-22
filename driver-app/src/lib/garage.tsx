/** كراجُ الكبتن — **مقروءٌ مرةً ويقرؤه الجميع** (2026-08-22).
 *
 * ثلاثةُ قرّاءٍ لجوابٍ واحد: علامتُه على الخريطة (الرئيسية)، وورقةُ الاحتفال
 * بهديّة أول اشتراك، وشاشةُ «مركباتي». **وثلاثةُ نداءاتٍ لجوابٍ واحدٍ تفترق**
 * — يبدّل المركبةَ في الكراج فتبقى القديمةُ على الخريطة حتى تُعاد الشاشة.
 *
 * **والتبديلُ متفائلٌ ويعود عند الرفض**: الخريطةُ تنعكس تحت الإصبع، ثم يُعاد
 * قراءةُ الكراج من بابه الواحد — فلا يُبنى شيءٌ على شكلِ ردٍّ لم يُجمَّد في
 * العقد (`PUT /vehicle-skins/active` يعلن مدخلَه ولا يعلن مخرجَه).
 *
 * **ومطفأً — أو للكبتن غيرِ المعتمد — لا شيءَ يُعرض ولا خطأٌ يُقال**: فشلُ
 * القراءة يعني «لا كراج»، وهي حالٌ صحيحةٌ لا عطب.
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

import { getGarage, markSkinSeen, setActiveSkin } from "@/api/endpoints";
import type { Garage, VehicleSkin } from "@/api/types";
import { useFeature } from "@/lib/config";
import { useSession } from "@/lib/session";

interface GarageState {
  /** **مفتاحُ السوق** — يقرؤه «حسابي» فلا يرسم صفّاً إلى بابٍ مغلق. */
  enabled: boolean;
  garage: Garage | null;
  loading: boolean;
  /** المركبةُ المفعَّلة — **مشتقّةٌ من الكراج لا محفوظةٌ ثانيةً**. */
  activeSkin: VehicleSkin | null;
  refresh: () => Promise<void>;
  activate: (skinId: string) => Promise<void>;
  /** يُختم أنها عُرضت — **قبل الإغلاق** فلا تُعرض ثانيةً إن تعثّر النداء. */
  celebrated: (skinId: string) => Promise<void>;
}

const GarageContext = createContext<GarageState>({
  enabled: false,
  garage: null,
  loading: true,
  activeSkin: null,
  refresh: async () => undefined,
  activate: async () => undefined,
  celebrated: async () => undefined,
});

export function GarageProvider({ children }: { children: ReactNode }) {
  const { user } = useSession();
  /** **خلف مفتاحه ويُشحن مطفأً** (`vehicle_skins_enabled`): مطفأً ترفض
   *  الخلفيةُ الأبوابَ الثلاثة بخطأٍ مسمّى — **فلا يُطرق بابٌ أصلاً**، ولا
   *  يبتلع التطبيقُ ٤٠٣ في كلِّ فتحة. ومطفأً لا كراجَ ولا مركبةَ على
   *  الخريطة ولا صفَّ في «حسابي»: قاعدةُ `women_service_enabled` نفسُها —
   *  المفتاحُ يحجب **ما تحته** لا الشاشةَ وحدَها. */
  const enabled = useFeature(user?.country_code, "vehicle_skins_enabled");
  const [garage, setGarage] = useState<Garage | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    try {
      setGarage(await getGarage());
    } catch {
      // **لا يُمحى كراجٌ قائمٌ بنداءٍ متعثّر** — درسُ `lib/driver.tsx`: نداءٌ
      // واحدٌ يفشل كان يترك الكبتنَ أمام شاشةٍ لا تنتهي
      /* يبقى ما كان */
    }
  }, [enabled]);

  // **بالمُعرِّف لا بالكائن**: `user` كائنٌ جديدٌ مع كلِّ تحديثِ جلسة
  const userId = user?.id ?? null;
  useEffect(() => {
    if (!userId || !enabled) {
      setGarage(null);
      return;
    }
    setLoading(true);
    getGarage()
      .then(setGarage)
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [userId, enabled]);

  const activate = useCallback(
    async (skinId: string) => {
      const before = garage;
      if (before) {
        setGarage({
          ...before,
          active_skin_id: skinId,
          skins: before.skins.map((skin) => ({
            ...skin,
            active: skin.id === skinId,
          })),
        });
      }
      try {
        await setActiveSkin(skinId);
      } catch (caught) {
        // **يعود إلى ما كان ثم يُرمى**: علامةٌ تبقى مبدَّلةً بعد رفضٍ تكذب
        if (before) setGarage(before);
        throw caught;
      }
      await refresh();
    },
    [garage, refresh],
  );

  const celebrated = useCallback(
    async (skinId: string) => {
      setGarage((current) =>
        current === null ? current : { ...current, celebrate: null },
      );
      await markSkinSeen(skinId).catch(() => undefined);
    },
    [],
  );

  const activeSkin = useMemo(
    () =>
      garage?.skins.find((skin) => skin.id === garage.active_skin_id) ?? null,
    [garage],
  );

  const value = useMemo<GarageState>(
    () => ({ enabled, garage, loading, activeSkin, refresh, activate, celebrated }),
    [enabled, garage, loading, activeSkin, refresh, activate, celebrated],
  );

  return (
    <GarageContext.Provider value={value}>{children}</GarageContext.Provider>
  );
}

export function useGarage() {
  return useContext(GarageContext);
}
