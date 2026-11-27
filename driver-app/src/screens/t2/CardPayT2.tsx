/** **الدفعُ بالبطاقة المصرفية** — اشتراكُ الكبتن ومستحقّاتُه ببطاقته البنكيّة (أمرُ المالك ٢٠٢٦-١١-١١، الأردن).
 *
 * **ما تقوله الصفحةُ قبل أن يدفع** — وكلُّه كما يصل من الخلفية، لا حسابَ هنا: المبلغُ بعملة سوقه، **وأنّ البطاقةَ تُخصم بالدولار** وبكم
 * لكلِّ دينار، **واسمُ شريك البطاقة ورسمُه على الدافع**، وأنّ الشريكَ قد يطلب هويّتَه أوّلَ مرّة، **وأنّ المبلغَ يصل TAXO أصلاً رقميّاً**.
 * **فلا يفاجئه شيءٌ في صفحة الشريك ولا في كشف حسابه** — والصدقُ في هذا شرطٌ دائمٌ لا يُرفع.
 *
 * **وصفحةُ البطاقة نفسُها صفحةُ الشريك** تُفتح كما تُفتح صفحاتُ الوسطاء (`goToCheckout`): **لا تمرّ بياناتُ البطاقة بخوادم TAXO**، والشريكُ
 * يمنع فتحَها داخل إطار (قِيس: `X-Frame-Options: DENY`) ويحتاج الكاميرا للتحقّق. **وشريطُ TAXO هنا** قبلها، والعودةُ إلى «نتيجة الدفع».
 *
 * **ولا شيءَ يتغيّر قبل أن يقول الوسيطُ «اكتمل»**: الاشتراكُ يُفعَّل أو المستحقّاتُ تُسدَّد في معاملة الاعتماد نفسِها.
 */

import { Capacitor } from "@capacitor/core";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listPaymentMethods, openPaymentCheckout } from "@/api/endpoints";
import type { PayMethod, PaymentRequestPurpose } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";
import { useCountryConfig } from "@/lib/config";
import { useDriver } from "@/lib/driver";
import { legalPages, openLegal } from "@/lib/legal";
import { goToCheckout, openedRequest } from "@/lib/pay-return";
import { PaymentEmailNote, emailRequired } from "@/screens/t2/PayDz";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits, formatAmount } from "@/lib/utils";
import { Icon, Wordmark } from "@/taxo2";

import "./fields.css";
import "./money.css";
import "./cardpay.css";
import { language, tr } from "@/lib/i18n";

/** **ما تحمله الشاشةُ التي فتحتها** — الغرضُ والمبلغُ كما حسبته الخلفية، والخطّةُ للاشتراك */
export interface CardPayHandoff {
  purpose: PaymentRequestPurpose;
  amount: string;
  planId?: string;
  planName?: string;
  /** **بالعملات الرقميّة** (MoonPay Commerce) لا بالبطاقة — الشاشةُ نفسُها بسطورها هي */
  crypto?: boolean;
}

/** **طريقةُ البطاقة المصرفية من طرق السوق** — هي وحدَها تحمل عملةَ خصمٍ أخرى */
export function bankCardMethod(methods: PayMethod[] | null | undefined, digistoreOn = true, freemiusOn = false): PayMethod | null {
  // **Whop أوّلاً حين يُعرض** (أمرُ المالك ٢٠٢٦-١١-١٣: طريقةُ الأردن الأساسيّة) — وإلا أيُّ وسيطِ بطاقةٍ مصرفيّةٍ في السوق
  // **وDigistore24 بمفتاح نسخته وحدَه** (أمرُ المالك ٢٠٢٦-١١-٢٣): الخادمُ يعرضه إن اشتعل مفتاحُ الموقع أو Play، **ونسخةُ Play لا ترسمه
  // ومفتاحُها مطفأ** — فلا يُذكر الدفعُ بالبطاقة فيها قبل موافقة Google
  // **وFreemius بمفتاح الموقع وحدَه** (أمرُ المالك ٢٠٢٦-١١-٢٦) — لا يُرسم في نسخة Play أبداً، ولا في «المستحقّات» (اشتراكٌ وحدَه)
  const cards =
    methods?.filter(
      (row) =>
        row.gateway &&
        row.charge_currency &&
        !row.crypto &&
        (digistoreOn || row.code !== DIGISTORE24) &&
        (freemiusOn || row.code !== FREEMIUS),
    ) ?? [];
  return cards.find((row) => row.code === "whop_card") ?? cards[0] ?? null;
}

