/** «ادعُ صديقك» — رمزي ومن سجّل به (SPEC §9.1، تعميمُ 12-ح).
 *
 * **وهي نسخةٌ من شاشة تطبيق الكبتن لا اشتقاقٌ ثانٍ** — كـ`BottomNav` بالضبط:
 * التطبيقان يتقاسمان نظامَ تصميمٍ واحداً، وشاشتان تُبنيان مرتين تفترقان أوّلَ
 * قيمةٍ تُعدَّل في إحداهما. والفرقُ بينهما نصّانِ لا أكثر: العنوان، ونصُّ
 * المشاركة.
 *
 * **وأربعُ قواعدَ فيها تحمل قراراتٍ لا تفاصيلَ عرض:**
 *
 * 1. **الرمزُ لاتينيٌّ بحروفٍ متباعدة**: يُنطق في مكالمةٍ ويُكتب في شاشةٍ أخرى
 *    حرفاً حرفاً — والخاناتُ في هذا التطبيق لاتينيةٌ أصلاً بالعُرف.
 * 2. **ولا يُذكر مبلغٌ حيث لم يُحدَّد**: `reward_amount === 0` تعني «لم يقرّره
 *    أحدٌ بعد» لا «صفراً» — ووعدٌ بمالٍ لم يُقرَّر يُقرأ خُلفاً للوعد يومَ لا يصل.
 * 3. **والبرنامجان يُشرحان معاً** (شرطُ المالك الثاني بحرفه): الرمزُ يعمل مع
 *    الاثنين، والمكافأةُ تختلف بحسب من يسجّل به — **فمن يدعو سائقاً لا يُفاجأ
 *    بمبلغٍ غير الذي توقّعه**.
 * 4. **والسقفُ يُعلن قبل أن يدعو لا بعد أن يُرفض دفعُه** (شرطُه الثالث)، ومن
 *    تجاوز يرى إحالتَه **مسجَّلةً وموسومةً** بأنها فوقه — لا صمتَ ولا رقمٌ يختفي.
 */

import { useEffect, useState } from "react";
import { Copy, Check, Share2 } from "lucide-react";

import { ApiError } from "@/api/client";
import { getMyReferrals } from "@/api/endpoints";
import type { MyReferrals, ReferralProgram, ReferralStage } from "@/api/types";
import { ErrorNote, EmptyState } from "@/components/ui/Feedback";
import { Screen } from "@/components/ui/Screen";
import { Stagger, StaggerItem } from "@/components/ui/Motion";
import { useSession } from "@/lib/session";
import { cn, formatMoney } from "@/lib/utils";

/** أوّلُ شرطٍ ناقصٍ هو الجواب — وسردُ الثلاثة يخفي المطلوبَ الآن. */
function stageOf(row: ReferralStage): { text: string; tone: string } {
  if (row.rewarded) return { text: "وصلت المكافأة", tone: "text-ok" };
  if (row.referral_type === "driver") {
    if (!row.driver_approved) {
      return { text: "حسابه قيد المراجعة", tone: "text-mut" };
    }
    if (!row.has_subscription) {
      return { text: "لم يشترِ اشتراكاً بعد", tone: "text-mut" };
    }
  }
  if (row.rides_done < row.rides_required) {
    return {
      text: `أكمل ${row.rides_done} من ${row.rides_required} رحلات`,
      tone: "text-mut",
    };
  }
  // **فوق السقف يُقال، لا يُصمت عنه**: «مستحقّة ولن تُدفع» حقيقةٌ يملكها صاحبُها
  if (row.over_monthly_cap) {
    return { text: "فوق سقف هذا الشهر — لن تُدفع", tone: "text-warn" };
  }
  return { text: "استحقّت — المكافأة في الطريق", tone: "text-tx" };
}

