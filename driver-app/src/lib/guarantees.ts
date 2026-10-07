/** **الحجزُ المضمون عند الكبتن** (SPEC §٦٣-ج/٣) — مفتاحُه ومدخلُه في الرئيسية. **والمشوارُ الثابتُ أخوه** (§٦٣-ج/٦):
 * اشتراكُ راكبٍ تُولَّد رحلاتُه حجوزاً يأخذها كبتنُه المعتمد — **قبولٌ مسبقٌ كقبول الحجز المضمون**، وبيتُه بيتُه. **و«بين المدن»
 * ثالثُهما** (§٦٣-ج/٧، آخرَ الملف): رحلةٌ يعلنها لموعدٍ قادمٍ ويُحجز فيها مسبقاً — عملٌ مجدولٌ كأخويه، وبيتُه هنا.
 *
 * **ومطفأً لا يُرسم شيءٌ ولا يُسأل باب**: المفتاحُ يُقرأ من `/config` قبل أيِّ نداء، فرئيسيةُ سوقٍ لم تُشعَل فيه الخدمةُ لا
 * تطرق «عروضٌ تنتظرك» في كلِّ فتحة. **والخلفيةُ تحرس نفسَها على كلِّ حال** — تردّ قائمةً فارغةً حيث الخدمةُ مطفأةٌ أو رسمُها صفر.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  approveCommute,
  cancelIntercityTrip,
  completeIntercityTrip,
  departIntercityTrip,
  listCommuteOffers,
  listGuaranteeOffers,
  listIntercityRoutes,
  listMyCommutes,
  listMyGuarantees,
  listMyIntercityTrips,
  postIntercityTrip,
  releaseCommute,
} from "@/api/endpoints";
import type { CommuteOffer, IntercityRoute, IntercityTrip } from "@/api/types";
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

// ═══════════════════════════════════════════════════════════ بين المدن (§٦٣-ج/٧)
//
// **المفتاحُ يحكم الإعلانَ وحدَه، و«رحلاتُك» تُقرأ ولو أُطفئ**: رحلةٌ أعلنها وحُجز فيها قائمةٌ تكمل — **وكبتنٌ لا يرى رحلتَه لا يعرف
// أن ركّاباً ينتظرونه في نقطة التجمّع**. والمالكُ يراجع القانونَ قبل الإشعال، فمطفأً لا مدخلَ لمن لا رحلةَ له.
//
// **ولا مالَ يُحسب هنا** (§14): سعرا المقعد والسيارة يُجمَّدان من المسار في الخلفية لحظةَ الإعلان، **وأجرتُه تُقيَّد هناك عند
// الإنهاء**. وما يُعدّ هنا مقاعد.

export function useIntercity(): boolean {
  const { user } = useSession();
  return useFeature(user?.country_code, "intercity_enabled");
}

/** **رحلةٌ لم تنتهِ** — مفتوحةٌ تنتظر موعدَها، أو انطلقت ولم يُنهِها. */
const isLive = (trip: IntercityTrip) => trip.status === "open" || trip.status === "departed";

/** **ما يقوله مدخلُ الرئيسية** — كم رحلةً له لم تنتهِ (وصفرٌ يعني دعوةً إلى الإعلان في سوقٍ مشتعل). و`null` حين تُطفأ الخدمةُ ولا
 *  رحلةَ قائمةً له — **فلا مدخلَ لما لا يُفعل**. وتعثّرُ القراءة صمتٌ كأخويه: الصفحةُ نفسُها تقول خطأها إن فُتحت. */
export interface IntercityEntry {
  live: number;
}