/** **صفُّ Digistore24 في طرق السوق** (`0188`) */
export const DIGISTORE24 = "digistore24_card";

/** **صفُّ Freemius في طرق السوق** (`0194`) — البوّابةُ الاحتياطيّة، لنسخة الموقع وحدَها */
export const FREEMIUS = "freemius_card";

/** **طريقةٌ تُخصم بالدولار وتُعرض بالدينار وحدَه** (قرارُ المالك) — Digistore24 وFreemius بسطرٍ خفيفٍ واحد وحارسِ السعر نفسِه */
export function isUsdPass(method: PayMethod | null | undefined): boolean {
  return method?.code === DIGISTORE24 || method?.code === FREEMIUS;
}

/** **قناةُ هذه النسخة** — الغلافُ نسخةُ Play (وحزمةُ الموقع موقَّعةٌ من Play نفسِها)، والمتصفّحُ نسخةُ الموقع */
export function payChannel(): "web" | "play" {
  return Capacitor.isNativePlatform() ? "play" : "web";
}

/** **أيُشعَل Digistore24 في هذه النسخة؟** — مفتاحُ قناتها وحدَه (أمرُ المالك ٢٠٢٦-١١-٢٣) */
export function digistoreOnHere(features: Record<string, boolean> | null | undefined): boolean {
  if (!features) return false;
  return payChannel() === "play" ? features.digistore24_card_play_enabled === true : features.digistore24_card_enabled === true;
}

/** **أيُشعَل Freemius في هذه النسخة؟** — نسخةُ الموقع ومفتاحُها وحدَهما (أمرُ المالك ٢٠٢٦-١١-٢٦: «never in the Play build») */
export function freemiusOnHere(features: Record<string, boolean> | null | undefined): boolean {
  return payChannel() === "web" && features?.freemius_card_enabled === true;
}

/** **حارسُ السعر** (قرارُ المالك ٢٠٢٦-١١-٢٣) — طريقةٌ بمبالغَ ثابتةٍ تُدفع بها الخطّةُ التي يساويها ما يدفعه الكبتنُ الآن وحدَها؛
 *  وطريقةٌ بلا مبالغَ ثابتةٍ لأيِّ مبلغ. **والمقارنةُ بالمليم** — نصّان من الخادم لا حسابُ مال */
export function cardFits(method: PayMethod | null | undefined, amount: string | null | undefined): boolean {
  if (!method || amount == null) return false;
  const fixed = method.fixed_amounts ?? [];
  if (fixed.length === 0) return true;
  const mills = (value: string) => Math.round(Number(value) * 1000);
  return fixed.some((value) => mills(value) === mills(amount));
}

/** **طريقةُ العملات الرقميّة من طرق السوق** (MoonPay Commerce، أمرُ المالك ٢٠٢٦-١١-١٤) — لا عملةَ خصمٍ لها، وتُعرف بـ`crypto` */
export function cryptoMethod(methods: PayMethod[] | null | undefined): PayMethod | null {
  return methods?.find((row) => row.gateway && row.crypto) ?? null;
}

