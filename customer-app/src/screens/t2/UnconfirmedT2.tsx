/** **«رحلةٌ لم يكتمل دفعها»** — R31 (`design/PAYMENTS-UNCONFIRMED.md` §٦، SPEC §٦٤-ز) — **بلا لوحة**: تُركَّب من عُدّة TAXO 2.0
 * القائمة — طبقةُ الدفع (`t2-m-stage` · بطاقةُ المبلغ · الورقةُ فوق الشاشة) ومنتقي القناة وسطرُ النسخ — فتشبه أخواتها بلا لونٍ جديد.
 *
 * **موضعُها بعد الترحيب مباشرةً وقبل الرئيسية** (`App.tsx::UnconfirmedOpening`)، صفحةٌ كاملةٌ لا ورقةٌ تُسحب ولا توستٌ يزول، **والأقدمُ
 * أوّلاً** كما ترسلها الخلفية. **و«لاحقاً» يُخفيها لهذه الفتحة وحدَها** — وتعود في التالية حتى تُحسم، وفي أعلى الرئيسية شريطٌ صغيرٌ
 * «تأكيدٌ ينتظرك» يفتحها (`UnconfirmedStripT2`). **وحين يبلغ الحدّ** يصير «لاحقاً» «ابقَ في الرئيسية» ويُقال المنعُ بسببه.
 *
 * **حازمةٌ لا عدوانية** (§٦): عنوانٌ واحد، والمبلغُ كبيراً، وما يُطلب فعلُه زرّاً — **بلا أحمرَ إلا للحدّ**، وبلا علاماتِ تعجّب.
 *
 * **ولا يُحسب هنا مالٌ ولا حال** (§14): المبلغُ كما أرسلته الخلفية، والحالُ (`state`) منها، **وبعد كلِّ فعلٍ يُسأل البابُ ثانيةً**
 * (`lib/payment.ts`) — فالبطاقةُ لا «تتوقّع» ما صار.
 *
 * **وما لم يُبنَ — بعلّته**:
 * - **«افتح تطبيق بنكي»** (§٤-٢/١): يحتاج قائمةَ بنوك الأردن بأسماء حزمها، **ولا قائمةَ في الشيفرة** — فلا زرَّ يَعِد بفتح بنكٍ لا
 *   نعرفه. والنسخُ وحدَه هو الموثوق، ويُقال ذلك في الورقة.
 * - **«أضف ما يثبت ذلك»** بعد «سلّمتُه» (§٦): صورةُ الإيصال لم تُبنَ في الخلفية (§٦٤-ز) — فالزرُّ «سلّمتُه» وحدَه، وهو إقرارٌ يصل
 *   المشرفَ مع النزاع.
 */

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import type { RiderUnconfirmed, RiderUnconfirmedItem } from "@/api/types";
import { CardChoice } from "@/components/payment/CardChoice";
import { CopyRow } from "@/components/payment/CliqPanel";
import { PAY_ICON_T2 } from "@/components/payment/PaymentPicker";
import { useCountryConfig, useFeature } from "@/lib/config";
import { PAYMENT_METHOD_LABEL } from "@/lib/labels";
import {
  UNCONFIRMED_FLAG,
  changeUnconfirmedMethod,
  channelsFor,
  declareCashHandover,
  needsRider,
  useUnconfirmed,
  type PayableMethod,
  type PaymentChannel,
} from "@/lib/payment";
import { useSession } from "@/lib/session";
import { currencyLabel, formatMoney, newIdempotencyKey } from "@/lib/utils";
import { Icon } from "@/taxo2";

import { BannerT2, BusyLabel, HeadT2, SheetModalT2, WaitT2 } from "./MoneyT2";
import { startOfToday, whenParts } from "./when";

import "./t2.css";
import "./money.css";
import "./unconfirmed.css";

/** **نصُّ الحدّ كما كتبه التصميم** (§٦ «الحدّ») — وهو نصُّ ٤٠٢ `unconfirmed_payment_blocked` نفسُه في الخلفية. */
const LIMIT_TEXT = "لا يمكن طلبُ رحلةٍ جديدةٍ حتى يُحسم دفعُ هذه الرحلة";

