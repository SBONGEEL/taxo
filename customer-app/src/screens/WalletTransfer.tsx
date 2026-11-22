/** تحويل P2P بين محافظ الركاب (SPEC القسم 7) — خلف `wallet_transfer_enabled`.
 *
 * الترتيب الذي يصفه SPEC حرفياً: **رقم المستلم ← عرض الاسم للتأكيد ← تنفيذ**.
 * خطوة الاسم ليست زينة: تحويلٌ إلى رقمٍ أخطأ فيه صاحبُه لا يُسترد — الدفتر لا
 * يُعدَّل، وردُّه يحتاج موافقة من وصله.
 *
 * والحدود اليومية والشهرية تحكمها الخلفية (`wallet_settings`)، وصفرٌ فيها
 * يعني «لم يُضبط بعد» فترتدّ العملية برسالةٍ تقول ذلك — لا تخترع الواجهة حداً.
 *
 * **بلغة TAXO 2.0** (لوحاتُ `design/t2-new/rider/R17` · `R17b` · `R17c`): حقلُ الهاتف في R03، والمستلمُ بطاقةُ الكبتن في R08،
 * والمبلغُ بطاقةُ R10، **وورقةُ التأكيد باقيةٌ كما هي** — الاسمُ والمبلغُ و«رصيدك بعده» في قدمٍ لا تُمرَّر. **والنداءاتُ والقواعدُ
 * وشروطُ التعطيل حرفاً.**
 *
 * **وحقلُ الهاتف بعلم الدولة ومُختارها، والتحويلُ إلى دولةٍ أخرى** (أمرُ المالك ٢٠٢٦-١١-٢٢): العلمُ والمفتاحُ في أوّل الحقل (`TransferPhoneT2`)،
 * **ومستلمٌ في دولةٍ أخرى** تُفتح له ورقةٌ تقول ما يُخصم بعملتك والرسمَ والسعرَ وما يصل بعملته — **كلُّها من الخلفية** (`quoteTransfer`)،
 * والاسمُ مخفيٌّ جزئيّاً منها. **والتحويلُ داخل الدولة كما كان حرفاً**.
 */

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getWallet, lookupRecipient, quoteTransfer, transfer } from "@/api/endpoints";
import type { CrossQuote, TransferRecipient } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { useCountryConfig } from "@/lib/config";
import { notMultipleMessage, roundingUnit, unitHint } from "@/lib/rounding";
import { useSession } from "@/lib/session";
import {
  currencyLabel,
  formatAmount,
  formatMoney,
  newIdempotencyKey,
  subtractMoney,
} from "@/lib/utils";
import { Icon } from "@/taxo2";
import { COUNTRY_LABEL } from "@/lib/phone";
import { TransferPhoneT2, useTransferPhone } from "@/screens/t2/TransferPhoneT2";
import { AmountCardT2, BannerT2, BusyLabel, HeadT2, SheetModalT2, UnitNoteT2 } from "@/screens/t2/MoneyT2"; import { tr } from "@/lib/i18n";