export function CardPayT2Screen() {
  const location = useLocation();
  const navigate = useNavigate();
  const handoff = (location.state ?? null) as CardPayHandoff | null;
  const goBack = useGoBack(handoff?.purpose === "subscription" ? "/subscription" : "/account/debt");
  const [method, setMethod] = useState<PayMethod | null | undefined>(undefined);
  const [currency, setCurrency] = useState<keyof typeof CURRENCY_LABEL | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // **بريدٌ يشترطه الوسيط وحسابُ الكابتن بلا بريد** (Freemius) — حقلُه هنا مرّةً ثمّ يتابع الدفعُ نفسُه؛ لا نصَّ «حدّث التطبيق» (قِيس ٢٠٢٦-١١-٢٧)
  const [needEmail, setNeedEmail] = useState(false);
  const { profile } = useDriver();
  const features = useCountryConfig(profile?.user?.country_code)?.features;

  // **عاد من صفحة البطاقة بزرّ الرجوع** (نسخةُ الموقع: الصفحةُ في النافذة نفسِها) — دفعةٌ فُتحت قبل قليل تُعرض نتيجتُها لا صفحةٌ جديدة:
  // «جارٍ تأكيد الدفع…» وزرُّ الإلغاء هناك، **فلا يُفتح طلبٌ ثانٍ والأوّلُ لم يُحسم**
  useEffect(() => {
    const open = openedRequest();
    if (open) navigate(`/wallet/pay/return?r=${encodeURIComponent(open)}`, { replace: true });
  }, [navigate]);

  useEffect(() => {
    if (!handoff) return;
    let alive = true;
    listPaymentMethods(handoff.purpose)
      .then((body) => {
        if (!alive) return;
        setCurrency(body.currency);
        setMethod(
          handoff.crypto
            ? cryptoMethod(body.methods)
            : bankCardMethod(body.methods, digistoreOnHere(features), freemiusOnHere(features)),
        );
      })
      .catch((caught: unknown) => {
        if (!alive) return;
        setMethod(null);
        setError(caught instanceof ApiError ? caught.message : tr("تعذّرت القراءة"));
      });
    return () => {
      alive = false;
    };
  }, [handoff, features]);

  async function pay() {
    if (!handoff || !method) return;
    setBusy(true);
    setError(null);
    try {
      const opened = await openPaymentCheckout({
        methodId: method.id,
        purpose: handoff.purpose,
        amount: handoff.amount,
        planId: handoff.purpose === "subscription" ? handoff.planId : undefined,
        channel: isUsdPass(method) ? payChannel() : undefined,
      });
      goToCheckout(opened.request.id, opened.checkout_url);
    } catch (caught) {
      if (emailRequired(caught)) setNeedEmail(true);
      else setError(caught instanceof ApiError ? caught.message : tr("تعذّر فتح صفحة الدفع — أعد المحاولة"));
      setBusy(false);
    }
  }

  const label = currency ? CURRENCY_LABEL[currency] : "";
  // **أقلُّ دفعٍ بالبطاقة** (قرارُ المالك ٢٠٢٦-١١-١١، حدُّ الطريقة من اللوحة) — تحتَه لا يُفتح الدفع ويُقال لماذا
  const floor = method?.min_amount ?? null;
  const belowFloor = handoff !== null && floor !== null && Number(handoff.amount) < Number(floor);
  // **Digistore24**: الدينارُ وحدَه على شاشات TAXO وسطرٌ خفيفٌ في الأسفل (قرارُ المالك ٢٠٢٦-١١-٢٣) — لا سعرَ دولار ولا سطرُ بنك
  const digistore = method?.code === DIGISTORE24;
  // **وFreemius مثلُه** (أمرُ المالك ٢٠٢٦-١١-٢٦): الدينارُ وحدَه، وسطرُ الدولار، وحارسُ السعر — **وسطرُ البريد بدل سطر الرمز البريديّ**
  const freemius = method?.code === FREEMIUS;
  const usdPass = digistore || freemius;
  const offPrice = usdPass && handoff !== null && !cardFits(method, handoff.amount);
  const termsUrl = legalPages(profile?.user?.country_code, language).find((page) => page.key === "terms")?.url ?? null;

  return (
    <div className="t2 t2-cardpay scr">
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label={tr("رجوع")} onClick={() => goBack()}>
          <Icon name="arrow_forward" />
        </button>
        <h1 className="t2-title">{handoff?.crypto ? tr("الدفع بالعملات الرقمية") : tr("الدفع بالبطاقة المصرفية")}</h1>
      </div>

      {/* **شريطُ TAXO** — قبل صفحة الشريك: من يدفع لمن، وأنّ البطاقةَ لا تصلنا */}
      <div className="t2-cardpay-bar">
        <Wordmark size={18} />
        <span className="t2-cardpay-bar-text">
          {handoff?.crypto ? tr("دفعٌ آمن من محفظتك الرقميّة — لا تصل مفاتيحُها إلى TAXO") : tr("دفعٌ آمن — بياناتُ بطاقتك لا تصل إلى TAXO")}
        </span>
        <Icon name="lock" />
      </div>

      {error ? (
        <p className="t2-note danger" role="alert">
          <Icon name="error" fill />
          {error}
        </p>
      ) : null}
      {needEmail ? (
        <PaymentEmailNote
          onSaved={() => {
            setNeedEmail(false);
            void pay();
          }}
        />
      ) : null}

      {!handoff ? (
        <p className="t2-note">{tr("افتح الدفعَ من صفحة الاشتراك أو من «المستحقّات عليك».")}</p>
      ) : method === undefined ? (
        <div className="t2-money-wait">
          <Spinner />
        </div>
      ) : method === null ? (
        <p className="t2-note">
          {handoff.crypto
            ? tr("الدفع بالعملات الرقمية غير متاح الآن — ادفع بكليك أو حاول لاحقاً.")
            : tr("الدفع بالبطاقة المصرفية غير متاح الآن — ادفع بكليك أو حاول لاحقاً.")}
        </p>
      ) : (
        <>
          <section className="t2-cardpay-total">
            <span className="t2-cardpay-k">
              {handoff.purpose === "subscription"
                ? tr("اشتراك {0}", { 0: handoff.planName ?? "" })
                : tr("سداد المستحقّات")}
            </span>
            <span className="t2-cardpay-amount">
              <span className="t2-cardpay-num" dir="ltr">
                {formatAmount(handoff.amount, currency)}
              </span>
              <span className="t2-cardpay-cur">{label}</span>
            </span>
          </section>

          {/* **ما يُقال قبل الدفع بالعملات الرقميّة** — كلُّه كما يقع: السعرُ بالدولار، ومن يحمل أيَّ رسم، وأن لا بطاقةَ ولا صورةَ هويّة،
              وأنّ الناقصَ لا يُضاف آليّاً */}
          {handoff.crypto ? (
            <ul className="t2-cardpay-facts">
              <li>
                <Icon name="info" />
                <span>
                  {tr("تدفع بعملةٍ رقميّةٍ من محفظتك (مثل USDC) بسعرٍ بالدولار الأمريكي: الدينار الواحد = {0} دولار.", {
                    0: digits(method.crypto_rate ?? ""),
                  })}
                </span>
              </li>
              <li>
                <Icon name="receipt_long" />
                <span>
                  {tr("يعالج الدفعَ {0}، ورسمُه تتحمّله TAXO؛ ورسمُ الشبكة تدفعه محفظتُك عند الإرسال.", {
                    0: method.partner ?? method.gateway_name ?? "MoonPay Commerce",
                  })}
                </span>
              </li>
              <li>
                <Icon name="account_balance" />
                <span>{tr("لا يمكن الدفعُ ببطاقةٍ بنكيّة هنا، ولا تطلب الصفحةُ صورةَ هويّة — تحتاج محفظةً رقميّةً فيها رصيد.")}</span>
              </li>
              <li>
                <Icon name="badge" />
                <span>{tr("أرسل المبلغَ الذي تطلبه الصفحةُ كاملاً — دفعٌ أقلُّ منه لا يُحتسب تلقائيّاً.")}</span>
              </li>
              <li>
                <Icon name="check_circle" />
                <span>
                  {handoff.purpose === "subscription"
                    ? tr("يُفعَّل اشتراكُك فورَ اكتمال الدفع. وإن لم يكتمل لا يُخصم شيءٌ من محفظتك.")
                    : tr("تُخصم مستحقّاتُك فورَ اكتمال الدفع، ويعود استقبالُ الطلبات حين تبلغ صفراً.")}
                </span>
              </li>
            </ul>
          ) : (
          <ul className="t2-cardpay-facts">
            {usdPass ? null : method.charge_rate ? (
              <li>
                <Icon name="credit_card" />
                <span>
                  {tr("تُخصم بطاقتك بالدولار الأمريكي: الدينار الواحد = {0} دولار.", { 0: digits(method.charge_rate) })}
                </span>
              </li>
            ) : null}
            {method.partner ? (
              <li>
                <Icon name="receipt_long" />
                <span>
                  {method.fee_payer === "taxo"
                    ? tr("تُعالج البطاقةَ شركةُ {0}، ورسمُها تتحمّله TAXO: تُخصم بطاقتك مستحقَّك وحدَه. واسمُها ما يظهر في كشف حسابك.", {
                        0: method.partner,
                      })
                    : tr("تُعالج البطاقةَ شركةُ {0}، ورسمُها على الدافع: {1}. واسمُها ما يظهر في كشف حسابك.", {
                        0: method.partner,
                        1: method.partner_fee ?? "",
                      })}
                </span>
              </li>
            ) : null}
            {method.charge_rate && !usdPass ? (
              <li>
                <Icon name="account_balance" />
                <span>{tr("وقد يضيف بنكُك رسمَ تحويل العملة، فيختلف ما في كشف حسابك قليلاً.")}</span>
              </li>
            ) : null}
            {/* **سطرا الشريك يُقالان حيث يقعان وحدَه** (NOWPayments) — وWhop لا يطلب هويّةً ولا يحوّل إلى أصلٍ رقميّ */}
            {method.partner_kyc !== false ? (
              <li>
                <Icon name="badge" />
                <span>{tr("قد يطلب الشريكُ أوّلَ مرّةٍ صورةَ هويّتك وصورةً شخصيّة للتحقّق.")}</span>
              </li>
            ) : null}
            {method.settles_digital !== false ? (
              <li>
                <Icon name="info" />
                <span>{tr("يحوّل الشريكُ المبلغَ إلى أصلٍ رقميٍّ يصل حسابَ TAXO.")}</span>
              </li>
            ) : null}
            <li>
              <Icon name="check_circle" />
              <span>
                {handoff.purpose === "subscription"
                  ? tr("يُفعَّل اشتراكُك فورَ اكتمال الدفع. وإن لم يكتمل لا يُخصم شيءٌ من محفظتك.")
                  : tr("تُخصم مستحقّاتُك فورَ اكتمال الدفع، ويعود استقبالُ الطلبات حين تبلغ صفراً.")}
              </span>
            </li>
          </ul>
          )}

          {offPrice ? (
            <p className="t2-note">{tr("هذا المبلغ لا يُدفع بالبطاقة الآن — ادفع بكليك أو من محفظتك.")}</p>
          ) : belowFloor && floor !== null ? (
            <p className="t2-note">{tr("أقلُّ دفعٍ بالبطاقة {0} {1} — للمبالغ الأصغر ادفع بكليك.", { 0: formatAmount(floor, currency), 1: label })}</p>
          ) : (
            <button type="button" className="t2-debt-cta" disabled={busy || method.down === true} onClick={() => void pay()}>
              {busy ? tr("جارٍ…") : handoff.crypto ? tr("تابع إلى صفحة الدفع") : tr("تابع إلى صفحة البطاقة")}
            </button>
          )}
          {method.down ? (
            <p className="t2-note">{tr("صفحة البطاقة متوقّفة الآن — حاول بعد قليل أو ادفع بكليك.")}</p>
          ) : null}
          {usdPass ? <p className="t2-cardpay-fine">{tr("سيتم خصم القيمة من البطاقة بما يعادلها بالدولار")}</p> : null}
          {/* **Freemius يُربط بالبريد** (صفحتُه لا تحمل مرجعَنا) — فيُقال قبل فتحها أن يبقى البريدُ كما هو */}
          {freemius ? <p className="t2-cardpay-fine">{tr("أبقِ بريدك في صفحة الدفع كما هو — به يُفعَّل اشتراكك")}</p> : null}
          {/* **الرمزُ البريديُّ يكتبه الكبتن** (قرارُ المالك ٢٠٢٦-١١-٢٤): صفحةُ Digistore24 تشترطه للأردن ولا مدينةَ في الحساب — فيُقال قبل فتحها */}
          {digistore ? <p className="t2-cardpay-fine">{tr("ستُسأل عن الرمز البريدي لمدينتك، واختر «شخص خاص»")}</p> : null}
          <button type="button" className="t2-link" onClick={() => navigate(-1)}>
            {tr("تراجع")}
          </button>
          {/* **رابطٌ صغيرٌ عاديٌّ إلى شروط الكابتن وحدَه** (قرارُ المالك ٢٠٢٦-١١-٢٧): بندُ الاسترداد في الشروط بين بنودها، **ولا نصَّ
              استردادٍ على هذه الشاشة** — لا شريطَ ولا تمييزَ ولا نافذة */}
          {termsUrl ? (
            <p className="t2-cardpay-fine">
              <button type="button" className="t2-cardpay-terms" onClick={() => openLegal(termsUrl)}>
                {tr("الشروط والسياسات")}
              </button>
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}
