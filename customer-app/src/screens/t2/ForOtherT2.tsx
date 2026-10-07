/** **رحلةٌ لشخصٍ آخر** (§٦٣-ج/١) — وجوهُها في تطبيق الراكب: الخيارُ في ورقة الطلب «R06»، وورقتُه، وكتلتُها في ورقة التتبّع.
 *
 * **لا لوحةَ لها في Claude Design** — فتُركَّب من عُدّة الهوية القائمة كما هي، **ولا شكلَ يُخترع**: الخيارُ بطاقةُ «المشاركة»
 * نفسُها (`t2-share`)، والورقةُ ورقةُ المال (`SheetModalT2`) بحقول التحويل نفسِها (`AuthBlock` · `AuthPhone` · `AuthChoice`)،
 * ومن يدفع بطاقتا «اختر الفئة» (`t2-cats`)، والملاحظةُ `t2-note`. **والتخطيطُ وحدَه في `for-other.css`** بالرموز.
 *
 * **والمنطقُ في بيته** (`lib/for-other.ts` · `useConfirmRide`): هذا الملفُّ يرسم ويجمع ما كتبه صاحبُه، **ولا يقرّر مالاً** —
 * الرقمُ يُطبَّع في الخلفية، وما يخالف الدافعَ ترفضه هي.
 */

import { useState } from "react";

import { ApiError } from "@/api/client";
import { createTrackLink } from "@/api/endpoints";
import type { CountryCode, CountryConfig, Ride, RideForOther, RidePayer } from "@/api/types";
import { ErrorNote } from "@/components/ui/Feedback";
import { useConfig, usePhoneCountry } from "@/lib/config";
import { PAYER_LINE, shareTrackLink, trackUrl, webOrigin } from "@/lib/for-other";
import { COUNTRY_LABEL, looksComplete, toE164, toNational } from "@/lib/phone";
import { useRide } from "@/lib/ride";
import { useSession } from "@/lib/session";
import { AuthBlock, AuthChoice, AuthInput, AuthPhone } from "@/taxo2";

import { SheetModalT2 } from "./MoneyT2";
import "./t2.css";
import "./for-other.css";

/** **الدافعُ في سطرٍ قصيرٍ على شارة الطلب** — والجملةُ الكاملةُ في ورقته وفي التتبّع (`PAYER_LINE`). */
const PAYER_SHORT: Record<RidePayer, string> = {
  requester: "تدفع أنت",
  passenger_cash: "يدفع نقداً للكبتن",
};

/** **خيارُ «لشخص آخر» في ورقة الطلب** — بطاقةُ «المشاركة» نفسُها قبل الاختيار، **وشارةُ «لـ: الاسم» بعده** بتعديلها وإزالتها.
 *
 *  **والمعطَّلُ يقول علّتَه في مكان وصفه** (قرارُ المالك 2026-08-23): زرٌّ ميّتٌ بلا سببٍ أسوأُ من زرٍّ يعمل ثمّ يرتدّ. */
export function ForOtherOptionT2({
  draft,
  blockedBy,
  onOpen,
  onClear,
}: {
  draft: RideForOther | null;
  /** علّةُ التعطيل نصّاً — `null` حين يُتاح. */
  blockedBy: string | null;
  onOpen: () => void;
  onClear: () => void;
}) {
  if (draft) {
    return (
      <div className="t2-fo-chip">
        <span className="t2-fo-chip-icon" aria-hidden="true">
          <span className="t2-icon">person</span>
        </span>
        <span className="t2-fo-chip-main">
          <span className="t2-fo-chip-title">لـ: {draft.name}</span>
          <span className="t2-fo-chip-sub">
            <span dir="ltr">{draft.phone}</span> · {PAYER_SHORT[draft.payer]}
          </span>
        </span>
        <button type="button" className="t2-fo-chip-btn" onClick={onOpen} aria-label="تعديل الراكب">
          <span className="t2-icon" aria-hidden="true">edit</span>
        </button>
        <button type="button" className="t2-fo-chip-btn" onClick={onClear} aria-label="إزالة — الرحلة لي">
          <span className="t2-icon" aria-hidden="true">close</span>
        </button>
      </div>
    );
  }
  return (
    <button type="button" className="t2-share t2-fo-open" disabled={blockedBy !== null} onClick={onOpen}>
      <span className="t2-share-main">
        <span className="t2-share-title">
          <span className="t2-icon" aria-hidden="true">person</span>
          لشخص آخر
        </span>
        <span className="t2-share-body">{blockedBy ?? "اطلبها لغيرك — يصله الكبتنُ ويتصل به باسمه ورقمه."}</span>
      </span>
      {blockedBy === null ? (
        <span className="t2-icon t2-fo-open-go" aria-hidden="true">chevron_left</span>
      ) : null}
    </button>
  );
}

