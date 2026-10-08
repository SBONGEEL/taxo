/** **«ركّابٌ ينتظرون تأكيدك»** — C33 (`design/PAYMENTS-UNCONFIRMED.md` §٦، SPEC §٦٤-ز) — **بلا لوحة**: تُركَّب من عُدّة الكبتن
 * القائمة — بطاقةُ حوالة كليك («وصلتني» بالجمر و«لم تصلني» بحافّة الخطر، `money.css`)، وأسبابُ النزاع (`Dispute.tsx`)، وحقلُ الهوية —
 * **في المظهرين** كأخواتها (§٦٢/٣)، بالرموز وحدَها.
 *
 * **موضعُها بعد الترحيب وقبل الرئيسية** (`App.tsx::CaptainUnconfirmedOpening`)، **مرّةً للفتحة**، والأقدمُ أوّلاً كما ترسلها الخلفية.
 * **و«لاحقاً» يُخفيها لهذه الفتحة**، وتعود في التالية حتى تُحسم، وفي الرئيسية سطرُها (`UnconfirmedHomeNoteT2`). **وعند الحجب**
 * (`blocked` — شرطُ التوزيع نفسُه) يصير «لاحقاً» «ابقَ في الرئيسية»، والرئيسيةُ تقول: «لا تصلك طلباتٌ جديدةٌ حتى تؤكّد ما سبق».
 *
 * **كلُّ طرفٍ يؤكّد ما في يده** (§١/١): الكبتنُ يؤكّد **الاستلام** — «استلمت المبلغ» للكاش و«وصلتني» لكليك، **وهما البابُ القائم
 * نفسُه** (`POST /payments/{id}/confirm`)؛ و«لم يدفع» / «لم تصلني» بابُ النزاع القائم بسببٍ مكتوب. **وما أُتمّ آلياً** (§٢-٥) يُقال
 * بسببه ومهلةِ اعتراضه (`POST /payments/{id}/object`).
 *
 * **ولا يُحسب هنا مالٌ ولا حال** (§14): المبلغُ والحالُ والمهلةُ من الخلفية، **وبعد كلِّ فعلٍ يُسأل البابُ ثانيةً** (`lib/attention.ts`).
 *
 * **وما لم يُبنَ — بعلّته** (§٦٤-ز): «رحلةٌ لم تُنهِها» (الإنهاءُ الآليُّ لم يُبنَ فلا تقع) · «وصلتني بلا مرجع» (كليك بلا مرجعٍ لا
 * يصل هذه القائمةَ أصلاً). **وجملةُ الإتمام الآليّ بلا جنس**: القائمةُ تحمل الاسمَ الأوّلَ للراكب وحدَه — فلا «أقرّت» ولا «أقرّ».
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import type { CaptainUnconfirmed, CaptainUnconfirmedItem } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { useConfig, useFeature } from "@/lib/config";
import {
  UNCONFIRMED_FLAG,
  confirmUnconfirmed,
  disputeUnconfirmed,
  objectUnconfirmed,
  useCaptainUnconfirmed,
} from "@/lib/attention";
import { CURRENCY_LABEL, METHOD_LABEL } from "@/lib/rideFormat";
import { useSession } from "@/lib/session";
import { digits } from "@/lib/utils";
import { CLIQ_DISPUTE_REASONS } from "@/screens/Dispute";
import { Icon } from "@/taxo2";

import { aheadParts, startOfToday, whenParts } from "./when";

import "./t2.css";
import "./fields.css";
import "./money.css";
import "./unconfirmed.css";

/** **نصُّ الحدّ كما كتبه التصميم** (§٦ «الحدّ») — في الرئيسية وفي رأس الصفحة. */
const LIMIT_TEXT = "لا تصلك طلباتٌ جديدةٌ حتى تؤكّد ما سبق — أكّد أو اعترض، وتعود الطلباتُ فوراً";

