/** **رحلةٌ لشخصٍ آخر** (§٦٣-ج/١) — بابُها الواحد في تطبيق الراكب: المفتاحُ، وقنواتُ الدفع بحسب الدافع، وسطرُ الدافع،
 * ورابطُ التتبّع.
 *
 * **مطفأً لا يظهر شيءٌ إطلاقاً** (قاعدةُ `lib/sharing.ts` بعينها): لا خيارٌ معطّلٌ ولا سطرُ «غير متاح». **والرحلةُ القائمةُ
 * تُقرأ من صفّها لا من المفتاح** — `ride.for_other` و`ride.payer` يصلان دائماً، فما طُلب لغيره يبقى كذلك ولو أُطفئ
 * المفتاحُ بعده («الإطفاءُ يمنع الجديد ولا يفكّ القائم»).
 *
 * **ولا قرارَ مالٍ هنا** (§14): الدافعُ يضيّق **ما يُعرض** من قنوات، والخلفيةُ هي التي ترفض ما يخالفه
 * (`payer_method_mismatch`) — فهذا يمنع الوصولَ إلى الرفض لا يستبدله.
 */

import type { CountryConfig, PublicTrack, RidePayer } from "@/api/types";
import { useFeature } from "@/lib/config";
import { channelsFor, usePaymentPreference, type PayableMethod } from "@/lib/payment";
import { useSession } from "@/lib/session";

export function useRideForOther(): boolean {
  const { user } = useSession();
  return useFeature(user?.country_code, "ride_for_other_enabled");
}

/** **القناتان اللتان يدفع بهما الطالبُ في رحلةٍ لغيره** — لا يقف عند السيارة ليدفع نقداً، ولا يحوّل كليك على alias كبتنٍ
 *  لم يركب معه. **ولا باقيَ نقداً من محفظةٍ لا تغطّي** (`cash_remainder=False` في `payments`): الأجرةُ كاملةً أو لا شيء. */
const REQUESTER_METHODS: ReadonlySet<PayableMethod> = new Set(["wallet", "card"]);

/** **أيستطيع الطالبُ أن يدفع في هذه الدولة أصلاً؟** — بلا محفظةٍ ولا بطاقةٍ مفعّلتين يصير «أنا أدفع» وعداً لا بابَ له
 *  بعد الرحلة: كلُّ قناةٍ باقيةٍ ترتدّ ٤٠٩. فيُعطَّل الخيارُ بعلّته، ولا يُترك يُختار ثمّ يُكتشف. */
export function requesterCanPay(country: CountryConfig | null | undefined): boolean {
  return channelsFor(country).some((channel) => REQUESTER_METHODS.has(channel.method));
}

/** **تفضيلُ الدفع مضيَّقاً بالدافع** — `null` رحلةٌ عاديّة فالتفضيلُ كما هو (`usePaymentPreference`).
 *
 *  - `requester` في رحلةٍ لغيره ⇒ **المحفظةُ والبطاقةُ وحدهما**، والمحفوظُ إن كان غيرَهما يُقرأ أوّلَ المتاح منهما.
 *  - `passenger_cash` ⇒ **لا قناةَ أصلاً**: الدفعةُ تفتحها الخلفيةُ عند الإنهاء نقداً، وصاحبُ الحساب لا يختار شيئاً.
 *  - `recipient_cash` (الطرد، §٦٣-ج/٤) ⇒ **مثلُه**: المستلمُ يدفع عند التسليم، وكلُّ قناةٍ من حساب المرسل ترتدّ ٤٠٩.
 *
 *  **ومرسلُ الطردِ الدافعُ لا يُمرَّر هنا** (`payerScope`): هو عند الالتقاط فيدفع بأيِّ قناةٍ كأيِّ رحلة.
 *
 *  **والاختيارُ يُحفظ تفضيلاً كما كان** (`choose`): من اختار البطاقةَ هنا اختارها عن قصد. */
export function usePayerPreference(country: CountryConfig | null | undefined, payer: RidePayer | null) {
  const { available, resolved, choose } = usePaymentPreference(country);
  if (payer === null) return { available, resolved, choose };
  if (payer === "passenger_cash" || payer === "recipient_cash") return { available: [], resolved: null, choose };
  const allowed = available.filter((channel) => REQUESTER_METHODS.has(channel.method));
  return {
    available: allowed,
    resolved: allowed.find((channel) => channel.method === resolved?.method) ?? allowed[0] ?? null,
    choose,
  };
}