/** «+962791112222» ⇐ دولتُه ورقمُه الوطنيّ بمفاتيح `/config` — **لتعديل ما كُتب** لا لتخمين دولة. */
function splitPhone(phone: string, countries: CountryConfig[]): { code: CountryCode; national: string } | null {
  const entry = countries.find((item) => phone.startsWith(`+${item.dial_code}`));
  return entry ? { code: entry.country_code, national: phone.slice(entry.dial_code.length + 1) } : null;
}

/** **ورقةُ الراكب الفعليّ** — اسمُه ورقمُه ومن يدفع، **وسطرُ الحفظ والمحو** بنصّ الوعد (ثلاثون يوماً، `PASSENGER_RETENTION_DAYS`).
 *
 *  **والرقمُ بحقل التحويل نفسِه** (`WalletTransfer`): الدولةُ زرّان حين تُنشر دولتان، والمفتاحُ أمام الرقم من `/config` —
 *  **فيُكتب رقمٌ أردنيٌّ أو ليبيٌّ** أيّاً كانت دولةُ الحساب، ويُرسل E.164. **ورقمُه هو يُقال قبل الإرسال** بنصِّ الخلفية نفسِه:
 *  الخلفيةُ هي الحارس، وهذا يمنع رحلةً ترتدّ لا يستبدل رفضَها. */
export function ForOtherSheetT2({
  initial,
  requesterPayable,
  onSave,
  onClose,
}: {
  initial: RideForOther | null;
  /** أتُتاح المحفظةُ أو البطاقةُ في هذه الدولة؟ — بغيرهما «أنا أدفع» بابٌ بلا قناة (`requesterCanPay`). */
  requesterPayable: boolean;
  onSave: (next: RideForOther) => void;
  onClose: () => void;
}) {
  const { user } = useSession();
  const { config } = useConfig();
  const listed = config?.countries ?? [];
  const countries = listed.map((entry) => entry.country_code);
  const held = initial ? splitPhone(initial.phone, listed) : null;
  const [code, setCode] = useState<CountryCode>(held?.code ?? user?.country_code ?? "JO");
  const { dialCode, nationalLength } = usePhoneCountry(code);
  const [name, setName] = useState(initial?.name ?? "");
  const [phone, setPhone] = useState(held?.national ?? "");
  const [payer, setPayer] = useState<RidePayer>(
    initial?.payer ?? (requesterPayable ? "requester" : "passenger_cash"),
  );

  const complete = dialCode !== null && looksComplete(phone, nationalLength);
  const full = complete && dialCode !== null ? toE164(phone, dialCode) : null;
  const own = full !== null && full === user?.phone;
  const phoneError =
    dialCode === null
      ? "مفتاحُ هذه الدولة غير متاح الآن — اختر دولةً أخرى أو أعد المحاولة."
      : own
        ? "هذا رقمُك — اطلب الرحلةَ لنفسك"
        : null;
  const ready = name.trim().length >= 2 && full !== null && !own && (payer !== "requester" || requesterPayable);

  const payers: Array<{ value: RidePayer; icon: string; label: string; hint: string; off: boolean }> = [
    {
      value: "requester",
      icon: "account_balance_wallet",
      label: "أنا أدفع — بالمحفظة أو البطاقة",
      hint: requesterPayable ? "من تطبيقك بعد الرحلة" : "لا محفظةَ ولا بطاقةَ مفعّلتان في بلدك",
      off: !requesterPayable,
    },
    {
      value: "passenger_cash",
      icon: "payments",
      label: "الراكب يدفع نقداً عند الوصول",
      hint: "يسلّم الأجرةَ للكبتن بيده",
      off: false,
    },
  ];

  return (
    <SheetModalT2
      onClose={onClose}
      footer={
        <button
          type="button"
          className="t2-button primary t2-fo-save"
          disabled={!ready}
          onClick={() => full !== null && onSave({ name: name.trim(), phone: full, payer })}
        >
          تأكيد
        </button>
      }
    >
      <div className="t2-picker-title">لشخص آخر</div>
      <AuthBlock label="اسم الراكب" htmlFor="for-other-name">
        <AuthInput
          id="for-other-name"
          value={name}
          maxLength={80}
          autoComplete="off"
          placeholder="الاسم كما يناديه الكبتن"
          onChange={(event) => setName(event.target.value)}
        />
      </AuthBlock>
      {/* **دولتان أو أكثر ⇒ تُختار دولةُ الرقم** — كشاشة التحويل (`AuthChoice`) */}
      {countries.length > 1 ? (
        <AuthBlock label="دولة الرقم">
          <AuthChoice
            label="دولة الرقم"
            value={code}
            options={countries.map((entry) => ({ value: entry, label: COUNTRY_LABEL[entry] }))}
            onChange={setCode}
          />
        </AuthBlock>
      ) : null}
      <AuthBlock label="رقم هاتفه" htmlFor="for-other-phone" error={phoneError}>
        <AuthPhone
          id="for-other-phone"
          type="tel"
          autoComplete="off"
          dial={dialCode}
          value={phone}
          maxLength={nationalLength}
          placeholder={"7".padEnd(nationalLength, "X")}
          valid={complete && !own}
          // **حقلٌ معطَّلٌ خيرٌ من رقمٍ بمفتاحٍ خاطئ** — قاعدةُ شاشة التحويل بعينها
          disabled={dialCode === null}
          invalid={Boolean(phoneError)}
          onChange={(event) => (dialCode === null ? undefined : setPhone(toNational(event.target.value, dialCode)))}
        />
      </AuthBlock>

      <div className="t2-pick-head">
        <span className="t2-pick-title">من يدفع؟</span>
      </div>
      <div className="t2-cats t2-fo-payers" role="radiogroup" aria-label="من يدفع">
        {payers.map((option) => {
          const on = option.value === payer;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={on}
              disabled={option.off}
              className={on ? "t2-cat on" : "t2-cat"}
              onClick={() => setPayer(option.value)}
            >
              <span className="t2-cat-icon">
                <span className="t2-icon" aria-hidden="true">{option.icon}</span>
              </span>
              <span className="t2-cat-main">
                <span className="t2-cat-name">{option.label}</span>
                <span className="t2-cat-hint">{option.hint}</span>
              </span>
            </button>
          );
        })}
      </div>

      <p className="t2-note t2-fo-keep">
        <span className="t2-icon" aria-hidden="true">lock</span>
        نحفظ اسمه ورقمه لهذه الرحلة وحدها، ونحذفهما بعد ثلاثين يوماً.
      </p>
    </SheetModalT2>
  );
}