/** **«لم يدفع» على الكاش** (§٢-٣) — أسبابُ التصميم القديم لرحلة الكاش (`Dispute.tsx` يذكرها انحرافاً حين لم يكن للكاش نزاع)، **صار
 *  لها موضعٌ الآن**. والنصُّ يصل الإدارةَ كما هو، ومعه ملاحظةُ الكبتن إن كتبها. */
const CASH_DISPUTE_REASONS = ["لم يدفع إطلاقاً", "دفع أقلَّ من الأجرة", "نزل وغادر دون أن يدفع"];

/** هل الطريقةُ كاش؟ — **ومنها كلُّ نصٍّ في البطاقة**: «استلمت المبلغ / لم يدفع» أو «وصلتني / لم تصلني». */
const isCash = (item: CaptainUnconfirmedItem) => item.method === "cash";

/** «أمس 22:04» — يومٌ وساعةٌ بخاناتٍ لاتينية؛ والساعةُ في `ltr`. */
function When({ iso, today }: { iso: string; today: number }) {
  const at = whenParts(iso, today);
  return (
    <>
      {digits(at.day)} <span dir="ltr">{digits(at.time)}</span>
    </>
  );
}

/** **موعدٌ قادم** — «09:15 م غداً» (`aheadParts`): «فاعترض قبل…» يقع في الأيام الثلاثة القادمة لا في الماضي. */
function Ahead({ iso, today }: { iso: string; today: number }) {
  const at = aheadParts(iso, today);
  return (
    <>
      <span dir="ltr">{digits(at.time)}</span> {at.half} {digits(at.day)}
    </>
  );
}

/** «3 معلَّقات» · «24 ساعة» — **تمييزُ العدد بالعربية**، والرقمُ من إعداد السوق كما أرسلته الخلفية. */
function countOf(n: number, one: string, two: string, few: string, many: string): string {
  if (n === 1) return one;
  if (n === 2) return two;
  return n <= 10 ? `${digits(String(n))} ${few}` : `${digits(String(n))} ${many}`;
}

