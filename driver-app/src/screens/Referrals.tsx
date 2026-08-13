/** «أَحِلْ سائقة» — رمزي ومن سجّل به (SPEC القسم 9.1، المرحلة 12-ح).
 *
 * **وثلاثُ قواعدَ في هذه الشاشة تحمل قراراتٍ لا تفاصيلَ عرض:**
 *
 * 1. **الرمزُ لاتينيٌّ بلا تحويلِ خانات**: يُنطق في مكالمةٍ ويُكتب في شاشةٍ
 *    أخرى حرفاً حرفاً — كاللوحة والمرجع، لا كالمبالغ (`Cards.tsx`/`Vehicle.tsx`).
 * 2. **ولا يُذكر مبلغٌ حيث لم يُحدَّد**: `reward_amount === 0` تعني «لم يقرّره
 *    أحدٌ بعد» لا «صفراً»، فالشاشةُ تعرض الرمزَ والعدَّ وتصمت عن المال — ووعدٌ
 *    بمالٍ لم يُقرَّر أسوأُ من صمت، ويُقرأ خُلفاً للوعد يومَ لا يصل.
 * 3. **وجملةُ الحالة تُبنى هنا** من حقائقَ ترسلها الخلفية (معتمدة؟ مثبَّتة
 *    الجنس؟ كم رحلةً من كم؟) لا نصّاً جاهزاً — نفسُ قاعدةِ بناء نصِّ الإشعار
 *    من `data`: الخلفيةُ لا تعرف من يقرأ.
 */

import { useEffect, useState } from "react";
import { Copy, Check, Share2 } from "lucide-react";

import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getMyReferrals } from "@/api/endpoints";
import type { MyReferrals, ReferralStage } from "@/api/types";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { useSession } from "@/lib/session";
import { arabicDigits, cn } from "@/lib/utils";

/** أوّلُ شرطٍ ناقصٍ هو الجواب — وسردُ الثلاثة يخفي المطلوبَ الآن. */
function stageOf(row: ReferralStage): { text: string; tone: string } {
  if (row.rewarded) return { text: "وصلت المكافأة", tone: "text-ok" };
  if (!row.driver_approved) {
    return { text: "حسابها قيد المراجعة", tone: "text-muted" };
  }
  if (!row.gender_ready) {
    return { text: "بانتظار إثبات بياناتها", tone: "text-muted" };
  }
  if (row.rides_done < row.rides_required) {
    return {
      text: `أكملت ${arabicDigits(String(row.rides_done))} من ${arabicDigits(
        String(row.rides_required),
      )} رحلات`,
      tone: "text-muted",
    };
  }
  return { text: "استحقّت — المكافأة في الطريق", tone: "text-ink" };
}

