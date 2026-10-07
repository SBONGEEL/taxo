/** **الحجزُ المضمون عند الكبتن** (SPEC §٦٣-ج/٣) — مفتاحُه ومدخلُه في الرئيسية.
 *
 * **ومطفأً لا يُرسم شيءٌ ولا يُسأل باب**: المفتاحُ يُقرأ من `/config` قبل أيِّ نداء، فرئيسيةُ سوقٍ لم تُشعَل فيه الخدمةُ لا
 * تطرق «عروضٌ تنتظرك» في كلِّ فتحة. **والخلفيةُ تحرس نفسَها على كلِّ حال** — تردّ قائمةً فارغةً حيث الخدمةُ مطفأةٌ أو رسمُها صفر.
 */

import { useEffect, useState } from "react";

import { listGuaranteeOffers, listMyGuarantees } from "@/api/endpoints";
import { useFeature } from "@/lib/config";
import { useSession } from "@/lib/session";

export function useGuarantees(): boolean {
  const { user } = useSession();
  return useFeature(user?.country_code, "guaranteed_booking_enabled");
}

/** **ما يقوله مدخلُ الرئيسية** — عددُ العروض، وعددُ ما قبله، **وأيُّها يُسأل الآن «هل أنت في الطريق؟»**.
 *
 * و`null` حيث المفتاحُ مطفأٌ أو لم يُقرأ بعد أو لا شيءَ في القائمتين — **فلا مدخلَ فارغٌ يُرسم**. وتعثّرُ القراءة صمتٌ لا شاشةُ
 * خطأ: المدخلُ إضافةٌ على الرئيسية، والصفحةُ نفسُها تقول خطأها إن فُتحت. */
export interface GuaranteeEntry {
  offers: number;
  upcoming: number;
  asking: boolean;
}

export function useGuaranteeEntry(active: boolean): GuaranteeEntry | null {
  const enabled = useGuarantees();
  const [entry, setEntry] = useState<GuaranteeEntry | null>(null);

  useEffect(() => {
    if (!enabled || !active) return;
    let cancelled = false;
    void Promise.all([listGuaranteeOffers(), listMyGuarantees()])
      .then(([offers, mine]) => {
        if (cancelled) return;
        setEntry(
          offers.length + mine.length === 0
            ? null
            : {
                offers: offers.length,
                upcoming: mine.length,
                asking: mine.some((booking) => booking.confirm_requested),
              },
        );
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [enabled, active]);

  return enabled ? entry : null;
}
