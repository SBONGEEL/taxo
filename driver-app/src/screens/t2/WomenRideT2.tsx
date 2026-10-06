/** الخدمةُ النسائيةُ في عمل الكبتنة — TAXO 2.0 «CW2 الرئيسية — الوضع النسائي» و«CW3 طلب وارد — راكبة»، **في الداكن المرسوم
 *  والفاتح والنسائيّ** (§٦٢-ج/٢٣). **وجوهٌ لا منطق**: الرئيسيةُ C04 نفسُها (`HomeT2` · `useHomeScreen`) والطلبُ C05 نفسُه (`OfferT2`)
 *  — **فالقبولُ والرفضُ والاستقبالُ هي هي**.
 *
 * **CW2 — «الوضعُ النسائيّ»** = كبتنةٌ (`gender = female`) اختارت «الراكبات فقط» حيث الخدمةُ مشتعلة — **بسلوك اليوم (الوضع أ)**: لا تصلها
 * إلا الراكبات. فـ«وضع نسائي» في الرأس (ولمستُه إلى CW1 حيث يُغيَّر)، والحرفُ بحافّة البرقوق، و«متصلة — طلبات الراكبات فقط · يمكنك
 * تغيير ذلك من الإعدادات» في حبّة الاستقبال برقوقاً — **مكانَ** شريط «أستقبل ركاباً: النساء فقط · تغيير» القائم، وهو يقول الشيءَ نفسَه.
 * **وأطوارُ الحبّة القائمة باقية** («نفتح الطلب…» · «بانتظار إشارة الموقع» · «جارٍ الاتصال…») بصيغة المؤنّث.
 *
 * **CW3 — «رحلة نسائية»** لكلِّ طلبٍ طُلبت فيه كبتنة (`gender_preference = female`): الشارةُ بالبرقوق مكانَ «طلب جديد» ومعها الفئة، وحافّةُ
 * البطاقة وقوسُ المهلة وأيقونةُ المسافة و«قبول» بالبرقوق. **وطلبُ «ذكور» ليس رحلةً نسائية** — فلا يُكتب عليه «طلب نسائي» كما كان
 * (`APPROVALS-WOMEN-MODES.md` §٦ — عطبٌ مُبلَّغٌ صُحِّح في هذه البطاقة).
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته**:
 * - **CW2 · «راكبات بانتظار كبتنة حولك» ونقاطُها على الخريطة**: لا يصل الكبتنةَ شيءٌ عن طلباتٍ لم تُعرض عليها، **وعدُّها جمعٌ جديد** —
 *   ولا يُبنى بلا مصدر. **و«كل راكبة تُؤكد رمز الرحلة قبل الركوب»**: رمزُ الرحلة مطفأٌ لم يُبنَ (§٦٢-ج/٥). **و«6 · 4:10 ساعة · 4.97»
 *   بطاقاتٍ**: الرحلاتُ والتقييمُ في شارتَي C04 القائمتين، والساعاتُ تنتظر إذنَ المالك (§٦٢-ج/٣٧). **وغيابُ الجرس في اللوحة**: الجرسُ باقٍ.
 * - **CW3 · «راكبة موثّقة» واسمُ الراكبة وتقييمُها ورحلاتُها**: **العرضُ لا يحمل هويةَ الراكب قبل القبول** عمداً (`OfferT2`). **و«حتى
 *   الراكبة»** ⇐ «حتى الراكب»: جنسُ الراكبة لا يُعرض لكبتن (وعدُ «الخصوصية» في «بياناتي» عند الراكبة). **و«4 د»**: زمنُ الوصول (§٦٢-ج/١٠).
 * - **CW4 · «اطلبي من الراكبة رمز الرحلة»**: لم يُبنَ — رمزُ الرحلة (§٦٢-ج/٥).
 */

import type { GenderPreference, Ride } from "@/api/types";
import { Icon } from "@/taxo2";

import "@/taxo2";
import "./women.css";

/** **رحلةُ الخدمة النسائية** = ما طُلبت فيه كبتنة — تفضيلُ الطلب لا جنسُ أحد. */
export function isWomenRide(ride: Pick<Ride, "gender_preference">): boolean {
  return ride.gender_preference === "female";
}

/** **CW2 — أهي في الوضع النسائيّ؟** كبتنةٌ اختارت «الراكبات فقط» حيث الخدمةُ مشتعلة. */
export function isWomenMode(womenService: boolean, preference: GenderPreference, gender: string | null | undefined): boolean {
  return womenService && preference === "female" && gender === "female";
}

/** **«وضع نسائي»** في رأس الرئيسية (CW2) — ولمستُه إلى CW1 حيث يُغيَّر. **وعلى الضيّق مع شارة المستوى أيقونتُه وحدَها** (`women.css`). */
export function WomenModeChipT2({ onOpen }: { onOpen: () => void }) {
  return (
    <button type="button" className="t2-wchip" onClick={onOpen} aria-label="وضع نسائي — الخدمة النسائية">
      <Icon name="woman" fill />
      <span className="t2-wchip-text">وضع نسائي</span>
    </button>
  );
}

/** **نصّا حبّة الاستقبال في الوضع النسائيّ** (CW2) — بأطوار الحبّة القائمة نفسِها، **والسطرُ الثاني حين تنتظر الطلبات وحدَه**. */
export function womenGoText({
  online,
  connecting,
  located,
  awaitedOffer,
  goLabel,
}: {
  online: boolean;
  connecting: boolean;
  located: boolean;
  awaitedOffer: boolean;
  goLabel: string;
}): { title: string; sub: string | null } {
  if (online) {
    if (awaitedOffer) return { title: "متصلة — نفتح الطلب…", sub: null };
    if (!located) return { title: "متصلة — بانتظار إشارة الموقع", sub: null };
    return { title: "متصلة — طلبات الراكبات فقط", sub: "يمكنك تغيير ذلك من الإعدادات" };
  }
  if (connecting) return { title: goLabel, sub: null };
  return { title: "غير متصلة", sub: goLabel };
}

/** **«رحلة نسائية · الفئة»** (CW3) مكانَ «طلب جديد · الفئة» — بالبرقوق كما رُسمت، **والفئةُ مكانَ «راكبة موثّقة»**. */
export function WomenOfferChipT2({ categoryLabel }: { categoryLabel: string }) {
  return (
    <span className="t2-wchip">
      <Icon name="woman" fill />
      رحلة نسائية · {categoryLabel}
    </span>
  );
}