export function UnconfirmedT2Screen() {
  const navigate = useNavigate();
  const { user } = useSession();
  const owner = user?.id ?? "";
  const { config } = useConfig();
  // **مفتاحُ السوق من `/config`** كجيرانه — والدولةُ من الحساب
  const enabled = useFeature(user?.country_code, UNCONFIRMED_FLAG);
  const data = useCaptainUnconfirmed(enabled);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [disputing, setDisputing] = useState<CaptainUnconfirmedItem | null>(null);
  const [objecting, setObjecting] = useState<CaptainUnconfirmedItem | null>(null);
  const today = startOfToday();

  // **مطفأً لا صفحة** — ورابطٌ قديمٌ إليها يعود إلى الرئيسية
  useEffect(() => {
    if (config && !enabled) navigate("/", { replace: true });
  }, [config, enabled, navigate]);

  // **حُسم كلُّ شيءٍ ⇒ الرئيسية** — ولا صفحةَ بلا شيءٍ ينتظر
  useEffect(() => {
    if (data !== null && data.items.length === 0) navigate("/", { replace: true });
  }, [data, navigate]);

  const leave = () => navigate("/", { replace: true });

  async function act(item: CaptainUnconfirmedItem, run: () => Promise<void>, message: string) {
    setBusy(item.payment_id);
    setError(null);
    setDone(null);
    try {
      await run();
      setDone(message);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر تنفيذ الطلب");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="t2 t2-ucd">
      <div className="t2-ucd-scroll scr">
        {/* **عنوانٌ واحدٌ بلا سهم** (§٦) — مخرجُها «لاحقاً» في القاع */}
        <div className="t2-head">
          <h1 className="t2-title">ركّابٌ ينتظرون تأكيدك</h1>
        </div>

        {data === null ? (
          <div className="t2-ucd-wait" aria-busy="true">
            <Spinner />
          </div>
        ) : (
          <>
            {/* **الحدُّ وحدَه بالأحمر** (§٦: «بلا أحمرَ إلا للحدّ») — وإلا فسطرُ العتبتين بخافتٍ يقول متى يقع */}
            {data.blocked ? (
              <div className="t2-callout danger t2-ucd-limit" role="alert">
                <Icon name="error" fill />
                <div className="t2-callout-main">
                  <p className="t2-callout-title">{LIMIT_TEXT}</p>
                </div>
              </div>
            ) : (
              <p className="t2-ucd-lede">{limitLine(data)}</p>
            )}
            {error ? (
              <p className="t2-note danger" role="alert">
                <Icon name="error" fill />
                {error}
              </p>
            ) : null}
            {done ? (
              <p className="t2-note t2-ucd-done" role="status">
                <Icon name="check_circle" fill />
                {done}
              </p>
            ) : null}

            {data.items.map((item) => (
              <ItemCard
                key={item.payment_id}
                item={item}
                today={today}
                busy={busy === item.payment_id}
                locked={busy !== null}
                onConfirm={() =>
                  void act(
                    item,
                    () => confirmUnconfirmed(owner, item.payment_id),
                    isCash(item) ? "أكّدتَ استلام المبلغ — اكتمل دفعُ الرحلة." : "أكّدتَ وصول الحوالة — اكتمل دفعُ الرحلة.",
                  )
                }
                onDispute={() => {
                  setError(null);
                  setDisputing(item);
                }}
                onObject={() => {
                  setError(null);
                  setObjecting(item);
                }}
              />
            ))}
          </>
        )}

        <div className="t2-ucd-push" />
        {/* **«لاحقاً» لهذه الفتحة وحدَها** — وعند الحجب «ابقَ في الرئيسية»: لا «لاحقاً» لما يوقف الطلباتِ الآن */}
        <button type="button" className="t2-button secondary t2-ucd-later" onClick={leave}>
          {data?.blocked ? "ابقَ في الرئيسية" : "لاحقاً"}
        </button>
      </div>

      {disputing ? (
        <ReasonSheet
          title={isCash(disputing) ? "لم يدفع — ما الذي وقع؟" : "لم تصلني — ما الذي وقع؟"}
          note={
            isCash(disputing)
              ? "يُسأل الراكبُ فوراً: «هل سلّمتَ المبلغ؟»، ويفصل فريقُ TAXO إن اختلفتما — ولا يُحسب عليك شيءٌ حتى الحكم."
              : "تفصل فيه الإدارة: مدفوعة أو غير مدفوعة."
          }
          reasons={isCash(disputing) ? CASH_DISPUTE_REASONS : CLIQ_DISPUTE_REASONS}
          submitLabel="إرسال النزاع"
          onClose={() => setDisputing(null)}
          onSubmit={async (text) => {
            const item = disputing;
            await disputeUnconfirmed(owner, item.payment_id, text);
            setDisputing(null);
            setDone("أُرسل النزاع — يفصل فيه فريقُ TAXO.");
          }}
        />
      ) : null}

      {objecting ? (
        <ReasonSheet
          title="لم أستلم هذا المبلغ"
          note="لا يُعكس شيءٌ الآن — يصل اعتراضُك فريقَ TAXO ويفصل فيه، والمبلغُ كما هو حتى الحكم."
          reasons={null}
          submitLabel="أرسل الاعتراض"
          onClose={() => setObjecting(null)}
          onSubmit={async (text) => {
            const item = objecting;
            await objectUnconfirmed(owner, item.payment_id, text);
            setObjecting(null);
            setDone("أُرسل اعتراضُك — يفصل فيه فريقُ TAXO.");
          }}
        />
      ) : null}
    </div>
  );
}

/** **متى يقع الحجب** — من عتبتي السوق كما أرسلتهما الخلفية (`block_count` · `block_hours`)، **لا رقمَ مكتوبٌ هنا**. */
function limitLine(data: CaptainUnconfirmed): string {
  const count = countOf(data.block_count, "معلَّقةٍ واحدة", "معلَّقتين", "معلَّقات", "معلَّقةً");
  const hours = countOf(data.block_hours, "ساعة", "ساعتين", "ساعات", "ساعة");
  return `تتوقّف الطلباتُ الجديدةُ عند ${count}، أو حين يمضي على أقدمها ${hours} — وتعود فورَ أن تؤكّد أو تعترض.`;
}

/** **بطاقةُ راكبٍ واحد** — «ليلى · أمس 21:58» ثمّ «3.364 د.أ كاش» ثمّ الفعلان (§٦). */
function ItemCard({
  item,
  today,
  busy,
  locked,
  onConfirm,
  onDispute,
  onObject,
}: {
  item: CaptainUnconfirmedItem;
  today: number;
  busy: boolean;
  locked: boolean;
  onConfirm: () => void;
  onDispute: () => void;
  onObject: () => void;
}) {
  const name = item.rider_first_name ?? "الراكب";
  const route =
    item.pickup_address && item.dropoff_address ? `${item.pickup_address} ← ${item.dropoff_address}` : null;

  return (
    <section className={item.state === "auto_confirmed" ? "t2-ucd-card auto" : "t2-ucd-card"}>
      {/* «ليلى · أمس 21:58» (§٦) */}
      <p className="t2-ucd-who">
        <b>{name}</b> · <When iso={item.completed_at} today={today} />
      </p>
      {route ? <p className="t2-ucd-route">{route}</p> : null}
      {/* **المبلغُ كبيراً** (§٦) كبطاقة حوالة كليك — كما أرسلته الخلفية، والعملةُ من رمزها */}
      <p className="t2-cts-amount">
        <span className="t2-cts-num t2-ucd-num" dir="ltr">
          {digits(item.amount)}
        </span>
        <span className="t2-cts-cur">
          {CURRENCY_LABEL[item.currency]} {METHOD_LABEL[item.method]}
        </span>
      </p>

      {item.state === "auto_confirmed" ? (
        // **ما بعد الإتمام الآليّ** (§٦): «عُدّ مبلغُ رحلة ليلى مستلَماً … — إن لم تستلمه فاعترض قبل {الوقت}» — **بلا جنس**
        // (رأسُ الملف)، والمهلةُ مجمَّدةٌ على الصفّ (`objection_deadline`)
        <>
          <div className="t2-callout warn t2-ucd-callout">
            <Icon name="receipt_long" />
            <div className="t2-callout-main">
              <p className="t2-callout-title">عُدّ مبلغُ رحلة {name} مستلَماً بعد إقرارٍ بتسليمه بلا اعتراض</p>
              {item.objection_deadline ? (
                <p className="t2-callout-body">
                  إن لم تستلمه فاعترض قبل <Ahead iso={item.objection_deadline} today={today} />
                </p>
              ) : null}
            </div>
          </div>
          <div className="t2-cts-acts">
            <button type="button" className="t2-cts-no" disabled={locked} onClick={onObject}>
              لم أستلم هذا المبلغ
            </button>
          </div>
        </>
      ) : (
        <>
          {isCash(item) ? (
            // **أقرّ الراكبُ بالتسليم** — ومنه يعرف الكبتنُ أن الصمتَ قد يُتمّه آلياً (بلا جنسٍ كجملة الإتمام)
            item.declared_at ? (
              <p className="t2-ucd-line">
                <Icon name="check_circle" />
                أُقِرّ بالتسليم <When iso={item.declared_at} today={today} />
              </p>
            ) : null
          ) : (
            // **كليك: «حوالةٌ بمرجع FT2410… · 21:47»** (§٦) — والمهلةُ المجمَّدةُ قبل أن تصير نزاعاً
            <>
              <p className="t2-ucd-line">
                حوالةٌ بمرجع{" "}
                <b dir="ltr" className="t2-ucd-ref">
                  {item.cliq_transfer_reference ?? "—"}
                </b>
                {item.cliq_reference_at ? (
                  <>
                    {" "}
                    · <When iso={item.cliq_reference_at} today={today} />
                  </>
                ) : null}
              </p>
              {item.cliq_confirmation_expires_at ? (
                <p className="t2-ucd-line muted">
                  <Icon name="hourglass_top" />
                  تصير نزاعاً <Ahead iso={item.cliq_confirmation_expires_at} today={today} />
                </p>
              ) : null}
            </>
          )}
          <div className="t2-cts-acts">
            {/* **بحدٍّ ولونِ الخطر** كبطاقة حوالة كليك — الرفضُ فعلٌ ثقيل */}
            <button type="button" className="t2-cts-no" disabled={locked} onClick={onDispute}>
              {isCash(item) ? "لم يدفع" : "لم تصلني"}
            </button>
            <button type="button" className="t2-cts-yes" disabled={locked} aria-busy={busy} onClick={onConfirm}>
              {busy ? (
                "…"
              ) : (
                <>
                  <Icon name="check" />
                  {isCash(item) ? "استلمت المبلغ" : "وصلتني"}
                </>
              )}
            </button>
          </div>
        </>
      )}
    </section>
  );
}

/** **ورقةُ السبب** — للنزاع بأسبابه (نمطُ `Dispute.tsx`: سببٌ يُختار وملاحظةٌ تُلحق به، **ونصٌّ واحدٌ يقرؤه إنسان**)، وللاعتراض
 *  بنصٍّ حرٍّ وحدَه (`PaymentObjectionRequest.reason`: ٣–٢٥٥). **والرسالةُ من الخلفية كما وصلت** — ومنها انقضاءُ النافذة. */
function ReasonSheet({
  title,
  note,
  reasons,
  submitLabel,
  onClose,
  onSubmit,
}: {
  title: string;
  note: string;
  reasons: readonly string[] | null;
  submitLabel: string;
  onClose: () => void;
  onSubmit: (text: string) => Promise<void>;
}) {
  const [reason, setReason] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // نصٌّ واحد: السببُ المختارُ ثمّ الملاحظةُ إن كُتبت — أو النصُّ الحرُّ وحدَه للاعتراض
  const composed = reasons ? (reason ? (text.trim() ? `${reason} — ${text.trim()}` : reason) : "") : text.trim();
  const ready = reasons ? reason !== null : composed.length >= 3;

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await onSubmit(composed.slice(0, 255));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الإرسال");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="t2-ucd-shade" role="presentation" onClick={busy ? undefined : onClose}>
      <div className="t2-ucd-sheet" role="dialog" aria-label={title} onClick={(event) => event.stopPropagation()}>
        <div className="t2-ucd-grab" />
        <h2 className="t2-ucd-sheet-title">{title}</h2>
        <p className="t2-ucd-sheet-note">{note}</p>
        {reasons ? (
          <div className="t2-ucd-reasons" role="radiogroup" aria-label="السبب">
            {reasons.map((option) => (
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={reason === option}
                className={reason === option ? "t2-ucd-reason on" : "t2-ucd-reason"}
                onClick={() => setReason(option)}
              >
                <span className="t2-ucd-radio" aria-hidden="true" />
                {option}
              </button>
            ))}
          </div>
        ) : null}
        <label className="t2-fld-label t2-ucd-label" htmlFor="ucd-reason">
          {reasons ? "ملاحظة" : "ما الذي وقع؟"}
        </label>
        <input
          id="ucd-reason"
          className="t2-fld"
          placeholder={reasons ? "أضف تفصيلاً يساعد الإدارة…" : "اكتب سببَ اعتراضك…"}
          value={text}
          maxLength={200}
          onChange={(event) => setText(event.target.value)}
        />
        {error ? (
          <p className="t2-note danger" role="alert">
            <Icon name="error" fill />
            {error}
          </p>
        ) : null}
        <button type="button" className="t2-ucd-send" disabled={!ready || busy} onClick={() => void submit()}>
          {busy ? "…" : submitLabel}
        </button>
        <button type="button" className="t2-ucd-cancel" disabled={busy} onClick={onClose}>
          تراجع
        </button>
      </div>
    </div>
  );
}