export function ReferralsScreen() {
  const navigate = useNavigate();
  const { user } = useSession();
  // العملةُ من دولة الحساب — والخلفيةُ ترسلها على المكافأة المدفوعة وحدها
  const currency = user?.country_code === "LY" ? CURRENCY_LABEL.LYD : CURRENCY_LABEL.JOD;
  const [data, setData] = useState<MyReferrals | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    getMyReferrals()
      .then(setData)
      .catch((caught) =>
        setError(
          caught instanceof ApiError ? caught.message : "تعذّر قراءة الإحالات",
        ),
      );
  }, []);

  // **شرطان لا شرط** — نفسُ `referrals.policy_for(...).pays` في الخلفية:
  // مفتاحٌ مطفأٌ ومبلغٌ مضبوطٌ (سوقٌ يُجهَّز للإطلاق) يجعل الشاشةَ تَعِد بمكافأةٍ
  // لا تُدفع، وهو أسوأُ من صمتٍ لأنه يُقرأ خُلفاً للوعد لا تأجيلاً له
  const pays =
    data !== null && data.enabled && Number(data.reward_amount) > 0;

  async function copy() {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(data.code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // نسخٌ فاشلٌ لا يُبلَّغ خطأً: الرمزُ معروضٌ أمامه فيقرؤه
    }
  }

  async function share() {
    if (!data) return;
    const text = `سجّلي كسائقة في تاكسو برمزي ${data.code}`;
    if (navigator.share) {
      try {
        await navigator.share({ text });
        return;
      } catch {
        // أُلغيت المشاركة — لا شيء يُقال
      }
    }
    void copy();
  }

  return (
    <div className="scr h-full bg-bg px-16 pb-12 pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => navigate(-1)}
          aria-label="رجوع"
          className="text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">أَحِلْ سائقة</h1>
      </div>

      <ErrorNote message={error} />
      {data === null ? (
        <Spinner />
      ) : (
        <div className="space-y-14">
          <section className="rounded-16 border border-line bg-surface p-16 text-center">
            <p className="text-12 text-muted">رمز الإحالة الخاص بك</p>
            {/* **لاتينيٌّ ومتباعدُ الحروف**: يُقرأ ليُنطق ويُكتب في شاشةٍ أخرى */}
            <p
              dir="ltr"
              className="mt-8 text-26 font-bold tracking-code text-ink"
            >
              {data.code}
            </p>
            <div className="mt-14 flex gap-10">
              <button
                type="button"
                onClick={() => void copy()}
                className="flex flex-1 items-center justify-center gap-8 rounded-13 border border-line bg-surface-2 py-12 text-13 font-semibold text-ink"
              >
                {copied ? <Check size={16} /> : <Copy size={16} />}
                {copied ? "نُسخ" : "انسخ"}
              </button>
              <button
                type="button"
                onClick={() => void share()}
                className="flex flex-1 items-center justify-center gap-8 rounded-13 border border-line bg-surface-2 py-12 text-13 font-semibold text-ink"
              >
                <Share2 size={16} />
                شارك
              </button>
            </div>
          </section>

          <section className="rounded-16 border border-line bg-surface p-16">
            <h2 className="text-13.5 font-bold text-ink">كيف تعمل</h2>
            <ol className="mt-8 space-y-6 text-12.5 leading-relaxed text-muted">
              <li>١. تسجّل السائقةُ حسابها وتكتب رمزك.</li>
              <li>٢. تُراجع مستنداتُها ويُعتمد حسابها.</li>
              <li>
                ٣. تُكمل {arabicDigits(String(data.required_rides))} رحلات.
              </li>
              {/* السطرُ الرابعُ يُذكر مبلغاً — فلا يُكتب حيث لا مبلغ */}
              {pays ? (
                <li>
                  ٤. تصلك{" "}
                  <b className="text-ink">
                    {arabicDigits(data.reward_amount)} {currency}
                  </b>{" "}
                  في محفظتك.
                </li>
              ) : (
                <li>٤. تُسجَّل الإحالةُ في حسابك.</li>
              )}
            </ol>
            {pays ? (
              <p className="mt-10 text-11.5 text-muted">
                مجموع ما وصلك: {arabicDigits(data.total_rewarded)} {currency}
              </p>
            ) : null}
          </section>

          <section>
            <h2 className="mb-8 text-13.5 font-bold text-ink">من سجّل برمزك</h2>
            {data.referrals.length === 0 ? (
              <p className="rounded-16 border border-line bg-surface p-16 text-center text-12.5 text-muted">
                لم يسجّل أحدٌ برمزك بعد.
              </p>
            ) : (
              <ul className="space-y-8">
                {data.referrals.map((row) => {
                  const where = stageOf(row);
                  return (
                    <li
                      key={row.id}
                      className="flex items-center justify-between gap-10 rounded-13 border border-line bg-surface p-12"
                    >
                      <span className={cn("text-12.5 font-medium", where.tone)}>
                        {where.text}
                      </span>
                      <span className="text-11.5 text-muted">
                        {row.rewarded && row.reward_amount
                          ? `${arabicDigits(row.reward_amount)} ${
                              row.reward_currency
                                ? CURRENCY_LABEL[
                                    row.reward_currency as "JOD" | "LYD"
                                  ]
                                : currency
                            }`
                          : null}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
