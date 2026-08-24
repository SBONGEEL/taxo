/** جدولُ إحالات السائقات (SPEC القسم 9.1، المرحلة 12-ح).
 *
 * **وجملةُ الحالة تُبنى هنا من حقائقَ ترسلها الخلفية**، لا نصٌّ يأتي جاهزاً:
 * الخلفيةُ ترسل «معتمدة؟ ومثبَّتة الجنس؟ وكم رحلةً من كم؟»، والشاشةُ تقول
 * «بانتظار اعتماد حسابها» أو «أكملت رحلةً من ٣». وهي نفسُ قاعدةِ بناء نصِّ
 * الإشعار من `data`: الخلفيةُ لا تعرف من يقرأ ولا بأي لغة.
 *
 * **ولا زرَّ «ادفع الآن»**: الدفعُ مهمةٌ دوريةٌ تقيس الشروطَ بنفسها، وزرٌّ يدفع
 * يدوياً بابٌ ثانٍ للمال يتجاوز الشروطَ التي يحرسها الأول. وتعويضُ المشرف
 * الاستثنائي بابُه `adjustment` في المحفظة — حيث يُكتب سببُه ويدخل سجلَّ التدقيق.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { getReferralSummary, listReferrals } from "@/api/endpoints";
import type { AdminReferralRow, ReferralSummary } from "@/api/types";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { currencyOf, day, money } from "@/lib/format";
import { digits } from "@/lib/utils";

/** أينَ وصلت — أوّلُ شرطٍ ناقصٍ هو الجواب، فسردُ الثلاثة يخفي المطلوب الآن.
 *
 * **ولا «بانتظار إثبات الجنس» بعد التعميم**: كان شرطاً فصار **علاوة** (قرارُ
 * المالك الثاني)، فوسمُه هنا كان سيقول إن الإحالةَ متوقّفةٌ على ما لا يوقفها —
 * ويجعل مشرفاً يلاحق ختماً لا يُغيّر شيئاً في الدفع.
 */
function stage(row: AdminReferralRow): { text: string; tone: Tone } {
  if (row.rewarded) return { text: "مكافأة مدفوعة", tone: "ok" };
  // شرطا برنامج السائقين وحدَه — والراكبُ يكفيه عددُ رحلاته
  if (row.referral_type === "driver") {
    if (!row.driver_approved) {
      return { text: "بانتظار اعتماد حسابه", tone: "warn" };
    }
    if (!row.has_subscription) {
      return { text: "لم يشترِ اشتراكاً بعد", tone: "warn" };
    }
  }
  if (row.rides_done < row.rides_required) {
    return {
      text: `${digits(String(row.rides_done))} من ${digits(String(row.rides_required))} رحلات`,
      tone: "muted",
    };
  }
  // استحقّت ولم تُدفع: الدورةُ كلَّ عشر دقائق، أو المبلغُ صفرٌ لم يُحدَّد بعد،
  // أو بلغ المُحيلُ سقفَ شهره — وثلاثتُها «مستحقّةٌ لم تُدفع» في هذا الجدول
  return { text: "مستحقّة — بانتظار الدفع", tone: "ink" };
}