export function ReferralsScreen() {
  const { user } = useSession();
  const currency = user?.country_code === "LY" ? "LYD" : "JOD";
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

  // **شرطان لا شرط** — نفسُ `referrals.policy_for(...).pays` في الخلفية
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
  const left =
    cap === undefined ? null : Math.max(0, cap - (data?.paid_this_month ?? 0));

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
    return formatMoney(program.reward_amount, currency);
  }

  return (
    <Screen title="ادعُ صديقك" back="/account" nav>
      <ErrorNote message={error} />
      {data === null ? null : (
        <div className="space-y-14">
          <section className="rounded-16 border border-line bg-sur p-16 text-center">
            <p className="text-12 text-mut">رمز الدعوة الخاص بك</p>
            <p dir="ltr" className="mt-8 text-26 font-bold tracking-code text-tx">
              {data.code}
            </p>
            <div className="mt-14 flex gap-10">
              <button
                type="button"
                onClick={() => void copy()}
                className="flex flex-1 items-center justify-center gap-8 rounded-13 border border-line bg-sur2 py-12 text-13 font-semibold text-tx"
              >
                {copied ? <Check size={16} /> : <Copy size={16} />}
                {copied ? "نُسخ" : "انسخ"}
              </button>
              <button
                type="button"
                onClick={() => void share()}
                className="flex flex-1 items-center justify-center gap-8 rounded-13 border border-line bg-sur2 py-12 text-13 font-semibold text-tx"
              >
                <Share2 size={16} />
                شارك
              </button>
            </div>
          </section>

          {pays ? (
            <section className="rounded-16 border border-line bg-sur p-16">
              <h2 className="text-13.5 font-bold text-tx">
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
                      className="flex items-start justify-between gap-10 rounded-13 border border-line bg-sur2 p-12"
                    >
                      <div>
                        <p className="text-12.5 font-semibold text-tx">
                          {isDriver ? "سجّل كبتناً" : "سجّل راكباً"}
                        </p>
                        <p className="mt-4 text-11.5 text-mut">
                          {isDriver
                            ? `يُعتمد حسابه ويشتري اشتراكاً ويُكمل ${program.required_rides} رحلات`
                            : `يُكمل ${program.required_rides} رحلات`}
                        </p>
                        {/* **العلاوةُ بجانب الأساس بجملةٍ تقول المُحصَّل** */}
                        {isDriver && Number(program.female_bonus_amount) > 0 ? (
                          <p className="mt-4 text-11.5 text-ok">
                            وإن كانت سائقةً موثَّقة:{" "}
                            {formatMoney(program.female_total_amount, currency)} —
                            الأساسُ وعلاوتُه معاً
                          </p>
                        ) : null}
                      </div>
                      <span
                        className={cn(
                          "shrink-0 text-13 font-bold",
                          active ? "text-tx" : "text-mut",
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
                    left === 0 ? "text-warn" : "text-mut",
                  )}
                >
                  {left === 0
                    ? `بلغتَ سقفَ هذا الشهر (${cap}). ما يُسجَّل بعده يبقى منسوباً لك ولا يُدفع حتى الشهر القادم.`
                    : `سقفُ هذا الشهر ${cap} دعوات — بقي لك ${left}.`}
                </p>
              ) : null}

              <p className="mt-8 text-11.5 text-mut">
                مجموع ما وصلك: {formatMoney(data.total_rewarded, currency)}
              </p>
            </section>
          ) : (
            <section className="rounded-16 border border-line bg-sur p-16">
              <h2 className="text-13.5 font-bold text-tx">كيف تعمل</h2>
              <p className="mt-8 text-12.5 leading-relaxed text-mut">
                شارك رمزك مع من تدعوه، فيكتبه عند التسجيل. وتُسجَّل الدعوةُ في
                حسابك من الآن — والمكافأةُ تُعلن هنا متى حُدِّدت.
              </p>
            </section>
          )}

          <section>
            <h2 className="mb-8 text-13.5 font-bold text-tx">من سجّل برمزك</h2>
            {data.referrals.length === 0 ? (
              <EmptyState title="لم يسجّل أحدٌ برمزك بعد" />
            ) : (
              <Stagger className="space-y-8">
                {data.referrals.map((row) => {
                  const where = stageOf(row);
                  return (
                    <StaggerItem
                      key={row.id}
                      className="flex items-center justify-between gap-10 rounded-13 border border-line bg-sur p-12"
                    >
                      <span>
                        <span
                          className={cn("block text-12.5 font-medium", where.tone)}
                        >
                          {where.text}
                        </span>
                        <span className="mt-2 block text-11 text-mut">
                          {row.referral_type === "driver" ? "كبتن" : "راكب"}
                        </span>
                      </span>
                      <span className="text-11.5 text-mut">
                        {row.rewarded && row.reward_amount
                          ? formatMoney(
                              row.reward_amount,
                              row.reward_currency ?? currency,
                            )
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
    </Screen>
  );
}
