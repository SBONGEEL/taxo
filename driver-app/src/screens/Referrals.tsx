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
 *
 * **بلغة TAXO 2.0** «C28» (`design/t2-new/captain/C28*.dc.html`): الرمزُ بطلُ الشاشة على الجمر الخافت (بطاقةُ «C10» «عمولة»)
 * وزرّا النسخ والمشاركة فيه، والبرنامجان صفوفٌ بمربّع «C12» ومبلغٍ بخطّ الأرقام، ومن سجّل قائمةٌ بنبرة مرحلته. **والمنطقُ حرفاً.**
 */

import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { Stagger, StaggerItem } from "@/components/ui/Motion";
import { getMyReferrals } from "@/api/endpoints";
import type { MyReferrals, ReferralProgram, ReferralStage } from "@/api/types";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { useSession } from "@/lib/session";
import { digits } from "@/lib/utils";
import { useGoBack } from "@/lib/back";
import { Icon } from "@/taxo2";

import "@/screens/t2/account.css";

/** أوّلُ شرطٍ ناقصٍ هو الجواب — وسردُ الثلاثة يخفي المطلوبَ الآن.
 *
 * **ولا «بانتظار إثبات الجنس» بعد التعميم**: كان شرطاً فصار علاوةً، فوسمُه
 * كان سيقول إن الإحالةَ متوقّفةٌ على ما لا يوقفها.
 *
 * **والنبرةُ اسمٌ لا صنفُ لون** (`ok` · `muted` · `warn` · `""` للحبر) — يرسمها صنفُ الشاشة بالرموز.
 */