export function useIntercityEntry(active: boolean): IntercityEntry | null {
  const enabled = useIntercity();
  const [live, setLive] = useState(0);

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    listMyIntercityTrips()
      .then((trips) => {
        if (!cancelled) setLive(trips.filter(isLive).length);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [active]);

  return enabled || live > 0 ? { live } : null;
}

/** **أفعالُ الرحلة الثلاثة** — أبوابُ الخلفية بأسمائها. **ومفاتيحُ كائنٍ لا اتحادٌ مسمّى**: `check:enums` يقرأ كلَّ `type X = "…"`
 *  مرآةً لتعداد، وهذه أفعالٌ لا قيمُ عمود. */
const INTERCITY_ACTIONS = {
  cancel: { call: cancelIntercityTrip, done: "أُلغيت الرحلة — وعاد إلى كلِّ راكبٍ مالُه كاملاً." },
  depart: { call: departIntercityTrip, done: "انطلقتَ — أرقامُ ركّابك تحت أسمائهم." },
  complete: { call: completeIntercityTrip, done: "أنهيتَ الرحلة — أجرتُها في كشف محفظتك." },
};
type IntercityAction = keyof typeof INTERCITY_ACTIONS;

/** **صفحةُ «بين المدن»** — المساراتُ (للإعلان، خلف المفتاح) ورحلاتُه، **وكلُّ فعلٍ يعيد الرحلةَ من الخلفية فتُستبدل في مكانها**
 *  وجوابُه تحت بطاقتها. **ورسائلُ الرفض كما ردّتها الخلفية** — التصريحُ الناقص، والمهلةُ التي فاتت، والرحلةُ بلا حجز. */
export function useIntercityBoard() {
  const enabled = useIntercity();
  const [routes, setRoutes] = useState<IntercityRoute[] | null>(null);
  const [trips, setTrips] = useState<IntercityTrip[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, { tone: "ok" | "danger"; text: string }>>({});
  const [posting, setPosting] = useState<{ tone: "ok" | "danger"; text: string } | null>(null);

  const load = useCallback(async () => {
    const [nextRoutes, nextTrips] = await Promise.all([
      enabled ? listIntercityRoutes() : Promise.resolve<IntercityRoute[]>([]),
      listMyIntercityTrips(),
    ]);
    setRoutes(nextRoutes);
    setTrips(nextTrips);
  }, [enabled]);

  useEffect(() => {
    load().catch((caught: unknown) =>
      setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة رحلات بين المدن"),
    );
  }, [load]);

  /** **الإعلان** — `departs_at` لحظةٌ بمنطقتها (`toISOString`) فلا تُقرأ بساعتين خطأً، **والسعران يُجمَّدان هناك**. */
  const post = useCallback(
    async (body: { route_id: string; departs_at: string; seats: number; min_seats: number }) => {
      setBusy("post");
      setPosting(null);
      try {
        await postIntercityTrip(body);
        setPosting({ tone: "ok", text: "أعلنتَ رحلتك — تظهر للركّاب في سوقك حتى موعدها." });
        await load();
        return true;
      } catch (caught) {
        setPosting({ tone: "danger", text: caught instanceof ApiError ? caught.message : "تعذّر الإعلان — حاول ثانية" });
        return false;
      } finally {
        setBusy(null);
      }
    },
    [load],
  );

  const act = useCallback(async (trip: IntercityTrip, kind: IntercityAction) => {
    const { call, done } = INTERCITY_ACTIONS[kind];
    setBusy(trip.id);
    setNotes((current) => {
      const next = { ...current };
      delete next[trip.id];
      return next;
    });
    try {
      const next = await call(trip.id);
      setTrips((current) => (current ?? []).map((item) => (item.id === next.id ? next : item)));
      setNotes((current) => ({ ...current, [trip.id]: { tone: "ok", text: done } }));
    } catch (caught) {
      const text = caught instanceof ApiError ? caught.message : "تعذّر الإرسال — حاول ثانية";
      setNotes((current) => ({ ...current, [trip.id]: { tone: "danger", text } }));
    } finally {
      setBusy(null);
    }
  }, []);

  return {
    enabled,
    routes,
    trips,
    error,
    busy,
    notes,
    posting,
    post,
    act: (trip: IntercityTrip, kind: IntercityAction) => void act(trip, kind),
  };
}
