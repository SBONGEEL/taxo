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
 */

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getWallet, lookupRecipient, transfer } from "@/api/endpoints";
import type { CountryCode, TransferRecipient } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { useConfig, useCountryConfig, usePhoneCountry } from "@/lib/config";
import { COUNTRY_LABEL, looksComplete, toNational } from "@/lib/phone";
import { useSession } from "@/lib/session";
import {
  currencyLabel,
  formatMoney,
  newIdempotencyKey,
  subtractMoney,
} from "@/lib/utils";
import { AuthBlock, AuthChoice, AuthPhone, Icon } from "@/taxo2";
import { AmountCardT2, BannerT2, BusyLabel, HeadT2, SheetModalT2 } from "@/screens/t2/MoneyT2";

export function WalletTransferScreen() {
  const navigate = useNavigate();
  const goBack = useGoBack("/wallet");
  const { user } = useSession();
  const { config } = useConfig();
  const country = useCountryConfig(user?.country_code);

  // **ولا سوقٌ مكتوبٌ هنا** (SPEC §24): القائمةُ من `/config`، فالمخفيُّ لا
  // يُعرض ولو كان لصاحب الحساب — والتحويلُ إليه بابٌ يفتحه إشعالُ المفتاح
  const countries =
    config?.countries.map((entry) => entry.country_code) ?? [];
  const [code, setCode] = useState<CountryCode>(user?.country_code ?? "JO");
  const { dialCode, nationalLength } = usePhoneCountry(code);
  const [phone, setPhone] = useState("");
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
      setRecipient(await lookupRecipient(phone));
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر العثور على الحساب",
      );
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
      const entry = await transfer(recipient.phone, amount, key.current);
      setDone(
        `تم تحويل ${formatMoney(entry.amount.replace("-", ""), entry.currency)} إلى ${recipient.name}`,
      );
      key.current = null;
      setRecipient(null);
      setPhone("");
      setAmount("");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر تنفيذ التحويل",
      );
    } finally {
      setBusy(false);
    }
  }

  // **سببُ الخطأ تحت حقله** (§٦٢/٢٠): ما يردّه البحثُ عن المستلم يخصّ الرقم — فتحته؛ وما يردّه التحويلُ سطرٌ فوق الزرّ
  const phoneError =
    dialCode === null
      ? "مفتاحُ هذه الدولة غير متاح الآن — اختر دولةً أخرى أو أعد المحاولة."
      : recipient
        ? null
        : error;
  const currency = country?.currency;

  return (
    <div className="t2 t2-m-page">
      <HeadT2 title="تحويل رصيد" onBack={goBack} />

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
          </div>
          <button type="button" className="t2-m-change" onClick={() => setRecipient(null)}>
            تغيير
          </button>
        </div>
      ) : (
        <>
          {/* **دولتان أو أكثر ⇒ تُختار الدولة** — زرّان لا قائمة، كشاشات الدخول (`AuthChoice`) */}
          {countries.length > 1 ? (
            <AuthBlock label="الدولة">
              <AuthChoice
                label="الدولة"
                value={code}
                options={countries.map((entry) => ({ value: entry, label: COUNTRY_LABEL[entry] }))}
                onChange={setCode}
              />
            </AuthBlock>
          ) : null}
          <AuthBlock label="رقم الهاتف" htmlFor="transfer-phone" error={phoneError}>
            <AuthPhone
              id="transfer-phone"
              type="tel"
              autoComplete="tel"
              dial={dialCode}
              value={phone}
              maxLength={nationalLength}
              placeholder={"7".padEnd(nationalLength, "X")}
              // **حقلٌ معطَّلٌ خيرٌ من رقمٍ بمفتاحٍ خاطئ**: بلا مفتاحٍ منشورٍ لهذه
              // الدولة لا يُبنى رقمٌ أصلاً — فالبديلُ أن يُبنى بمفتاح سوقٍ آخر
              disabled={busy || dialCode === null}
              invalid={Boolean(phoneError)}
              onChange={(event) =>
                dialCode === null ? undefined : setPhone(toNational(event.target.value, dialCode))
              }
            />
          </AuthBlock>
        </>
      )}

      {recipient ? (
        <>
          <div className="t2-m-gap">
            {/* **الرمزُ لا الكود**: كلُّ سطحٍ ماليٍّ آخر يقول «د.أ» */}
            <AmountCardT2 id="transfer-amount" label="المبلغ" value={amount} onChange={setAmount} currency={currency} />
          </div>
          <p className="t2-m-hint">الحدّان اليومي والشهري يضبطهما فريق TAXO</p>
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
              رصيدك لا يكفي — المتاح <b>{formatMoney(balance ?? "0", currency)}</b>. اشحن محفظتك أو أنقص المبلغ.
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
            disabled={busy || Number(amount) <= 0 || short}
            aria-busy={busy}
            onClick={() => setConfirming(true)}
          >
            <BusyLabel busy={busy}>
              <Icon name="sync_alt" />
              تأكيد التحويل
            </BusyLabel>
          </button>
        ) : (
          <button
            type="button"
            className="t2-button primary t2-m-cta"
            disabled={busy || !looksComplete(phone, nationalLength)}
            aria-busy={busy}
            onClick={findRecipient}
          >
            <BusyLabel busy={busy}>متابعة</BusyLabel>
          </button>
        )}

        {done ? (
          <button type="button" className="t2-button secondary t2-m-wide" onClick={() => navigate("/wallet")}>
            العودة للمحفظة
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
              <div className="t2-m-sum">
                {/* **الاسمُ أولاً وأكبر**: الرقمُ ما كُتب، والاسمُ ما يُتحقَّق به */}
                <div className="t2-m-sum-row">
                  <span className="t2-m-sum-label">إلى</span>
                  <span className="t2-m-sum-name">{recipient?.name}</span>
                </div>
                <div className="t2-m-sum-row">
                  <span className="t2-m-sum-label">رقمه</span>
                  <span dir="ltr" className="t2-m-sum-sub">
                    {recipient?.phone}
                  </span>
                </div>
                <div className="t2-m-dash" aria-hidden="true" />
                <div className="t2-m-sum-row">
                  <span className="t2-m-sum-label">المبلغ</span>
                  <span>
                    <span dir="ltr" className="t2-m-num sm">
                      {formatMoney(amount)}
                    </span>{" "}
                    <span className="t2-m-sum-sub t2-m-strong">{currencyLabel(country?.currency ?? "JOD")}</span>
                  </span>
                </div>
                {balance ? (
                  <div className="t2-m-sum-row">
                    <span className="t2-m-sum-label">رصيدك بعده</span>
                    {/* **ولا يُعرض سالباً** (عطبٌ مقيسٌ على الجهاز 2026-08-23: رصيدٌ صفرٌ ومبلغُ 12.500 أعطى
                        «رصيدك بعده −12.500 د.أ»). **و«رصيدك بعده» لا يكون سالباً بالتعريف**: التحويلُ لا يقع أصلاً،
                        فالرقمُ يصف حالاً لن تكون. والسالبُ يُقرأ **ديناً**، ولا دَينَ هنا.
                        **وهو الشكلُ الذي أُصلح مرةً في `withdrawals.available_balance`** — ولم يمسكه ذاك الحدُّ لأنه
                        **موضعٌ آخر تماماً**: ذاك خلفيٌّ في مسار سحب الكبتن، وهذا **طرحٌ في المتصفّح** على شاشة تحويل
                        الراكب. **حدٌّ في موضعٍ لا يحرس موضعاً ثانياً يحسب الشيءَ نفسَه.** */}
                    <span className={short ? "t2-m-sum-after short" : "t2-m-sum-after"}>
                      {short
                        ? "لا يكفي رصيدك"
                        : formatMoney(subtractMoney(balance, amount), country?.currency ?? "JOD")}
                    </span>
                  </div>
                ) : null}
              </div>
              <button
                type="button"
                className="t2-button primary t2-m-cta"
                disabled={busy}
                aria-busy={busy}
                onClick={() => {
                  setConfirming(false);
                  void send();
                }}
              >
                <BusyLabel busy={busy}>أرسل الآن</BusyLabel>
              </button>
              <button
                type="button"
                className="t2-button secondary t2-m-wide"
                disabled={busy}
                onClick={() => setConfirming(false)}
              >
                رجوع
              </button>
            </div>
          }
        >
          <div className="t2-m-sheet-title">تأكيد التحويل</div>
          <p className="t2-m-sheet-sub last">لا يمكن التراجع بعد الإرسال — راجعِ الاسمَ لا الرقم وحدَه.</p>
        </SheetModalT2>
      ) : null}
    </div>
  );
}
