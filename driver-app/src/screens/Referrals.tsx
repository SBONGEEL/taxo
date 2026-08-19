/** «أَحِلْ صديقك» — رمزي ومن سجّل به (SPEC §9.1، 12-ح ثم تعميمُها).
 *
 * **وأربعُ قواعدَ في هذه الشاشة تحمل قراراتٍ لا تفاصيلَ عرض:**
 *
 * 1. **الرمزُ لاتينيٌّ بلا تحويلِ خانات**: يُنطق في مكالمةٍ ويُكتب في شاشةٍ
 *    أخرى حرفاً حرفاً — كاللوحة والمرجع، لا كالمبالغ (`Cards.tsx`/`Vehicle.tsx`).
 * 2. **ولا يُذكر مبلغٌ حيث لم يُحدَّد**: `reward_amount === 0` تعني «لم يقرّره
 *    أحدٌ بعد» لا «صفراً»، فالشاشةُ تعرض الرمزَ والعدَّ وتصمت عن المال — ووعدٌ
 *    بمالٍ لم يُقرَّر أسوأُ من صمت، ويُقرأ خُلفاً للوعد يومَ لا يصل.
 * 3. **والبرنامجان يُشرحان معاً** (شرطُ المالك الثاني بحرفه): الرمزُ يعمل مع
 *    الاثنين، والمكافأةُ تختلف بحسب من يسجّل به — **فمن يدعو سائقاً لا يُفاجأ
 *    بمبلغٍ غير الذي توقّعه**. وعرضُ مبلغٍ واحدٍ كان سيكذب على نصف من يقرأ.
 * 4. **والسقفُ يُعلن قبل أن يدعو لا بعد أن يُرفض دفعُه** (شرطُه الثالث): كم
 *    السقفُ وكم بقي منه هذا الشهر. ومن تجاوز يرى إحالتَه **مسجَّلةً وموسومةً**
 *    بأنها فوق السقف — لا صمتَ ولا رقمٌ يختفي.
 *
 * **وجملةُ الحالة تُبنى هنا** من حقائقَ ترسلها الخلفية لا نصّاً جاهزاً — نفسُ
 * قاعدةِ بناء نصِّ الإشعار من `data`: الخلفيةُ لا تعرف من يقرأ.
 */

import { useEffect, useState } from "react";
import { Copy, Check, Share2 } from "lucide-react";

import { ApiError } from "@/api/client";
import { Stagger, StaggerItem } from "@/components/ui/Motion";
import { getMyReferrals } from "@/api/endpoints";
import type { MyReferrals, ReferralProgram, ReferralStage } from "@/api/types";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { useSession } from "@/lib/session";
import { digits, cn } from "@/lib/utils";
import { useGoBack } from "@/lib/back";

/** أوّلُ شرطٍ ناقصٍ هو الجواب — وسردُ الثلاثة يخفي المطلوبَ الآن.
 *
 * **ولا «بانتظار إثبات الجنس» بعد التعميم**: كان شرطاً فصار علاوةً، فوسمُه
 * كان سيقول إن الإحالةَ متوقّفةٌ على ما لا يوقفها.
 */
function stageOf(row: ReferralStage): { text: string; tone: string } {
  if (row.rewarded) return { text: "وصلت المكافأة", tone: "text-ok" };
  if (row.referral_type === "driver") {
    if (!row.driver_approved) {
      return { text: "حسابه قيد المراجعة", tone: "text-muted" };
    }
    if (!row.has_subscription) {
      return { text: "لم يشترِ اشتراكاً بعد", tone: "text-muted" };
    }
  }
  if (row.rides_done < row.rides_required) {
    return {
      text: `أكمل ${digits(String(row.rides_done))} من ${digits(
        String(row.rides_required),
      )} رحلات`,
      tone: "text-muted",
    };
  }
  // **فوق السقف يُقال، لا يُصمت عنه**: «مستحقّة ولن تُدفع» حقيقةٌ يملكها صاحبُها
  if (row.over_monthly_cap) {
    return { text: "فوق سقف هذا الشهر — لن تُدفع", tone: "text-warn" };
  }
  return { text: "استحقّت — المكافأة في الطريق", tone: "text-ink" };
}