/** **ما يضيّق قنواتِ الدفع في هذه الرحلة** — الدافعُ في رحلةٍ لغيره، **ومستلمُ الطرد إن دفع هو**؛ و`null` لكلِّ رحلةٍ
 *  يدفعها صاحبُها كما يشاء — **ومنها طردٌ يدفعه مرسلُه**: هو عند الالتقاط، فلا يُضيَّق عليه شيء. */
export function payerScope(ride: { for_other: boolean; payer: RidePayer }): RidePayer | null {
  if (ride.for_other) return ride.payer;
  return ride.payer === "recipient_cash" ? ride.payer : null;
}

/** **سطرُ الدافع على الرحلة الجارية** — يقول لصاحب الحساب ما عليه بعد الرحلة قبل أن تنتهي. */
export const PAYER_LINE: Record<RidePayer, string> = {
  requester: "تدفع أنت بعد الرحلة — بالمحفظة أو البطاقة",
  passenger_cash: "يدفع الراكبُ نقداً للكبتن",
  recipient_cash: "يدفع المستلمُ نقداً عند التسليم",
};

/** **رابطُ التتبّع من عنوان التطبيق نفسِه** (`/t/{token}`) — والخلفيةُ لا تكتب نطاقاً يفترق عن مكان التطبيق.
 *
 *  **في المتصفّح وغلافِ أندرويد** العنوانُ هو النطاقُ العامُّ نفسُه (`server.url` في `capacitor.config.ts`) فيصلح رابطاً
 *  يُرسل. **وفي حزمة iOS** الشاشاتُ من داخل الحزمة (`capacitor://localhost`) — ولا نطاقَ عامّاً في التطبيق يُبنى منه،
 *  **فلا رابطَ يُخترع**: `null`، والزرُّ لا يُرسم. رابطٌ إلى عنوانٍ لا يفتحه أحدٌ أسوأُ من لا رابط. */
export function webOrigin(): string | null {
  const { protocol, origin } = window.location;
  return protocol === "https:" || protocol === "http:" ? origin : null;
}

export function trackUrl(token: string): string | null {
  const origin = webOrigin();
  return origin === null ? null : `${origin}/t/${token}`;
}

/** **مشاركةُ الرابط بورقة النظام، والحافظةُ حين لا ورقة** — كـ`shareRide` في `useTrackingSheet`.
 *
 *  وما يعود يقول للشاشة ماذا تقول: النسخُ يُقال بتنبيه (لا شيءَ آخرَ يدلّ عليه)، وورقةُ النظام تقول ما فعلته بنفسها،
 *  **والإغلاقُ بلا مشاركةٍ قرارُ صاحبه** فلا يُقال له شيء. والتعذّرُ يُقال ومعه الرابطُ نفسُه — ينسخه بيده. */
export async function shareTrackLink(url: string): Promise<"shared" | "copied" | "cancelled" | "failed"> {
  const text = `تابع رحلتك مع TAXO: ${url}`;
  if (navigator.share) {
    try {
      await navigator.share({ title: "تتبّع الرحلة · TAXO", text });
      return "shared";
    } catch (error) {
      if ((error as Error)?.name === "AbortError") return "cancelled";
      // ورقةٌ رُفضت لا أُلغيت (إذنٌ أو سياقٌ غيرُ آمن) — فالحافظةُ بعدها
    }
  }
  try {
    await navigator.clipboard.writeText(text);
    return "copied";
  } catch {
    return "failed";
  }
}

/** **حالُ الرحلة لمن يتابعها** — جملةٌ لكلِّ حال، ولا رقمَ ولا وقتَ لا مصدرَ له. */
export const PUBLIC_STATE_LINE: Record<PublicTrack["state"], string> = {
  searching: "نبحث عن كبتن…",
  coming: "الكبتن في الطريق",
  arrived: "الكبتن وصل",
  riding: "في الطريق إلى الوجهة",
  ended: "انتهت الرحلة",
};

/** **الموقعُ في خرائط قوقل** — حين لا خريطةَ في الصفحة (لا توكن خرائط منشور). */
export function mapsUrl(position: { lat: number; lng: number }): string {
  return `https://www.google.com/maps?q=${position.lat},${position.lng}`;
}
