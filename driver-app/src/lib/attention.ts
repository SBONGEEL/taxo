/** **ما يحتاج انتباهَ الكبتن في رئيسيته** (§٦٢-ج/٤٣، C04) — بيتٌ واحدٌ لسؤالين: «أتحتاج وثائقُه فعلاً؟» و«أمرتفعٌ الطلبُ حوله؟».
 *
 * **والجوابان من الخلفية كما هما**: الوثائقُ من `GET /drivers/me/documents` (ما ينقص وما يُطلب رفعُه والحالُ والانتهاء)، والطلبُ من
 * `GET /drivers/me/demand` (نعم/لا وحدَها). **ولا يُخترع شيء**: فشلُ النداء «لا» — نقطةٌ أو سطرٌ يُرى على باطلٍ أسوأُ من غيابه.
 */

import { useEffect, useState, useSyncExternalStore } from "react";

import {
  confirmPayment,
  disputePayment,
  getDemand,
  getMyUnconfirmedPayments,
  listDocuments,
  objectAutoConfirm,
} from "@/api/endpoints";
import type { CaptainUnconfirmed, DriverDocuments } from "@/api/types";
import { useSession } from "@/lib/session";

/** يومُ الجهاز `YYYY-MM-DD` — **مقارنةُ تاريخين لا مال**؛ وتاريخُ الانتهاء يومٌ تقويميٌّ بلا ساعة. */
function today(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** **أتحتاج وثائقُه فعلاً؟** — مطلوبٌ ناقص · رفعٌ مطلوب · مستندٌ مرفوض · صلاحيةٌ انقضت. */
function documentsNeedAttention(state: DriverDocuments): boolean {
  if (state.missing_required.length > 0 || state.awaiting_upload.length > 0) return true;
  const day = today();
  return state.documents.some(
    (document) =>
      document.review_status === "rejected" || (document.expires_on !== null && document.expires_on < day),
  );
}

/** نقطةُ «الوثائق» — تُقرأ مرّةً عند الفتح، **ومن الطلب نفسِه** الذي تقرأ به شاشةُ المركبة وثائقَها. */
export function useDocumentsAttention(): boolean {
  const [needed, setNeeded] = useState(false);
  useEffect(() => {
    let cancelled = false;
    listDocuments()
      .then((state) => {
        if (!cancelled) setNeeded(documentsNeedAttention(state));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);
  return needed;
}

/** **كلَّ دقيقتين** — الطلبُ حول نقطةٍ لا يتبدّل في ثوانٍ، والسؤالُ يقرأ طلباتِ ربع ساعة. */
const DEMAND_EVERY_MS = 120_000;

/** «الطلب مرتفع حولك» — **ما دام متصلاً في رئيسيته وحدَها**: من لا يستقبل لا طلبَ حوله، ومن في رحلةٍ لا يقرؤه. */
export function useDemandHigh(active: boolean): boolean {
  const [high, setHigh] = useState(false);
  useEffect(() => {
    if (!active) {
      setHigh(false);
      return;
    }
    let cancelled = false;
    const ask = () =>
      getDemand()
        .then((answer) => {
          if (!cancelled) setHigh(answer.high);
        })
        .catch(() => undefined);
    void ask();
    const timer = window.setInterval(ask, DEMAND_EVERY_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [active]);
  return high;
}

// ═══ «ركّابٌ ينتظرون تأكيدك» (`design/PAYMENTS-UNCONFIRMED.md` §٦ · §٧، SPEC §٦٤-ز) ══════════════════════════════════════
//
// **سؤالٌ ثالثٌ من الجنس نفسِه**: ما ينتظر تأكيدَه، **وأمحجوبٌ هو عن الطلبات بسببه** — والجوابُ من الخلفية كما هو (`blocked` شرطُ
// التوزيع نفسُه، `unconfirmed_rules.driver_blocked_clause`)، **فلا يُحسب هنا عددٌ ولا عمر**.

/** **مفتاحُ المسار كلِّه** — مطفأً لا صفحةَ ولا شريطَ ولا نداء، والتطبيقُ كما كان حرفاً. */
export const UNCONFIRMED_FLAG = "unconfirmed_payments_enabled";

/** **جوابٌ واحدٌ لقارئين** — الصفحةُ وسطرُ الرئيسية: نداءٌ لكلٍّ يفترق بين لحظتين، فيقول السطرُ «محجوب» والصفحةُ فارغة.
 *
 *  **ومختومٌ بصاحبه** (`users.id`) — قاعدةُ أخيه في تطبيق الراكب (`customer-app/src/lib/payment.ts`): المخزنُ عمرُ الوحدة،
 *  **والخروجُ لا يعيد تحميلَ الصفحة**؛ فكبتنٌ ثانٍ يدخل على الجهاز نفسِه كان يرى «محجوب» الأوّلِ ومعلَّقاتِه حتى يصل نداؤه —
 *  **وإلى الأبد إن سقط** (الخطأُ صامت). فلا يُقرأ الجوابُ إلا لمن سُئل له. */
let held: { owner: string; data: CaptainUnconfirmed } | null = null;
/** **آخرُ سؤال** — جوابُ سؤالٍ أقدمَ يصل بعد أحدثَ منه لا يكتب فوقه. */
let asked = 0;
const listeners = new Set<() => void>();

function subscribeUnconfirmed(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** يُسأل البابُ ثانيةً **لصاحبه** ويُبلَّغ كلُّ قارئ — **بعد كلِّ فعل**: الحجبُ يُرفع فوراً بالحسم (§٧)، فيُقرأ من الخلفية لا
 *  يُفترض. */
export async function refreshCaptainUnconfirmed(owner: string): Promise<CaptainUnconfirmed> {
  const ticket = ++asked;
  const data = await getMyUnconfirmedPayments();
  if (ticket === asked) {
    held = { owner, data };
    for (const listener of listeners) listener();
  }
  return data;
}

/** **ما ينتظر تأكيدَه** — `null` حتى يصل، **ولا نداءَ حيث المفتاحُ مطفأ**، **ولا جوابَ حسابٍ آخر**؛ ويُسأل عند كلِّ تركيبٍ وكلَّما
 *  عاد `active`، **وعند عودة التطبيق إلى الواجهة** (`visibilitychange`): التطبيقُ في الخلفية لا يُغلق، وسطرُ الحجب الذي بقي
 *  من الأمس يقول ما لم يعد قائماً. */
export function useCaptainUnconfirmed(enabled: boolean, active = true): CaptainUnconfirmed | null {
  const { user } = useSession();
  const owner = user?.id ?? null;
  const value = useSyncExternalStore(subscribeUnconfirmed, () =>
    held !== null && held.owner === owner ? held.data : null,
  );
  useEffect(() => {
    if (!enabled || !active || owner === null) return;
    const read = () => {
      refreshCaptainUnconfirmed(owner).catch(() => undefined);
    };
    read();
    const onVisible = () => {
      if (document.visibilityState === "visible") read();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [enabled, active, owner]);
  return enabled ? value : null;
}

/** **«عند كلِّ فتح» — مرّةً للفتحة** (§٦): «لاحقاً» يُخفيها لهذه الفتحة وحدَها، والفتحةُ عمرُ التطبيق في الذاكرة. **ولكلِّ حسابٍ
 *  فتحتُه** — حسابٌ ثانٍ في العمر نفسِه لم يرَ صفحتَه بعد. */
const openedFor = new Set<string>();

export function claimCaptainOpening(owner: string): boolean {
  if (openedFor.has(owner)) return false;
  openedFor.add(owner);
  return true;
}

/** **«استلمت المبلغ» / «وصلتني»** — البابُ القائمُ نفسُه (`POST /payments/{id}/confirm`)، ثمّ يُسأل ما بقي. */
export async function confirmUnconfirmed(owner: string, paymentId: string): Promise<void> {
  await confirmPayment(paymentId);
  await refreshCaptainUnconfirmed(owner).catch(() => undefined);
}

/** **«لم يدفع» / «لم تصلني»** — بابُ النزاع القائم بسببٍ مكتوب (نمطُ `Dispute.tsx`)، ثمّ يُسأل ما بقي. */
export async function disputeUnconfirmed(owner: string, paymentId: string, reason: string): Promise<void> {
  await disputePayment(paymentId, reason);
  await refreshCaptainUnconfirmed(owner).catch(() => undefined);
}

/** **«لم أستلم هذا المبلغ»** — اعتراضٌ على إتمامٍ آليٍّ خلال نافذته (§٢-٥)، ثمّ يُسأل ما بقي. */
export async function objectUnconfirmed(owner: string, paymentId: string, reason: string): Promise<void> {
  await objectAutoConfirm(paymentId, reason);
  await refreshCaptainUnconfirmed(owner).catch(() => undefined);
}