function stageOf(row: ReferralStage): { text: string; tone: string } {
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
      text: `أكمل ${digits(String(row.rides_done))} من ${digits(
        String(row.rides_required),
      )} رحلات`,
      tone: "muted",
    };
  }
  // **فوق السقف يُقال، لا يُصمت عنه**: «مستحقّة ولن تُدفع» حقيقةٌ يملكها صاحبُها
  if (row.over_monthly_cap) {
    return { text: "فوق سقف هذا الشهر — لن تُدفع", tone: "warn" };
  }
  return { text: "استحقّت — المكافأة في الطريق", tone: "" };
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
    // **TAXO باللاتينية** (§٦٢/٢٠) — كان «تاكسو» في الرسالة التي يرسلها الكبتنُ لمن يدعوه
    const text = `سجّل في TAXO برمزي ${data.code}`;
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
    return (
      <span className="t2-ref-amount">
        <span className="t2-ref-amount-num" dir="ltr">
          {digits(program.reward_amount)}
        </span>
        <span className="t2-ref-amount-cur">{currency}</span>
      </span>
    );
  }

  return (
    <div className="t2 t2-ax">
      <div className="t2-ax-scroll">
        <div className="t2-head">
          <button type="button" className="t2-back" aria-label="رجوع" onClick={() => goBack()}>
            <Icon name="arrow_forward" />
          </button>
          <h1 className="t2-title">أَحِلْ صديقك</h1>
        </div>

        {error ? (
          <p className="t2-note danger" role="alert">
            <Icon name="error" />
            {error}
          </p>
        ) : null}
        {data === null ? (
          error ? null : (
            <div className="t2-ax-center">
              <span className="t2-ax-spin" role="status" aria-label="جارٍ التحميل" />
            </div>
          )
        ) : (
          <>
            <section className="t2-ref-code">
              <p className="t2-ref-code-k">رمز الإحالة الخاص بك</p>
              {/* **لاتينيٌّ ومتباعدُ الحروف**: يُقرأ ليُنطق ويُكتب في شاشةٍ أخرى */}
              <p dir="ltr" className="t2-ref-code-v">
                {data.code}
              </p>
              <div className="t2-ref-acts">
                <button
                  type="button"
                  onClick={() => void copy()}
                  className={copied ? "t2-ref-act done" : "t2-ref-act"}
                >
                  <Icon name={copied ? "check" : "content_copy"} />
                  {copied ? "نُسخ" : "انسخ"}
                </button>
                <button
                  type="button"
                  onClick={() => void share()}
                  className="t2-ref-act"
                >
                  <Icon name="share" />
                  شارك
                </button>
              </div>
            </section>

            {/* **رمزٌ واحدٌ وبرنامجان** — شرطُ المالك الثاني: النصُّ يشرح أن الرمز
                يعمل مع الاثنين وأن المكافأة تختلف بحسب من يسجّل به */}
            {pays ? (
              <>
                <h2 className="t2-section">رمزك واحدٌ، والمكافأةُ بحسب من يسجّل به</h2>
                <section className="t2-ref-programs">
                  {data.programs.map((program) => {
                    const active =
                      program.enabled && Number(program.reward_amount) > 0;
                    const isDriver = program.referral_type === "driver";
                    return (
                      <div key={program.referral_type} className="t2-ref-program">
                        <span className="t2-ax-tile sm accent" aria-hidden="true">
                          <Icon name={isDriver ? "local_taxi" : "person_add"} />
                        </span>
                        <div className="t2-ref-program-main">
                          <p className="t2-ref-program-title">
                            {isDriver ? "سجّل كبتناً" : "سجّل راكباً"}
                          </p>
                          <p className="t2-ref-program-cond">
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
                            <p className="t2-ref-program-bonus">
                              وإن كانت سائقةً موثَّقة:{" "}
                              {digits(program.female_total_amount)} {currency}{" "}
                              — الأساسُ وعلاوتُه معاً
                            </p>
                          ) : null}
                        </div>
                        {active ? amountOf(program) : <span className="t2-ref-amount off">—</span>}
                      </div>
                    );
                  })}

                  {/* **السقفُ قبل أن يدعو** — شرطُ المالك الثالث بحرفه */}
                  {cap !== undefined ? (
                    <p className={left === 0 ? "t2-ref-note warn" : "t2-ref-note"}>
                      {left === 0
                        ? `بلغتَ سقفَ هذا الشهر (${digits(String(cap))}). ما يُسجَّل بعده يبقى منسوباً لك ولا يُدفع حتى الشهر القادم.`
                        : `سقفُ هذا الشهر ${digits(String(cap))} إحالات — بقي لك ${digits(String(left))}.`}
                    </p>
                  ) : null}

                  <p className="t2-ref-note">
                    مجموع ما وصلك: {digits(data.total_rewarded)} {currency}
                  </p>
                </section>
              </>
            ) : (
              <section className="t2-ax-card t2-ref-how">
                <h2 className="t2-ref-how-title">كيف تعمل</h2>
                <p className="t2-ref-how-text">
                  شارك رمزك مع من تدعوه، فيكتبه عند التسجيل. وتُسجَّل الإحالةُ في
                  حسابك من الآن — والمكافأةُ تُعلن هنا متى حُدِّدت.
                </p>
              </section>
            )}

            <section>
              <h2 className="t2-section">من سجّل برمزك</h2>
              {data.referrals.length === 0 ? (
                <p className="t2-empty">لم يسجّل أحدٌ برمزك بعد.</p>
              ) : (
                <Stagger className="t2-ref-rows">
                  {data.referrals.map((row) => {
                    const where = stageOf(row);
                    const isDriver = row.referral_type === "driver";
                    return (
                      <StaggerItem key={row.id} className="t2-ref-row">
                        <span className="t2-ax-tile sm" aria-hidden="true">
                          <Icon name={isDriver ? "local_taxi" : "person"} />
                        </span>
                        <span className="t2-ref-row-main">
                          <span
                            className={where.tone ? `t2-ref-row-stage ${where.tone}` : "t2-ref-row-stage"}
                          >
                            {where.text}
                          </span>
                          <span className="t2-ref-row-kind">
                            {isDriver ? "كبتن" : "راكب"}
                          </span>
                        </span>
                        {row.rewarded && row.reward_amount ? (
                          <span className="t2-ref-amount">
                            <span className="t2-ref-amount-num sm" dir="ltr">
                              {digits(row.reward_amount)}
                            </span>
                            <span className="t2-ref-amount-cur">
                              {row.reward_currency
                                ? CURRENCY_LABEL[
                                    row.reward_currency as "JOD" | "LYD"
                                  ]
                                : currency}
                            </span>
                          </span>
                        ) : null}
                      </StaggerItem>
                    );
                  })}
                </Stagger>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
