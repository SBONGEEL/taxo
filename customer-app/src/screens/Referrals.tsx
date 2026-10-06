/** «ادعُ صديقك» — TAXO 2.0 «R25» (`design/t2-new/rider/R25-referrals.dc.html` · `R25b-…`)، **في المظهرين والنسائيّ** —
 *  رمزي ومن سجّل به (SPEC §9.1، تعميمُ 12-ح). **والرمزُ في بطاقة الرصيد من R11 بعينها** (الحبرُ وشريطاه وزرّا الجمر والحافّة).
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

import { ApiError } from "@/api/client";
import { getMyReferrals } from "@/api/endpoints";
import type { MyReferrals, ReferralProgram, ReferralStage } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { useSession } from "@/lib/session";
import { currencyLabel, formatMoney } from "@/lib/utils";
import { BlankT2, NoteT2, SubHeadT2 } from "@/screens/t2/KitT2";
import { Icon } from "@/taxo2";

import "@/screens/t2/t2.css";
import "@/screens/t2/account.css";

/** أوّلُ شرطٍ ناقصٍ هو الجواب — وسردُ الثلاثة يخفي المطلوبَ الآن. والنبرةُ معناه: نجاحٌ · انتظار · تنبيه · حبر. */
function stageOf(row: ReferralStage): { text: string; tone: "ok" | "muted" | "warn" | "ink" } {
  if (row.rewarded) return { text: "وصلت المكافأة", tone: "ok" };
  if (row.referral_type === "driver") {
    if (!row.driver_approved) {
      return { text: "حسابه قيد المراجعة", tone: "muted" };
    }
    if (!row.has_subscription) {
      return { text: "لم يشترِ اشتراكاً بعد", tone: "muted" };
    }
  }
  if (row.rides_done < row.rides_required) {
    return {
      text: `أكمل ${row.rides_done} من ${row.rides_required} رحلات`,
      tone: "muted",
    };
  }
  // **فوق السقف يُقال، لا يُصمت عنه**: «مستحقّة ولن تُدفع» حقيقةٌ يملكها صاحبُها
  if (row.over_monthly_cap) {
    return { text: "فوق سقف هذا الشهر — لن تُدفع", tone: "warn" };
  }
  return { text: "استحقّت — المكافأة في الطريق", tone: "ink" };
}

/** **المبلغُ بخطّين كما في R06**: الرقمُ بخطّ الأرقام، والعملةُ صغيرةً خافتة — والرقمُ من الخلفية كما وصل. */
function Amount({ value, currency, off = false }: { value: string; currency: string; off?: boolean }) {
  return (
    <span className={off ? "t2-amt off" : "t2-amt"}>
      <span dir="ltr" className="t2-num">
        {formatMoney(value)}
      </span>
      <span className="t2-amt-cur">{currencyLabel(currency)}</span>
    </span>
  );
}

export function ReferralsScreen() {
  const goBack = useGoBack("/account");
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
    return <Amount value={program.reward_amount} currency={currency} />;
  }

  return (
    <div className="t2 t2-page pb-nav">
      <SubHeadT2 title="ادعُ صديقك" onBack={goBack} />

      {error ? (
        <NoteT2 tone="danger" lead>
          {error}
        </NoteT2>
      ) : null}

      {data === null ? null : (
        <>
          <section className="t2-balance">
            <span className="t2-stripe a" aria-hidden="true" />
            <span className="t2-stripe b" aria-hidden="true" />
            <div className="t2-balance-label">رمز الدعوة الخاص بك</div>
            <div dir="ltr" className="t2-code-value">
              {data.code}
            </div>
            <div className="t2-balance-actions">
              <button type="button" className="t2-btn ember" onClick={() => void copy()}>
                <Icon name={copied ? "check" : "content_copy"} />
                {copied ? "نُسخ" : "انسخ"}
              </button>
              <button type="button" className="t2-btn ghost" onClick={() => void share()}>
                <Icon name="ios_share" />
                شارك
              </button>
            </div>
          </section>

          {pays ? (
            <>
              <div className="t2-section">رمزك واحدٌ، والمكافأةُ بحسب من يسجّل به</div>
              <div className="t2-list t2-sgroup">
                {data.programs.map((program) => {
                  const active = program.enabled && Number(program.reward_amount) > 0;
                  const isDriver = program.referral_type === "driver";
                  return (
                    <div key={program.referral_type} className="t2-prog">
                      <span className="t2-badge">
                        <Icon name={isDriver ? "local_taxi" : "person"} />
                      </span>
                      <div className="t2-prog-main">
                        <p className="t2-prog-title">{isDriver ? "سجّل كبتناً" : "سجّل راكباً"}</p>
                        <p className="t2-prog-cond">
                          {isDriver
                            ? `يُعتمد حسابه ويشتري اشتراكاً ويُكمل ${program.required_rides} رحلات`
                            : `يُكمل ${program.required_rides} رحلات`}
                        </p>
                        {/* **العلاوةُ بجانب الأساس بجملةٍ تقول المُحصَّل** */}
                        {isDriver && Number(program.female_bonus_amount) > 0 ? (
                          <p className="t2-prog-bonus">
                            وإن كانت سائقةً موثَّقة: {formatMoney(program.female_total_amount, currency)} — الأساسُ وعلاوتُه
                            معاً
                          </p>
                        ) : null}
                      </div>
                      {active ? amountOf(program) : <span className="t2-amt off">—</span>}
                    </div>
                  );
                })}
              </div>

              {/* **السقفُ قبل أن يدعو** — شرطُ المالك الثالث بحرفه */}
              {cap !== undefined ? (
                <NoteT2 tone={left === 0 ? "warn" : "plain"}>
                  {left === 0
                    ? `بلغتَ سقفَ هذا الشهر (${cap}). ما يُسجَّل بعده يبقى منسوباً لك ولا يُدفع حتى الشهر القادم.`
                    : `سقفُ هذا الشهر ${cap} دعوات — بقي لك ${left}.`}
                </NoteT2>
              ) : null}

              <NoteT2 tone="plain">مجموع ما وصلك: {formatMoney(data.total_rewarded, currency)}</NoteT2>
            </>
          ) : (
            <>
              <div className="t2-section">كيف تعمل</div>
              <p className="t2-howto">
                شارك رمزك مع من تدعوه، فيكتبه عند التسجيل. وتُسجَّل الدعوةُ في حسابك من الآن — والمكافأةُ تُعلن هنا متى
                حُدِّدت.
              </p>
            </>
          )}

          <div className="t2-section">من سجّل برمزك</div>
          {data.referrals.length === 0 ? (
            <BlankT2 icon="group" title="لم يسجّل أحدٌ برمزك بعد" />
          ) : (
            <div className="t2-list">
              {data.referrals.map((row) => {
                const where = stageOf(row);
                return (
                  <div key={row.id} className="t2-ref">
                    <span className="t2-badge">
                      <Icon name={row.referral_type === "driver" ? "local_taxi" : "person"} />
                    </span>
                    <div className="t2-ref-main">
                      <p className={`t2-ref-stage ${where.tone}`}>{where.text}</p>
                      <p className="t2-ref-who">{row.referral_type === "driver" ? "كبتن" : "راكب"}</p>
                    </div>
                    {row.rewarded && row.reward_amount ? (
                      <Amount value={row.reward_amount} currency={row.reward_currency ?? currency} />
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