/** «الكبتن زيد» — **الاسمُ الأوّل في سطر الرحلة** (§٦)، والكاملُ لورقة كليك وحدَها: به يطابق الراكبُ ما يراه في بنكه. */
function firstName(name: string | null): string | null {
  const parts = (name ?? "").trim().split(/\s+/);
  return parts[0] ? parts[0] : null;
}

/** «رحلةٌ لم يكتمل دفعها» · «رحلتان…» · «3 رحلاتٍ…» — **تمييزُ العدد بالعربية** (رحلة · رحلتان · رحلات · رحلةً) لا «3 رحلة». */
function ridesLine(count: number): string {
  if (count === 1) return "رحلةٌ لم يكتمل دفعها";
  if (count === 2) return "رحلتان لم يكتمل دفعهما";
  if (count <= 10) return `${count} رحلاتٍ لم يكتمل دفعها`;
  return `${count} رحلةً لم يكتمل دفعها`;
}

/** «أمس 22:04» — يومٌ وساعةٌ بخاناتٍ لاتينية (`when.ts`)؛ والساعةُ في `ltr` كي لا تنقلب خاناتُها. **و«أمس · 21:58»** بنقطةٍ في سطر
 *  الرحلة كما كتبه التصميم (§٦). */
function When({ iso, today, dot = false }: { iso: string; today: number; dot?: boolean }) {
  const at = whenParts(iso, today);
  return (
    <>
      {at.day}
      {dot ? " · " : " "}
      <span dir="ltr">{at.time}</span>
    </>
  );
}