export function Referrals({ onError }: { onError: (message: string) => void }) {
  const { country } = useCountry();
  const [rows, setRows] = useState<AdminReferralRow[] | null>(null);
  const [onlyPending, setOnlyPending] = useState(false);
  const [summary, setSummary] = useState<ReferralSummary | null>(null);

  const load = useCallback(async () => {
    setRows(null);
    try {
      // **المجموعُ من الخلفية** لا من الصفحة المعروضة: الصفحةُ مقصوصةٌ بخمسين
      // صفاً، ومجموعُها تحت عنوان «المدفوع كلُّه» رقمٌ يكذب (نفس قاعدة §14)
      const [list, totals] = await Promise.all([
        listReferrals(country, onlyPending ? false : undefined),
        getReferralSummary(country),
      ]);
      setSummary(totals);
      setRows(list);
    } catch (caught) {
      onError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الإحالات",
      );
    }
  }, [country, onlyPending, onError]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="rounded-16 border border-line bg-surface p-18">
      <div className="flex items-start justify-between gap-12">
        <div>
          <h2 className="text-14 font-bold text-ink">إحالات السائقات</h2>
          <p className="mt-4 max-w-[70ch] text-11 leading-snug text-muted">
            <b className="text-ink">تتحمّلها الشركة</b> — المكافأةُ قيدٌ دائنٌ في
            محفظة من أحال، بلا خصمٍ من أحد. وتُدفع بعد اعتماد حساب المُحالة{" "}
            <b className="text-ink">وإثبات جنسها</b> وإكمالها الرحلات المطلوبة.
            والمبلغُ والشرطُ في «الإعدادات».
          </p>
          {summary ? (
            <p className="mt-8 text-12 text-ink">
              المدفوع كلُّه:{" "}
              <b>{money(summary.total_rewarded, currencyOf(country))}</b>{" "}
              <span className="text-muted">
                ({digits(String(summary.rewarded_count))} مكافأة ·{" "}
                {digits(String(summary.pending_count))} تنتظر)
              </span>
            </p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => setOnlyPending((value) => !value)}
          className={
            onlyPending
              ? "shrink-0 rounded-full border border-accent bg-accent px-12 py-6 text-11.5 font-semibold text-accent-ink"
              : "shrink-0 rounded-full border border-line bg-surface-2 px-12 py-6 text-11.5 font-semibold text-muted"
          }
        >
          غير المدفوعة
        </button>
      </div>

      {rows === null ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <p className="mt-14 text-12.5 text-muted">
          {onlyPending
            ? "لا إحالاتٍ غير مدفوعة في هذا السوق."
            : "لا إحالاتٍ في هذا السوق بعد."}
        </p>
      ) : (
        <div className="mt-14 overflow-x-auto">
          <table className="w-full min-w-[52rem] text-12.5">
            <thead>
              <tr className="text-11 text-muted">
                <th className="p-8 text-start font-semibold">المُحيل</th>
                <th className="p-8 text-start font-semibold">المُحال</th>
                <th className="p-8 text-start font-semibold">الرمز</th>
                <th className="p-8 text-start font-semibold">البرنامج</th>
                <th className="p-8 text-start font-semibold">التسجيل</th>
                <th className="p-8 text-start font-semibold">الحالة</th>
                <th className="p-8 text-start font-semibold">المدفوع</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const where = stage(row);
                return (
                  <tr key={row.id} className="border-t border-line">
                    <td className="p-8">
                      <span className="block font-medium text-ink">
                        {row.referrer_name}
                      </span>
                      {/* **الرقمُ لاتينيٌّ بلا تحويل**: يُطابقه المشرفُ خانةً
                          بخانة على شاشةٍ أخرى، والتحويلُ يجعله يقارن شكلين */}
                      <span className="block text-11 text-muted" dir="ltr">
                        {row.referrer_phone}
                      </span>
                    </td>
                    <td className="p-8">
                      <span className="block font-medium text-ink">
                        {row.referred_name}
                      </span>
                      <span className="block text-11 text-muted" dir="ltr">
                        {row.referred_phone}
                      </span>
                    </td>
                    <td className="p-8 font-bold text-ink" dir="ltr">
                      {row.code_used}
                    </td>
                    {/* **البرنامجُ عمودٌ لا استنتاج**: رمزٌ واحدٌ يخدم الاثنين،
                        فمشرفٌ يقرأ مبلغين مختلفين على رمزٍ واحد يظنّه عطباً */}
                    <td className="p-8">
                      <Badge tone={row.referral_type === "driver" ? "ink" : "muted"}>
                        {row.referral_type === "driver" ? "كبتن" : "راكب"}
                      </Badge>
                      {row.referral_type === "driver" && row.female_verified ? (
                        <span className="mt-4 block text-11 text-ok">+ علاوة</span>
                      ) : null}
                    </td>
                    <td className="p-8 text-muted">{day(row.created_at)}</td>
                    <td className="p-8">
                      <Badge tone={where.tone}>{where.text}</Badge>
                    </td>
                    <td className="p-8 text-ink">
                      {/* **ولا اشتقاقَ للعملة من الرقم**: `reward_currency`
                          موجودةٌ كلَّما كان الصفُّ مدفوعاً — قيدُ «كلٌّ أو لا
                          شيء» في القاعدة يضمنه. واستنتاجُ دولةٍ من بادئةِ هاتفٍ
                          تخمينٌ يكتب عملةً خطأً على مالٍ صحيح */}
                      {row.rewarded && row.reward_amount
                        ? money(row.reward_amount, row.reward_currency ?? "")
                        : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