export function ReferralsScreen() {
  const goBack = useGoBack();
  const { user } = useSession();
  // العملةُ من دولة الحساب — والخلفيةُ ترسلها على المكافأة المدفوعة وحدها
  const currency =
    user?.country_code === "LY" ? CURRENCY_LABEL.LYD : CURRENCY_LABEL.JOD;
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
  const paying = (data?.programs ?? []).filter(
    (program) => program.enabled && Number(program.reward_amount) > 0,
  );
  const pays = paying.length > 0;

  // **والسقفُ يُقرأ من البرنامج الذي يدفع**، وإن دفع الاثنان فأصغرُهما هو
  // القيدُ الفعليّ — وعرضُ الأوسع يَعِد بما لا يُدفع
  const cap = paying
    .map((program) => program.monthly_cap)
    .filter((value): value is number => value !== null)
    .sort((a, b) => a - b)[0];
  const left = cap === undefined ? null : Math.max(0, cap - (data?.paid_this_month ?? 0));

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
    const text = `سجّل في تاكسو برمزي ${data.code}`;
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

  function amountOf(program: ReferralProgram) {
    return `${digits(program.reward_amount)} ${currency}`;
  }

  return (
    <div className="scr h-full bg-bg px-16 pb-12 pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => goBack()}
          aria-label="رجوع"
          className="pressable text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">أَحِلْ صديقك</h1>
      </div>

      <ErrorNote message={error} />
      {data === null ? (
        <Spinner />
      ) : (
        <div className="space-y-14">
          <section className="card p-16 text-center">
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
                className="pressable flex flex-1 items-center justify-center gap-8 rounded-13 border border-line bg-surface-2 py-12 text-13 font-semibold text-ink"
              >
                {copied ? <Check size={16} /> : <Copy size={16} />}
                {copied ? "نُسخ" : "انسخ"}
              </button>
              <button
                type="button"
                onClick={() => void share()}
                className="pressable flex flex-1 items-center justify-center gap-8 rounded-13 border border-line bg-surface-2 py-12 text-13 font-semibold text-ink"
              >
                <Share2 size={16} />
                شارك
              </button>
            </div>
          </section>

          {/* **رمزٌ واحدٌ وبرنامجان** — شرطُ المالك الثاني: النصُّ يشرح أن الرمز
              يعمل مع الاثنين وأن المكافأة تختلف بحسب من يسجّل به */}
          {pays ? (
            <section className="card p-16">
              <h2 className="text-13.5 font-bold text-ink">
                رمزك واحدٌ، والمكافأةُ بحسب من يسجّل به
              </h2>
              <div className="mt-10 space-y-8">
                {data.programs.map((program) => {
                  const active =
                    program.enabled && Number(program.reward_amount) > 0;
                  const isDriver = program.referral_type === "driver";
                  return (
                    <div
                      key={program.referral_type}
                      className="flex items-start justify-between gap-10 rounded-13 border border-line bg-surface-2 p-12"
                    >
                      <div>
                        <p className="text-12.5 font-semibold text-ink">
                          {isDriver ? "سجّل كبتناً" : "سجّل راكباً"}
                        </p>
                        <p className="mt-4 text-11.5 text-muted">
                          {isDriver
                            ? `يُعتمد حسابه ويشتري اشتراكاً ويُكمل ${digits(
                                String(program.required_rides),
                              )} رحلات`
                            : `يُكمل ${digits(
                                String(program.required_rides),
                              )} رحلات`}
                        </p>
                        {/* **العلاوةُ بجانب الأساس بجملةٍ تقول المُحصَّل** —
                            ورقمان منفصلان يُقرأ ثانيهما بديلاً عن الأول */}
                        {isDriver && Number(program.female_bonus_amount) > 0 ? (
                          <p className="mt-4 text-11.5 text-ok">
                            وإن كانت سائقةً موثَّقة:{" "}
                            {digits(program.female_total_amount)} {currency}{" "}
                            — الأساسُ وعلاوتُه معاً
                          </p>
                        ) : null}
                      </div>
                      <span
                        className={cn(
                          "shrink-0 text-13 font-bold",
                          active ? "text-ink" : "text-muted",
                        )}
                      >
                        {active ? amountOf(program) : "—"}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* **السقفُ قبل أن يدعو** — شرطُ المالك الثالث بحرفه */}
              {cap !== undefined ? (
                <p
                  className={cn(
                    "mt-10 text-11.5",
                    left === 0 ? "text-warn" : "text-muted",
                  )}
                >
                  {left === 0
                    ? `بلغتَ سقفَ هذا الشهر (${digits(String(cap))}). ما يُسجَّل بعده يبقى منسوباً لك ولا يُدفع حتى الشهر القادم.`
                    : `سقفُ هذا الشهر ${digits(String(cap))} إحالات — بقي لك ${digits(String(left))}.`}
                </p>
              ) : null}

              <p className="mt-8 text-11.5 text-muted">
                مجموع ما وصلك: {digits(data.total_rewarded)} {currency}
              </p>
            </section>
          ) : (
            <section className="card p-16">
              <h2 className="text-13.5 font-bold text-ink">كيف تعمل</h2>
              <p className="mt-8 text-12.5 leading-relaxed text-muted">
                شارك رمزك مع من تدعوه، فيكتبه عند التسجيل. وتُسجَّل الإحالةُ في
                حسابك من الآن — والمكافأةُ تُعلن هنا متى حُدِّدت.
              </p>
            </section>
          )}

          <section>
            <h2 className="mb-8 text-13.5 font-bold text-ink">من سجّل برمزك</h2>
            {data.referrals.length === 0 ? (
              <p className="card p-16 text-center text-12.5 text-muted">
                لم يسجّل أحدٌ برمزك بعد.
              </p>
            ) : (
              <Stagger className="space-y-8">
                {data.referrals.map((row) => {
                  const where = stageOf(row);
                  return (
                    <StaggerItem
                      key={row.id}
                      className="flex items-center justify-between gap-10 rounded-13 border border-line bg-surface p-12"
                    >
                      <span>
                        <span
                          className={cn("block text-12.5 font-medium", where.tone)}
                        >
                          {where.text}
                        </span>
                        <span className="mt-2 block text-11 text-muted">
                          {row.referral_type === "driver" ? "كبتن" : "راكب"}
                        </span>
                      </span>
                      <span className="text-11.5 text-muted">
                        {row.rewarded && row.reward_amount
                          ? `${digits(row.reward_amount)} ${
                              row.reward_currency
                                ? CURRENCY_LABEL[
                                    row.reward_currency as "JOD" | "LYD"
                                  ]
                                : currency
                            }`
                          : null}
                      </span>
                    </StaggerItem>
                  );
                })}
              </Stagger>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