export function WalletTransferScreen() {
  const navigate = useNavigate();
  const goBack = useGoBack("/wallet");
  const { user } = useSession();
  const country = useCountryConfig(user?.country_code);

  // **علمُ الدولة ومُختارُها في أوّل الحقل** (أمرُ المالك ٢٠٢٦-١١-٢٢) — دولةُ حسابك افتراضاً، والأخرى حين يُتاح التحويلُ إليها
  const phoneDraft = useTransferPhone();
  const { full, complete } = phoneDraft;
  /** **عرضُ التحويل إلى دولةٍ أخرى** — يُطلب حين يُضغط «تأكيد التحويل»، ويُعرض في الورقة كما جاء */
  const [quote, setQuote] = useState<CrossQuote | null>(null);
  const [amount, setAmount] = useState("");
  const [recipient, setRecipient] = useState<TransferRecipient | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // **ورقةُ تأكيدٍ قبل تحويلٍ لا رجعةَ فيه** (قرارُ المالك 2026-08-19): المالُ
  // يذهب إلى **شخصٍ آخر** ويُختار **برقمٍ يُكتب باليد** — ورقمٌ واحدٌ خاطئ
  // يرسل المال إلى غريبٍ بلا استرداد. فالورقةُ تقول ثلاثة: **اسمَ** المستقبِل
  // لا رقمَه وحدَه، والمبلغ، والرصيدَ بعده.
  const [confirming, setConfirming] = useState(false);
  const [balance, setBalance] = useState<string | null>(null);
  /** **أقصرُ من المبلغ؟** — يُحسب مرةً ويُقرأ في موضعين: الرقمِ والزرّ. وهو
   *  **عرضٌ لا قرار**: الخلفيةُ تبقى هي التي ترفض (§14)، وهذا يمنع الوصولَ
   *  إلى الرفض لا يستبدله. */
  const short =
    balance !== null && Number(amount) > 0 && Number(amount) > Number(balance);
  /** **ومع الرسم**: «لا يكفي» من الخلفية (`send.balance_after` فارغٌ) — يُقرأ منه لا يُحسب هنا */
  const shortCross = quote !== null && quote.send.balance_after === null;

  // الرصيدُ يُقرأ ليُعرض «رصيدك بعده» — ولا يُحسب في المتصفح إلا للعرض:
  // الخلفيةُ ترفض ما يتجاوز الرصيد على أي حال (§14)
  useEffect(() => {
    getWallet()
      .then((wallet) => setBalance(wallet.balance))
      .catch(() => setBalance(null));
  }, [done]);
  // مفتاحٌ واحد لهذه العملية: إعادة المحاولة بعد انقطاعٍ لا تحوّل مرتين
  const key = useRef<string | null>(null);

  async function findRecipient() {
    setBusy(true);
    setError(null);
    try {
      if (full) setRecipient(await lookupRecipient(full));
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : tr("تعذّر العثور على الحساب"),
      );
    } finally {
      setBusy(false);
    }
  }

  /** **«تأكيد التحويل»** — داخل الدولة تُفتح الورقةُ كما كانت؛ وإلى دولةٍ أخرى يُطلب العرضُ أوّلاً فتقول الورقةُ ما يصل بعملته */
  async function openConfirm() {
    if (!recipient?.cross) {
      setConfirming(true);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setQuote(await quoteTransfer(recipient.phone, amount));
      setConfirming(true);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : tr("تعذّر حساب التحويل"));
    } finally {
      setBusy(false);
    }
  }

  async function send() {
    if (!recipient) return;
    setBusy(true);
    setError(null);
    try {
      key.current ??= newIdempotencyKey("transfer");
      // **ما عرضته الورقةُ يُعاد كما جاء** — لتردّ الخلفيةُ إن تغيّر السعر، لا ليُحسب هنا
      const expectedReceived = quote?.receive.amount;
      const entry = await transfer(recipient.phone, amount, key.current, expectedReceived);
      setDone(
        quote
          ? tr("أُرسل {0} — يصل {1} إلى {2}", {
              0: formatMoney(quote.send.total, quote.send.currency),
              1: formatMoney(quote.receive.amount, quote.receive.currency),
              2: recipient.name,
            })
          : tr("تم تحويل {0} إلى {1}", { 0: formatMoney(entry.amount.replace("-", ""), entry.currency), 1: recipient.name }),
      );
      key.current = null;
      setRecipient(null);
      setQuote(null);
      phoneDraft.reset();
      setAmount("");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : tr("تعذّر تنفيذ التحويل"),
      );
      // **سعرٌ تغيّر بين العرض والضغط** — العرضُ القديمُ لا يبقى على الشاشة ليُضغط ثانيةً
      setQuote(null);
    } finally {
      setBusy(false);
    }
  }

  // **سببُ الخطأ تحت حقله** (§٦٢/٢٠): ما يردّه البحثُ عن المستلم يخصّ الرقم — فتحته؛ وما يردّه التحويلُ سطرٌ فوق الزرّ
  const phoneError = phoneDraft.problem ?? (recipient ? null : error);
  const currency = country?.currency;
  // **المبلغُ مضاعفٌ لوحدة التقريب حين تكون مشتعلة** (SPEC §٧٠-ج/٦) — والخلفيةُ تردّ غيرَه؛ هذا يقول الخطواتِ قبل الردّ
  const unit = roundingUnit(country);
  const unitError = notMultipleMessage(amount, unit, currency);

  return (
    <div className="t2 t2-m-page">
      <HeadT2 title={tr("تحويل رصيد")} onBack={goBack} />

      {recipient ? (
        // **المستلمُ وُجد** — الاسمُ قبل الرقم، والدائرةُ بعلامة «وُجد الحساب» (R08)
        <div className="t2-m-person">
          <span className="t2-m-person-badge" aria-hidden="true">
            <Icon name="how_to_reg" />
          </span>
          <div className="t2-m-person-main">
            <div className="t2-m-person-name">{recipient.name}</div>
            <div dir="ltr" className="t2-m-person-sub">
              {recipient.phone}
            </div>
            {recipient.cross && recipient.country_code ? (
              <div className="t2-m-person-sub">{tr("في {0}", { 0: COUNTRY_LABEL[recipient.country_code] })}</div>
            ) : null}
          </div>
          <button
            type="button"
            className="t2-m-change"
            onClick={() => {
              setRecipient(null);
              setQuote(null);
            }}
          >
            {tr("تغيير")}
          </button>
        </div>
      ) : (
        <>
          <TransferPhoneT2 draft={phoneDraft} id="transfer-phone" error={phoneError} disabled={busy} />
        </>
      )}

      {recipient ? (
        <>
          <div className="t2-m-gap">
            {/* **الرمزُ لا الكود**: كلُّ سطحٍ ماليٍّ آخر يقول «د.أ» */}
            <AmountCardT2
              id="transfer-amount"
              label={recipient.cross ? tr("المبلغ بعملتك") : tr("المبلغ")}
              value={amount}
              onChange={(next) => {
                setAmount(next);
                setQuote(null);
              }}
              currency={currency}
            />
          </div>
          <UnitNoteT2 hint={unitHint(unit, currency)} error={unitError} />
          <p className="t2-m-hint">{tr("الحدّان اليومي والشهري يضبطهما فريق TAXO")}</p>
        </>
      ) : null}

      {/* **والعلّةُ مع الزرِّ لا داخلَ ورقةٍ لا تُفتح** (قرارُ المالك
          2026-08-23): إطفاءُ الزرِّ وحدَه يترك صاحبَه أمام زرٍّ ميّتٍ بلا
          سبب — **وهو أسوأُ من زرٍّ يعمل ثم يرتدّ**، لأن الثاني يقول شيئاً.
          وتقول الرقمَ الذي يملكه كي لا يخمّن. */}
      {short ? (
        <div className="t2-callout warn t2-m-callout">
          <Icon name="error" />
          <div className="t2-callout-main">
            <p className="t2-callout-body t2-m-callout-text">
              {tr("رصيدك لا يكفي — المتاح")}{" "}<b>{formatMoney(balance ?? "0", currency)}</b>{tr(". اشحن محفظتك أو أنقص المبلغ.")}
            </p>
          </div>
        </div>
      ) : null}

      {recipient ? <BannerT2 tone="danger" message={error} /> : null}
      <BannerT2 tone="ok" message={done} />

      <div className="t2-m-actions">
        {recipient ? (
          <button
            type="button"
            className="t2-button primary t2-m-cta"
            // **ولا زرَّ حيٌّ على عمليةٍ سترتدّ** — الخلفيةُ ترفض ما يتجاوز
            // الرصيد، **وزرٌّ يعمل ثم يردّ ٤٠٩ يعلّم صاحبَه أن يعيد الضغط**.
            disabled={busy || Number(amount) <= 0 || short || unitError !== null}
            aria-busy={busy}
            onClick={() => void openConfirm()}
          >
            <BusyLabel busy={busy}>
              <Icon name="sync_alt" />
              {tr("تأكيد التحويل")}
            </BusyLabel>
          </button>
        ) : (
          <button
            type="button"
            className="t2-button primary t2-m-cta"
            disabled={busy || !complete}
            aria-busy={busy}
            onClick={findRecipient}
          >
            <BusyLabel busy={busy}>{tr("متابعة")}</BusyLabel>
          </button>
        )}

        {done ? (
          <button type="button" className="t2-button secondary t2-m-wide" onClick={() => navigate("/wallet")}>
            {tr("العودة للمحفظة")}
          </button>
        ) : null}
      </div>

      {confirming ? (
        // **سقفٌ وتمريرٌ وقدمٌ ثابتة** (عطبٌ مقيسٌ 2026-08-23): لوحةُ المفاتيح مفتوحةٌ بالضرورة — المستخدمُ لتوّه كتب المبلغ —
        // والإطارُ يتقلّص معها (قِيس ٨٢٠ ⇐ ٤٦٢). فالمبلغُ و«رصيدك بعده» في **قدمٍ لا تُمرَّر**، والعنوانُ وحدَه يُمرَّر (`SheetT2`)
        <SheetModalT2
          onClose={() => setConfirming(false)}
          footer={
            <div className="t2-m-foot">
              {quote ? (
                // **التحويلُ إلى دولةٍ أخرى** (أمرُ المالك ٢٠٢٦-١١-٢٢): «ترسل … ← يصل …» أوّلاً وأكبر، ثمّ السعرُ والرسمُ وما يُخصم
                <div className="t2-m-sum">
                  <div className="t2-m-fx">
                    <span dir="ltr" className="t2-m-num sm">{formatMoney(quote.send.amount, quote.send.currency)}</span>
                    <span className="t2-m-fx-arrow" aria-hidden="true">←</span>
                    <span dir="ltr" className="t2-m-num sm t2-m-strong">{formatMoney(quote.receive.amount, quote.receive.currency)}</span>
                  </div>
                  <div className="t2-m-sum-row">
                    <span className="t2-m-sum-label">{tr("إلى")}</span>
                    <span className="t2-m-sum-name">
                      {quote.recipient_name} · {COUNTRY_LABEL[quote.recipient_country]}
                    </span>
                  </div>
                  <div className="t2-m-sum-row">
                    <span className="t2-m-sum-label">{tr("رقمه")}</span>
                    <span dir="ltr" className="t2-m-sum-sub">{recipient?.phone}</span>
                  </div>
                  <div className="t2-m-dash" aria-hidden="true" />
                  <div className="t2-m-sum-row">
                    <span className="t2-m-sum-label">{tr("سعر الصرف")}</span>
                    {/* **كلُّ طرفٍ معزولٌ باتّجاهه** — `dir="ltr"` على السطر كلِّه قلبه: علامةُ العملة العربيّة تجرّ الرقمَ بعدها
                        فيُقرأ «1 د.ج 190.25 = د.أ» (قِيس في لقطة ٢٢/١١) */}
                    <span className="t2-m-sum-sub">
                      <bdi dir="ltr">1 {currencyLabel(quote.send.currency)}</bdi> = <bdi dir="ltr">{quote.rate} {currencyLabel(quote.receive.currency)}</bdi>
                    </span>
                  </div>
                  <div className="t2-m-sum-row">
                    <span className="t2-m-sum-label">{tr("ضُبط في")}</span>
                    <span dir="ltr" className="t2-m-sum-sub">{new Date(quote.rate_set_at).toLocaleDateString("en-GB")}</span>
                  </div>
                  <div className="t2-m-sum-row">
                    <span className="t2-m-sum-label">{tr("رسم التحويل")}</span>
                    <span className="t2-m-sum-sub">
                      <bdi dir="ltr">{formatMoney(quote.send.fee, quote.send.currency)}</bdi>
                      {Number(quote.fee_percent) > 0 ? <> <bdi dir="ltr">({quote.fee_percent}%)</bdi></> : null}
                    </span>
                  </div>
                  <div className="t2-m-sum-row">
                    <span className="t2-m-sum-label">{tr("يُخصم من محفظتك")}</span>
                    <span dir="ltr" className="t2-m-num sm t2-m-strong">{formatMoney(quote.send.total, quote.send.currency)}</span>
                  </div>
                  <div className="t2-m-sum-row">
                    <span className="t2-m-sum-label">{tr("رصيدك بعده")}</span>
                    <span className={shortCross ? "t2-m-sum-after short" : "t2-m-sum-after"}>
                      {quote.send.balance_after === null
                        ? tr("لا يكفي رصيدك")
                        : formatMoney(quote.send.balance_after, quote.send.currency)}
                    </span>
                  </div>
                </div>
              ) : (
              <div className="t2-m-sum">
                {/* **الاسمُ أولاً وأكبر**: الرقمُ ما كُتب، والاسمُ ما يُتحقَّق به */}
                <div className="t2-m-sum-row">
                  <span className="t2-m-sum-label">{tr("إلى")}</span>
                  <span className="t2-m-sum-name">{recipient?.name}</span>
                </div>
                <div className="t2-m-sum-row">
                  <span className="t2-m-sum-label">{tr("رقمه")}</span>
                  <span dir="ltr" className="t2-m-sum-sub">
                    {recipient?.phone}
                  </span>
                </div>
                <div className="t2-m-dash" aria-hidden="true" />
                <div className="t2-m-sum-row">
                  <span className="t2-m-sum-label">{tr("المبلغ")}</span>
                  <span>
                    <span dir="ltr" className="t2-m-num sm">
                      {formatAmount(amount, currency)}
                    </span>{" "}
                    <span className="t2-m-sum-sub t2-m-strong">{currencyLabel(country?.currency)}</span>
                  </span>
                </div>
                {balance ? (
                  <div className="t2-m-sum-row">
                    <span className="t2-m-sum-label">{tr("رصيدك بعده")}</span>
                    {/* **ولا يُعرض سالباً** (عطبٌ مقيسٌ على الجهاز 2026-08-23: رصيدٌ صفرٌ ومبلغُ 12.500 أعطى
                        «رصيدك بعده −12.500 د.أ»). **و«رصيدك بعده» لا يكون سالباً بالتعريف**: التحويلُ لا يقع أصلاً،
                        فالرقمُ يصف حالاً لن تكون. والسالبُ يُقرأ **ديناً**، ولا دَينَ هنا.
                        **وهو الشكلُ الذي أُصلح مرةً في `withdrawals.available_balance`** — ولم يمسكه ذاك الحدُّ لأنه
                        **موضعٌ آخر تماماً**: ذاك خلفيٌّ في مسار سحب الكبتن، وهذا **طرحٌ في المتصفّح** على شاشة تحويل
                        الراكب. **حدٌّ في موضعٍ لا يحرس موضعاً ثانياً يحسب الشيءَ نفسَه.** */}
                    <span className={short ? "t2-m-sum-after short" : "t2-m-sum-after"}>
                      {short
                        ? tr("لا يكفي رصيدك")
                        : formatMoney(subtractMoney(balance, amount), country?.currency)}
                    </span>
                  </div>
                ) : null}
              </div>
              )}
              <button
                type="button"
                className="t2-button primary t2-m-cta"
                disabled={busy || shortCross}
                aria-busy={busy}
                onClick={() => {
                  setConfirming(false);
                  void send();
                }}
              >
                <BusyLabel busy={busy}>{tr("أرسل الآن")}</BusyLabel>
              </button>
              <button
                type="button"
                className="t2-button secondary t2-m-wide"
                disabled={busy}
                onClick={() => setConfirming(false)}
              >
                {tr("رجوع")}
              </button>
            </div>
          }
        >
          <div className="t2-m-sheet-title">{tr("تأكيد التحويل")}</div>
          <p className="t2-m-sheet-sub last">{tr("لا يمكن التراجع بعد الإرسال — راجعِ الاسمَ لا الرقم وحدَه.")}</p>
        </SheetModalT2>
      ) : null}
    </div>
  );
}