export function UnconfirmedT2Screen() {
  const navigate = useNavigate();
  const { user } = useSession();
  const owner = user?.id ?? null;
  const enabled = useFeature(user?.country_code, UNCONFIRMED_FLAG);
  const country = useCountryConfig(user?.country_code);
  const data = useUnconfirmed(enabled);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [changing, setChanging] = useState<RiderUnconfirmedItem | null>(null);
  const [copying, setCopying] = useState<RiderUnconfirmedItem | null>(null);
  const today = startOfToday();

  const waiting = (data?.items ?? []).filter(needsRider);

  // **مطفأً لا صفحة** — المفتاحُ يحكم المسارَ كلَّه، ورابطٌ قديمٌ إليها يعود إلى الرئيسية
  useEffect(() => {
    if (!enabled) navigate("/", { replace: true });
  }, [enabled, navigate]);

  // **حُسم كلُّ ما بيده ⇒ الرئيسية** — وما بقي بيد الكبتن يقوله شريطُها («لا يلزمك شيء»)، لا صفحةٌ بلا فعل
  useEffect(() => {
    if (data !== null && waiting.length === 0) navigate("/", { replace: true });
  }, [data, waiting.length, navigate]);

  const leave = () => navigate("/", { replace: true });

  async function declare(item: RiderUnconfirmedItem) {
    if (!item.payment_id || !owner) return;
    setBusy(item.payment_id);
    setError(null);
    setDone(null);
    try {
      await declareCashHandover(owner, item.payment_id);
      // **ما يقع بعد الإقرار بحسب الحال لا جملةٌ واحدة**: على المعلَّق ينتظر الكبتن؛ **وعلى النزاع** قال الكبتنُ كلمتَه (أو أحاله
      // المشرف) فلا «بانتظار تأكيده» — الإقرارُ روايةٌ تصل فريقَ TAXO مع النزاع (§٢-٣)
      setDone(
        item.state === "disputed"
          ? "سُجّل إقرارُك — يصل فريقَ TAXO مع النزاع."
          : "سُجّل إقرارُك — بانتظار تأكيد الكبتن، ولا يلزمك شيء.",
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر تسجيل الإقرار");
    } finally {
      setBusy(null);
    }
  }

  if (data === null) {
    return (
      <div className="t2 t2-m-stage t2-uc">
        <HeadT2 title="رحلةٌ لم يكتمل دفعها" />
        <WaitT2 label="نقرأ ما ينتظرك…" />
      </div>
    );
  }

  return (
    <div className="t2 t2-m-stage t2-uc">
      {/* **عنوانٌ واحدٌ بلا سهم** (§٦): «لا تُغلق إلى صمت» — مخرجُها «لاحقاً» في القاع، وزرُّ الجهاز يعود كما يعود منها */}
      <HeadT2 title="رحلةٌ لم يكتمل دفعها" />

      {/* **الحدُّ وحدَه بالأحمر** — حين صار الطلبُ الجديدُ ممنوعاً فعلاً (`blocked` هو حكمُ «اطلب رحلة» نفسُه) */}
      {data.blocked ? (
        <div className="t2-m-banner danger" role="alert">
          <Icon name="error" />
          <span>{LIMIT_TEXT}</span>
        </div>
      ) : null}
      <BannerT2 tone="danger" message={error} />
      <BannerT2 tone="ok" message={done} />

      <div className="t2-uc-list">
        {waiting.map((item) => (
          <ItemCard
            key={item.payment_id ?? item.ride_id}
            item={item}
            today={today}
            busy={busy !== null && busy === item.payment_id}
            onDeclare={() => void declare(item)}
            onChange={() => {
              setError(null);
              setChanging(item);
            }}
            onCopy={() => setCopying(item)}
            onPay={() => navigate(`/rides/${item.ride_id}/pay`)}
          />
        ))}
      </div>

      <div className="t2-m-push" />

      {/* **«لاحقاً» لهذه الفتحة وحدَها** (§٦) — وعند الحدّ «ابقَ في الرئيسية»: لا «لاحقاً» لما يمنع الآن */}
      <button type="button" className="t2-button secondary t2-m-cta t2-uc-later" onClick={leave}>
        {data.blocked ? "ابقَ في الرئيسية" : "لاحقاً"}
      </button>

      {changing ? (
        <ChangeMethodSheet
          item={changing}
          owner={owner}
          channels={channelsFor(country)}
          onClose={() => setChanging(null)}
          onChanged={(message) => {
            setChanging(null);
            setDone(message);
          }}
        />
      ) : null}

      {copying ? (
        <CopySheet
          item={copying}
          onClose={() => setCopying(null)}
          onReference={() => navigate(`/rides/${copying.ride_id}/pay`)}
        />
      ) : null}
    </div>
  );
}

/** **بطاقةُ رحلةٍ واحدة** — «أمس · 21:58 · الشميساني ← دابوق · الكبتن زيد» ثمّ «3.364 د.أ · كاش» ثمّ ما يُطلب فعلُه (§٦). */
function ItemCard({
  item,
  today,
  busy,
  onDeclare,
  onChange,
  onCopy,
  onPay,
}: {
  item: RiderUnconfirmedItem;
  today: number;
  busy: boolean;
  onDeclare: () => void;
  onChange: () => void;
  onCopy: () => void;
  onPay: () => void;
}) {
  const captain = firstName(item.captain_name);
  const route =
    item.pickup_address && item.dropoff_address ? `${item.pickup_address} ← ${item.dropoff_address}` : null;

  return (
    <section className="t2-m-card t2-uc-card">
      <p className="t2-uc-trip">
        <When iso={item.completed_at} today={today} dot />
        {route ? ` · ${route}` : ""}
        {captain ? ` · الكبتن ${captain}` : ""}
      </p>
      {/* **المبلغُ كبيراً** (§٦) — كما أرسلته الخلفية، والعملةُ من رمزها */}
      <div className="t2-m-amount">
        <span dir="ltr" className="t2-m-num lg">
          {formatMoney(item.amount)}
        </span>
        <span className="t2-m-cur">{currencyLabel(item.currency)}</span>
        <span className="t2-uc-method">· {PAYMENT_METHOD_LABEL[item.method]}</span>
      </div>

      {item.state === "payment_due" ? (
        // **أجرةٌ مستحقّةٌ ولا صفَّ عليها** — حكمُ «غيرُ مدفوع» أو دفعٌ سقط (`schemas/unconfirmed_payment.py`): بابُها شاشةُ الدفع
        <>
          <p className="t2-uc-note">لم يكتمل دفعُ هذه الرحلة — ادفعها بالطريقة التي تناسبك.</p>
          <div className="t2-uc-acts">
            <button type="button" className="t2-button action t2-m-cta" onClick={onPay}>
              ادفع الآن
            </button>
          </div>
        </>
      ) : item.state === "disputed" ? (
        // **نزاعُ كاش** (§٢-٣/§٦) — للكاش وحدَه هنا (`needsRider`): «سلّمتُه» روايتُه للمشرف، و«سأدفع الآن» يُلغي المتنازَعَ عليه
        // ويفتح ما يدفع به (`DISPUTED → VOIDED`).
        //
        // **وعنوانُه صادقٌ أيّاً كان من فتحه — ولذلك ليس نصَّ التصميم حرفاً**: §٦ كتب «الكبتنُ يقول إنه لم يستلم المبلغ» لنزاعٍ فتحه
        // الكبتنُ بـ«لم يدفع»، **والنزاعُ نفسُه يفتحه المشرفُ أيضاً** بـ«حوّل إلى نزاع» (§٥، `admin_dispute`) — وحمولةُ الراكب لا تقول
        // مَن فتحه (`RiderUnconfirmedItem`). فجملةٌ تنسب إلى الكبتن ما لم يقله كذبٌ في نصف الحالات؛ و«لم يؤكّد الكبتنُ استلامَه» صادقةٌ
        // في الثلاث (لم يدفع · اعتراضٌ بعد إتمامٍ آليّ · إحالةُ المشرف). **ويعود نصُّ التصميم** حين تنشر الخلفيةُ من فتح النزاع.
        //
        // **و`dispute_reason` لا يُرسم هنا البتّة**: في إحالة المشرف هو **سببُه المكتوب لسجلّ التدقيق** («السبب (يدخل سجلَّ
        // التدقيق)» في اللوحة) — ملاحظةُ موظفٍ يظنّها داخليّة، **تُعرض على الراكب منسوبةً إلى كبتنه**. والواجهةُ لا تفرّق سببَ كبتنٍ
        // من سببِ مشرف، فلا يُعرض أيٌّ منهما.
        <>
          <div className="t2-callout warn t2-uc-callout">
            <Icon name="gavel" />
            <div className="t2-callout-main">
              <p className="t2-callout-title">لم يؤكّد الكبتنُ استلامَ المبلغ</p>
              <p className="t2-callout-body">
                {item.declared_at ? (
                  <>
                    أقررتَ بالتسليم <When iso={item.declared_at} today={today} /> — يفصل فريقُ TAXO في النزاع.
                  </>
                ) : (
                  <>الدفعُ في نزاعٍ يفصل فيه فريقُ TAXO — إن سلّمتَه فقل ذلك، أو ادفعه الآن.</>
                )}
              </p>
            </div>
          </div>
          <div className="t2-uc-acts pair">
            {item.declared_at ? null : (
              <button type="button" className="t2-button secondary" disabled={busy} aria-busy={busy} onClick={onDeclare}>
                <BusyLabel busy={busy}>سلّمتُه</BusyLabel>
              </button>
            )}
            <button type="button" className="t2-button action" disabled={busy} onClick={onChange}>
              سأدفع الآن
            </button>
          </div>
        </>
      ) : item.method === "cliq" ? (
        // **كليك: المرجعُ إلزاميٌّ ومنه تبدأ ساعةُ الكبتن** (§٢-٤) — الإدخالُ في شاشة الدفع القائمة، والنسخُ هنا (§٤-٢/١)
        <div className="t2-uc-acts">
          <button type="button" className="t2-button action t2-m-cta" onClick={onPay}>
            أدخل مرجع الحوالة
          </button>
          <div className="t2-uc-acts pair">
            <button type="button" className="t2-button secondary" onClick={onCopy}>
              انسخ بيانات التحويل
            </button>
            <button type="button" className="t2-button secondary" onClick={onChange}>
              غيّر طريقة الدفع
            </button>
          </div>
        </div>
      ) : (
        // **الكاش** (§٢-٣): الراكبُ يقرّ بما خرج من يده — «لم أسلّمه بعد» يفتح الدفعَ القائم
        <div className="t2-uc-acts">
          <button
            type="button"
            className="t2-button action t2-m-cta"
            disabled={busy}
            aria-busy={busy}
            onClick={onDeclare}
          >
            <BusyLabel busy={busy}>سلّمتُ المبلغ للكبتن</BusyLabel>
          </button>
          <div className="t2-uc-acts pair">
            <button type="button" className="t2-button secondary" disabled={busy} onClick={onChange}>
              غيّر طريقة الدفع
            </button>
            <button type="button" className="t2-button secondary" disabled={busy} onClick={onPay}>
              لم أسلّمه بعد
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

/** **ما يُقال بعد التبديل** — بالقناة الجديدة: المحفظةُ تُسوّى لحظتَها، والكاشُ وكليك صفٌّ معلَّقٌ جديدٌ ينتظر خطوتَه. */
const CHANGED: Record<PayableMethod, string> = {
  wallet: "دُفعت من محفظتك — اكتمل دفعُ الرحلة.",
  card: "دُفعت بالبطاقة — اكتمل دفعُ الرحلة.",
  cliq: "صار الدفعُ عبر كليك — حوّل ثمّ أدخل مرجع الحوالة.",
  cash: "صار الدفعُ كاشاً — سلّم المبلغ للكبتن ثمّ أقِرّ بالتسليم.",
};

/** **«غيّر طريقة الدفع» و«سأدفع الآن»** (§٢-١ · §٦) — **بابٌ واحدٌ** (`POST /payments/{id}/change-method`) بحمل الدفع حرفاً.
 *
 * - **على معلَّقٍ**: الطريقةُ الحاليةُ لا تُعرض (الخلفيةُ تردّها ٤٢٢ — «هذه طريقتُك الآن»).
 * - **على نزاع كاش** («سأدفع الآن»): كلُّ قناة، **ولو كاشاً ثانيةً** يسلّمه الآن.
 * - **البطاقةُ** خطوتُها الوسطى نفسُها (`CardChoice`) ثمّ صفحةُ المزوّد — والعودةُ منها تسأل عن الحال كما في شاشة الدفع.
 *
 * **ومفتاحُ عدم التكرار لكلِّ قناةٍ ما دامت الورقة**: إعادةُ المحاولة بالمفتاح نفسِه لا تدفع مرّتين، وقناةٌ أخرى بمفتاحها. **وسقوطُ
 * الجديد** (رصيدٌ لا يكفي · قناةٌ مطفأة · كاشٌ موقوفٌ لحسابه) **يُبقي القديمَ كما كان**، ورسالتُه هنا كما وصلت.
 */
function ChangeMethodSheet({
  item,
  owner,
  channels,
  onClose,
  onChanged,
}: {
  item: RiderUnconfirmedItem;
  /** صاحبُ الصفحة — **يُسأل البابُ بعد التبديل له وحدَه** (`lib/payment.ts`: المخزنُ لحسابٍ واحد) */
  owner: string | null;
  channels: PaymentChannel[];
  onClose: () => void;
  onChanged: (message: string) => void;
}) {
  const keys = useRef(new Map<PayableMethod, string>());
  const [busy, setBusy] = useState<PayableMethod | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [card, setCard] = useState(false);
  const payNow = item.state === "disputed";
  const options = payNow ? channels : channels.filter((channel) => channel.method !== item.method);

  async function pick(method: PayableMethod, extras: { save_card?: boolean; saved_card_id?: string } = {}) {
    if (!item.payment_id || !owner) return;
    setBusy(method);
    setError(null);
    try {
      const key =
        keys.current.get(method) ?? newIdempotencyKey(`chg-${method}-${item.payment_id.slice(0, 8)}`);
      keys.current.set(method, key);
      const state = await changeUnconfirmedMethod(owner, item.payment_id, method, key, extras);
      // **البطاقةُ تعود برابط صفحة المزوّد** — والعودةُ منها تسأل عن الحال (`CardReturn`)، كما في شاشة الدفع حرفاً
      const redirect = state.card_order?.redirect_url;
      if (method === "card" && redirect) {
        sessionStorage.setItem("taxo.card_return_ride", item.ride_id);
        window.location.assign(redirect);
        return;
      }
      onChanged(CHANGED[method]);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر تبديل طريقة الدفع");
      setCard(false);
    } finally {
      setBusy(null);
    }
  }

  if (card) {
    return <CardChoice busy={busy === "card"} onPay={(extras) => void pick("card", extras)} onCancel={() => setCard(false)} />;
  }

  return (
    <SheetModalT2 onClose={busy ? null : onClose}>
      <p className="t2-m-sheet-title">{payNow ? "سأدفع الآن" : "غيّر طريقة الدفع"}</p>
      <p className="t2-m-sheet-sub">
        <b dir="ltr" className="t2-m-strong">
          {formatMoney(item.amount, item.currency)}
        </b>{" "}
        {payNow
          ? "— يُطوى النزاعُ بدفعتك الجديدة."
          : `— بدل ${PAYMENT_METHOD_LABEL[item.method]}، والطريقةُ الجديدةُ تحلّ محلَّها.`}
      </p>
      <BannerT2 tone="danger" message={error} />
      {options.length === 0 ? (
        <p className="t2-m-hint">لا طريقةَ أخرى متاحةٌ في بلدك الآن.</p>
      ) : (
        <div className="t2-list t2-m-gap">
          {options.map(({ method, hint }) => (
            <button
              key={method}
              type="button"
              className="t2-row t2-m-opt"
              disabled={busy !== null}
              aria-busy={busy === method}
              onClick={() => (method === "card" ? setCard(true) : void pick(method))}
            >
              <Icon name={PAY_ICON_T2[method]} />
              <span className="t2-row-main">
                <span className="t2-row-title">{PAYMENT_METHOD_LABEL[method]}</span>
                <span className="t2-row-body">{hint}</span>
              </span>
              {busy === method ? (
                <span className="t2-m-btn-spin t2-m-opt-end" aria-hidden="true" />
              ) : (
                <Icon name="chevron_left" className="t2-m-opt-end go" />
              )}
            </button>
          ))}
        </div>
      )}
    </SheetModalT2>
  );
}

/** **«انسخ بيانات التحويل»** (§٤-٢/١) — **النسخُ لا المسح**: TAXO يعرف الاسمَ المستعارَ للكبتن، فثلاثةُ أسطرٍ بزرِّ نسخٍ لكلٍّ —
 *  الاسمُ المستعار · المبلغُ بالضبط · مرجعُ TAXO (يُكتب في ملاحظة الحوالة) — **واسمُ الكبتن كما يراه البنك** فيطابقه الراكبُ قبل أن
 *  يرسل. والمبلغُ يُنسخ كما أرسلته الخلفيةُ بخاناته الثلاث، **وعملتُه في تسميته**. **ولا «افتح تطبيق بنكي»** — رأسُ الملفّ. */
function CopySheet({
  item,
  onClose,
  onReference,
}: {
  item: RiderUnconfirmedItem;
  onClose: () => void;
  onReference: () => void;
}) {
  const [copied, setCopied] = useState<string | null>(null);

  async function copy(value: string | null, label: string) {
    if (!value) return;
    await navigator.clipboard?.writeText(value).catch(() => undefined);
    setCopied(label);
    window.setTimeout(() => setCopied(null), 2_000);
  }

  return (
    <SheetModalT2
      onClose={onClose}
      footer={
        <div className="t2-m-foot">
          <button type="button" className="t2-button action t2-m-cta" onClick={onReference}>
            حوّلتُ — أدخل مرجع الحوالة
          </button>
          <button type="button" className="t2-m-link" onClick={onClose}>
            إغلاق
          </button>
        </div>
      }
    >
      <p className="t2-m-sheet-title">بيانات التحويل</p>
      <p className="t2-m-sheet-sub">انسخ كلَّ سطرٍ ثمّ الصقه في تطبيق بنكك — والمرجعَ في ملاحظة الحوالة.</p>
      <dl className="t2-m-copies">
        <CopyRow
          label="الاسم المستعار للكبتن"
          value={item.cliq_alias ?? "—"}
          copied={copied === "alias"}
          onCopy={() => void copy(item.cliq_alias, "alias")}
        />
        <CopyRow
          label={`المبلغ بالضبط (${currencyLabel(item.currency)})`}
          value={item.amount}
          copied={copied === "amount"}
          onCopy={() => void copy(item.amount, "amount")}
        />
        <CopyRow
          label="مرجع TAXO (اكتبه في ملاحظة الحوالة)"
          value={item.cliq_reference ?? "—"}
          copied={copied === "reference"}
          onCopy={() => void copy(item.cliq_reference, "reference")}
        />
      </dl>
      {/* **التحقّقُ الحقيقيُّ اسمُ المستفيد في بنكه** (§٤-١ «Payee Confirmation») — به يعرف أن المالَ يذهب إلى كبتنه */}
      {item.captain_name ? (
        <div className="t2-callout t2-m-callout">
          <Icon name="verified_user" />
          <div className="t2-callout-main">
            <p className="t2-callout-title">ستظهر في بنكك باسم: {item.captain_name}</p>
            <p className="t2-callout-body">طابِق الاسمَ قبل أن ترسل — اسمٌ غيرُه يعني أن الحوالةَ لا تذهب إلى كبتن رحلتك.</p>
          </div>
        </div>
      ) : null}
    </SheetModalT2>
  );
}

/** **شريطُ الرئيسية** (§٦) — صغيرٌ في أعلاها، **ولا يُرسم إلا بشرطه**:
 *
 * - **الحدّ** (`blocked`): «لا يمكن طلبُ رحلةٍ جديدةٍ…» بالأحمر، ولمستُه تفتح الصفحة.
 * - **ما بيده** (`needsRider`): «تأكيدٌ ينتظرك» — ولمستُه تفتح الصفحة.
 * - **وإلا فما بيد غيره** — «أقررتَ بالتسليم أمس 22:04 — بانتظار تأكيد الكبتن. **لا يلزمك شيء**» (شريطٌ لا صفحة، §٦)، ومرجعُ كليك
 *   بالجملة نفسِها، **ونزاعُ كليك** بيد فريق TAXO. **سطرٌ يُقرأ لا زرٌّ**: لا شيءَ يُفعل.
 */
export function UnconfirmedStripT2({
  data,
  onOpen,
}: {
  data: RiderUnconfirmed | null | undefined;
  onOpen: () => void;
}) {
  if (!data || data.items.length === 0) return null;
  const today = startOfToday();

  if (data.blocked) {
    return (
      <button type="button" className="t2-uc-strip danger" onClick={onOpen}>
        <Icon name="error" fill className="t2-uc-strip-icon" />
        <span className="t2-uc-strip-text">{LIMIT_TEXT}</span>
        <Icon name="chevron_left" className="t2-uc-strip-go" />
      </button>
    );
  }

  const waiting = data.items.filter(needsRider);
  if (waiting.length > 0) {
    return (
      <button type="button" className="t2-uc-strip" onClick={onOpen}>
        <Icon name="payments" className="t2-uc-strip-icon" />
        <span className="t2-uc-strip-text">
          <b>تأكيدٌ ينتظرك</b>
          <span className="t2-uc-strip-sub">{ridesLine(waiting.length)}</span>
        </span>
        <Icon name="chevron_left" className="t2-uc-strip-go" />
      </button>
    );
  }

  const first = data.items[0];
  return (
    <div className="t2-uc-strip quiet" role="status">
      <Icon name={first.state === "disputed" ? "gavel" : "hourglass_top"} className="t2-uc-strip-icon" />
      <span className="t2-uc-strip-text">
        {first.state === "disputed" ? (
          // **نصٌّ صادقٌ في الطرق الثلاث** التي يصير بها كليك نزاعاً: «لم تصلني» من الكبتن · انقضاءُ المهلة بلا ردّه
          // (`AUTO_DISPUTE_REASON` — لم يقل الكبتنُ شيئاً) · إحالةُ المشرف ولو بلا مرجع (فلا حوالةَ خرجت أصلاً). **ولا يُنسب
          // إلى الكبتن ما لم يقله** — والمرجعُ لا يُدخَل على نزاع (`submit_cliq_reference` يقبل المعلَّقَ وحدَه)، فـ«لا يلزمك شيء» صادقة
          <>دفعُ هذه الرحلة في نزاعٍ لدى فريق TAXO — يفصل فيه، ولا يلزمك شيء</>
        ) : first.method === "cash" && first.declared_at ? (
          <>
            أقررتَ بالتسليم <When iso={first.declared_at} today={today} /> — بانتظار تأكيد الكبتن. <b>لا يلزمك شيء</b>
          </>
        ) : first.cliq_reference_at ? (
          <>
            أدخلتَ مرجع الحوالة <When iso={first.cliq_reference_at} today={today} /> — بانتظار تأكيد الكبتن.{" "}
            <b>لا يلزمك شيء</b>
          </>
        ) : (
          <>
            بانتظار تأكيد الكبتن. <b>لا يلزمك شيء</b>
          </>
        )}
      </span>
    </div>
  );
}