/** **سطرُ الرئيسية** (§٦ · §٧) — فوق زرِّ الاستقبال حيث تُقال أسبابُ ما يقف بين الكبتن والعمل:
 *
 * - **الحجب** (`blocked`): «لا تصلك طلباتٌ جديدةٌ حتى تؤكّد ما سبق — أكّد أو اعترض، وتعود الطلباتُ فوراً» بالأحمر، وزرٌّ إلى الصفحة.
 * - **وإلا فما ينتظر**: «تأكيدٌ ينتظرك» — **بعدِّ `awaiting_you` وحدَه** — يفتح الصفحةَ التي أخفاها «لاحقاً».
 * - **وما أُتمّ آلياً وحدَه** (`auto_confirmed`): «مبلغٌ عُدّ مستلَماً — لك أن تعترض قبل …» — لا تأكيدَ يُطلب، بل نافذةُ اعتراض.
 *
 * **ولا شيءَ يُرسم بلا شيءٍ ينتظر**، أو والمفتاحُ مطفأ (`data === null`).
 */
export function UnconfirmedHomeNoteT2({
  data,
  onOpen,
}: {
  data: CaptainUnconfirmed | null;
  onOpen: () => void;
}) {
  if (!data || data.items.length === 0) return null;
  if (data.blocked) {
    return (
      <div className="t2-callout danger t2-ucd-home" role="alert">
        <Icon name="error" fill />
        <div className="t2-callout-main">
          <p className="t2-callout-title">{LIMIT_TEXT}</p>
          <button type="button" className="t2-callout-open" onClick={onOpen}>
            افتح ما ينتظر تأكيدك
          </button>
        </div>
      </div>
    );
  }
  // **«ينتظر تأكيدك» لما ينتظره حقّاً** (`awaiting_you`) — **وما أُتمّ آلياً لا ينتظر تأكيداً**: عُدّ مستلَماً، وله نافذةُ اعتراضٍ
  // وحدَها (§٢-٥). عدُّه مع المنتظِرين كان يقول «راكبٌ ينتظر تأكيدك» عن مبلغٍ لا يُطلب فيه شيء
  const waiting = data.items.filter((item) => item.state === "awaiting_you");
  const n = waiting.length;
  if (n === 0) {
    const auto = data.items.filter((item) => item.state === "auto_confirmed");
    const first = auto[0];
    if (!first) return null;
    return (
      <button type="button" className="t2-ucd-strip" onClick={onOpen}>
        <Icon name="receipt_long" />
        <span className="t2-ucd-strip-text">
          <b>
            {auto.length === 1
              ? "مبلغٌ عُدّ مستلَماً"
              : auto.length === 2
                ? "مبلغان عُدّا مستلَمَين"
                : countOf(auto.length, "", "", "مبالغ عُدّت مستلَمة", "مبلغاً عُدّت مستلَمة")}
          </b>
          <span>
            {auto.length === 1 && first.objection_deadline ? (
              <>
                لك أن تعترض قبل <Ahead iso={first.objection_deadline} today={startOfToday()} />
              </>
            ) : (
              "لك أن تعترض على كلٍّ قبل مهلته"
            )}
          </span>
        </span>
        <Icon name="chevron_left" className="t2-ucd-strip-go" />
      </button>
    );
  }
  const who =
    n === 1 ? "راكبٌ ينتظر تأكيدك" : n === 2 ? "راكبان ينتظران تأكيدك" : `${countOf(n, "", "", "ركّاب", "راكباً")} ينتظرون تأكيدك`;
  return (
    <button type="button" className="t2-ucd-strip" onClick={onOpen}>
      <Icon name="payments" />
      <span className="t2-ucd-strip-text">
        <b>تأكيدٌ ينتظرك</b>
        <span>{who}</span>
      </span>
      <Icon name="chevron_left" className="t2-ucd-strip-go" />
    </button>
  );
}