/** **كتلةُ «لشخص آخر» في ورقة التتبّع** (R07–R09): اسمُ الراكب حين يُنشر (بعد القبول وحتى الانتهاء)، **وسطرُ الدافع**،
 *  وزرُّ «شارك رابط التتبّع».
 *
 *  **والرمزُ يُطلب عند الضغط لا قبله** — رابطٌ عامٌّ لا يُنشأ لرحلةٍ لم يطلب صاحبُها مشاركتَها؛ **ويُحفظ بعد أوّل طلب** فلا
 *  تنتظر الضغطةُ الثانيةُ شبكةً (والخلفيةُ تعيد الرمزَ نفسَه على أيِّ حال). **والنسخُ يُقال بتنبيه** — لا أثرَ له غيرُه يُرى. */
export function ForOtherTrackT2({ ride }: { ride: Ride }) {
  const { notify } = useRide();
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // **بلا عنوانِ ويبٍ لا رابط** (حزمةُ iOS — `webOrigin`)، فلا زرَّ يَعِد بما لا يُبنى
  const linkable = webOrigin() !== null;

  async function share() {
    setBusy(true);
    setError(null);
    try {
      const held = token ?? (await createTrackLink(ride.id)).token;
      setToken(held);
      const url = trackUrl(held);
      if (url === null) return;
      const outcome = await shareTrackLink(url);
      if (outcome === "copied") notify("نُسخ رابط التتبّع", "أرسله إلى الراكب ليتابع رحلته.");
      if (outcome === "failed") setError(`تعذّر نسخ الرابط — انسخه من هنا: ${url}`);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر إنشاء رابط التتبّع");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="t2-fo-ride">
      <div className="t2-fo-ride-card">
        {ride.passenger_name ? (
          <div className="t2-fo-ride-name">
            <span className="t2-icon" aria-hidden="true">person</span>
            <span>
              الراكب: <b>{ride.passenger_name}</b>
            </span>
          </div>
        ) : null}
        <div className="t2-fo-ride-payer">
          <span className="t2-icon" aria-hidden="true">
            {ride.payer === "passenger_cash" ? "payments" : "account_balance_wallet"}
          </span>
          <span>{PAYER_LINE[ride.payer]}</span>
        </div>
      </div>
      {linkable ? (
        <button
          type="button"
          className="t2-button secondary t2-fo-link"
          disabled={busy}
          aria-busy={busy}
          onClick={() => void share()}
        >
          <span className="t2-icon" aria-hidden="true">ios_share</span>
          شارك رابط التتبّع
        </button>
      ) : null}
      <ErrorNote message={error} className="t2-error" />
    </div>
  );
}
