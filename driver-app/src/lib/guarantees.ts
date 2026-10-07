/** **الحجزُ المضمون عند الكبتن** (SPEC §٦٣-ج/٣) — مفتاحُه ومدخلُه في الرئيسية. **والمشوارُ الثابتُ أخوه** (§٦٣-ج/٦، آخرَ الملف):
 * اشتراكُ راكبٍ تُولَّد رحلاتُه حجوزاً يأخذها كبتنُه المعتمد — **قبولٌ مسبقٌ كقبول الحجز المضمون**، وبيتُه بيتُه.
 *
 * **ومطفأً لا يُرسم شيءٌ ولا يُسأل باب**: المفتاحُ يُقرأ من `/config` قبل أيِّ نداء، فرئيسيةُ سوقٍ لم تُشعَل فيه الخدمةُ لا
 * تطرق «عروضٌ تنتظرك» في كلِّ فتحة. **والخلفيةُ تحرس نفسَها على كلِّ حال** — تردّ قائمةً فارغةً حيث الخدمةُ مطفأةٌ أو رسمُها صفر.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  approveCommute,
  listCommuteOffers,
  listGuaranteeOffers,
  listMyCommutes,
  listMyGuarantees,
  releaseCommute,
} from "@/api/endpoints";
import type { CommuteOffer } from "@/api/types";
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

// ═══════════════════════════════════════════════════════════ المشوارُ الثابت (§٦٣-ج/٦)
//
// **المفتاحُ يحكم العروضَ وحدَها، و«مشاويرُك» تُقرأ ولو أُطفئ**: اشتراكٌ اعتمده قائمٌ يكمل شهرَه (مالُ راكبه محفوظ)، **وكبتنٌ لا
// يرى ما اعتمده لا يعرف أن رحلاتِه تنتظره**. والخلفيةُ تردّ العروضَ فارغةً حيث الخدمةُ مطفأةٌ أو خصمُها صفر على أيِّ حال.

export function useCommutes(): boolean {
  const { user } = useSession();
  return useFeature(user?.country_code, "rider_subscription_enabled");
}

/** **ما يقوله مدخلُ الرئيسية** — عددُ العروض وعددُ ما اعتمده. و`null` حين لا شيءَ في القائمتين — **فلا مدخلَ فارغٌ يُرسم** —
 *  وتعثّرُ القراءة صمتٌ كمدخل الحجوز: الصفحةُ نفسُها تقول خطأها إن فُتحت. **والعروضُ لا تُسأل مطفأةً**: جوابُها فارغٌ سلفاً. */
export interface CommuteEntry {
  offers: number;
  mine: number;
}

export function useCommuteEntry(active: boolean): CommuteEntry | null {
  const enabled = useCommutes();
  const [entry, setEntry] = useState<CommuteEntry | null>(null);

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    void Promise.all([enabled ? listCommuteOffers() : Promise.resolve<CommuteOffer[]>([]), listMyCommutes()])
      .then(([offers, mine]) => {
        if (cancelled) return;
        setEntry(offers.length + mine.length === 0 ? null : { offers: offers.length, mine: mine.length });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [enabled, active]);

  return entry;
}

/** **صفحةُ «مشاويرُ ثابتة»** — القائمتان، **وكلُّ فعلٍ يعيد القائمتين** (العرضُ المعتمَدُ ينتقل إلى «مشاويرُك»)، **وجوابُه تحت
 *  بطاقته** لا في رأس الصفحة. **ورفضُ «اعتمد» نهائيٌّ حين سبقه غيرُه** (٤٠٩ «اعتمد هذا المشوارَ كبتنٌ آخر») — فلا يُعاد بضغطةٍ
 *  ثانية؛ ورسائلُ الخلفية كما ردّتها، لا نصَّ يُخترع مكانَها. */
export function useCommuteBoard() {
  const enabled = useCommutes();
  const [lists, setLists] = useState<{ offers: CommuteOffer[]; mine: CommuteOffer[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, { tone: "ok" | "danger"; text: string; final: boolean }>>({});

  const load = useCallback(async () => {
    const [offers, mine] = await Promise.all([enabled ? listCommuteOffers() : Promise.resolve<CommuteOffer[]>([]), listMyCommutes()]);
    setLists({ offers, mine });
  }, [enabled]);

  useEffect(() => {
    load().catch((caught: unknown) =>
      setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة المشاوير الثابتة"),
    );
  }, [load]);

  const run = useCallback(
    async (row: CommuteOffer, call: () => Promise<unknown>, done: string) => {
      setBusy(row.id);
      setNotes((current) => {
        const next = { ...current };
        delete next[row.id];
        return next;
      });
      try {
        await call();
        setNotes((current) => ({ ...current, [row.id]: { tone: "ok", text: done, final: false } }));
        await load();
      } catch (caught) {
        setNotes((current) => ({
          ...current,
          [row.id]: {
            tone: "danger",
            text: caught instanceof ApiError ? caught.message : "تعذّر الإرسال — حاول ثانية",
            // **٤٠٩ على عرضٍ مفتوحٍ يعني أن غيرَه سبقه** — أو أنه غيرُ مشترك؛ والزرُّ بعدهما يَعِد بما لا يقع
            final: caught instanceof ApiError && caught.status === 409,
          },
        }));
      } finally {
        setBusy(null);
      }
    },
    [load],
  );

  return {
    enabled,
    lists,
    error,
    busy,
    notes,
    approve: (row: CommuteOffer) =>
      void run(row, () => approveCommute(row.id), "اعتمدتَ المشوار — تصلك رحلاتُه قبل موعدها حين تكون متصلاً ومتاحاً."),
    release: (row: CommuteOffer) =>
      void run(row, () => releaseCommute(row.id), "اعتذرتَ عن المشوار — عاد مفتوحاً لكبتنٍ معتمدٍ آخر."),
  };
}
