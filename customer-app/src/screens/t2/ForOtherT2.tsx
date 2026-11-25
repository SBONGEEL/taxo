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
import type { CountryCode, Ride, RideForOther, RidePayer } from "@/api/types";
import { ErrorNote } from "@/components/ui/Feedback";
import { useConfig, useCountryConfig, usePhoneCountry } from "@/lib/config";
import { REQUESTER_METHODS, payerLine, shareTrackLink, trackUrl, webOrigin } from "@/lib/for-other";
import { methodsPhrase } from "@/lib/payment";
import { COUNTRY_LABEL, cleanSecondPhone, looksComplete } from "@/lib/phone";
import { useRide } from "@/lib/ride";
import { useSession } from "@/lib/session";
import { AuthBlock, AuthInput, AuthPhone, Icon } from "@/taxo2";

import { SheetModalT2 } from "./MoneyT2";
import "./t2.css";
import "./for-other.css"; import { tr } from "@/lib/i18n";

/** **الدافعُ في سطرٍ قصيرٍ على شارة الطلب** — والجملةُ الكاملةُ في ورقته وفي التتبّع (`PAYER_LINE`). **وشارةُ الطرد تقرؤه
 *  كذلك** (`ParcelT2`): «تدفع أنت» هي هي، و`recipient_cash` للطرد وحدَه. */
export const PAYER_SHORT: Record<RidePayer, string> = {
  requester: tr("تدفع أنت"),
  passenger_cash: tr("يدفع نقداً للكابتن"),
  recipient_cash: tr("يدفع المستلمُ نقداً"),
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
          <Icon name="person" />
        </span>
        <span className="t2-fo-chip-main">
          <span className="t2-fo-chip-title">{tr("لـ:")}{" "}{draft.name}</span>
          <span className="t2-fo-chip-sub">
            <span dir="ltr">{draft.phone}</span> · {PAYER_SHORT[draft.payer]}
          </span>
        </span>
        <button type="button" className="t2-fo-chip-btn" onClick={onOpen} aria-label={tr("تعديل الراكب")}>
          <Icon name="edit" />
        </button>
        <button type="button" className="t2-fo-chip-btn" onClick={onClear} aria-label={tr("إزالة — الرحلة لي")}>
          <Icon name="close" />
        </button>
      </div>
    );
  }
  return (
    <button type="button" className="t2-share t2-fo-open" disabled={blockedBy !== null} onClick={onOpen}>
      <span className="t2-share-main">
        <span className="t2-share-title">
          <Icon name="person" />
          {tr("لشخص آخر")}
        </span>
        <span className="t2-share-body">{blockedBy ?? tr("اطلبها لغيرك — يصله الكابتنُ ويتصل به باسمه ورقمه.")}</span>
      </span>
      {blockedBy === null ? (
        <Icon name="chevron_left" className="t2-fo-open-go" />
      ) : null}
    </button>
  );
}

/** **رقمُ شخصٍ آخر — من دولة حسابك وحدَها** (أمرُ المالك ٢٠٢٦-١١-٢١، SPEC §٦٣-ج/١): لا زرَّ دولة — **الدولةُ دولةُ الحساب ولا
 *  تُغيَّر**، وعلمُها ومفتاحُها ثابتان أمام الحقل. **يقرؤه كلُّ بابٍ يُكتب فيه رقمُ طرفٍ ثانٍ**: الراكبُ الفعليّ هنا، والمستلمُ
 *  والمُسلِّمُ (`ParcelT2`)، والمحوَّلُ إليه (`WalletTransfer`) — فلا يفترق حقلا رقمٍ في دولةٍ ولا في طولٍ ولا في نصِّ رفض.
 *  و`initial` رقمٌ كُتب قبلُ (E.164) يُنظَّف كما لو كُتب الآن. **والتسجيلُ خارجه**: يختار دولتَه كما كان. */
export function usePhoneDraft(initial: string | null) {
  const { user } = useSession();
  const { config } = useConfig();
  const code: CountryCode = user?.country_code ?? config?.default_country_code ?? "JO";
  const { dialCode, nationalLength, prefixes } = usePhoneCountry(code);
  // **كلُّ مفاتيح الدول المنشورة** — لا المفتوحةُ وحدَها: رقمٌ ليبيٌّ يُعرف ليبيّاً ولو كان سوقُه مغلقاً
  const others = (config?.countries ?? []).map((entry) => entry.dial_code).filter((dial) => dial !== dialCode);
  const [state, setState] = useState(() =>
    dialCode === null ? { national: "", foreign: false } : cleanSecondPhone(initial ?? "", dialCode, others, nationalLength),
  );
  const badStart =
    !state.foreign && state.national.length > 0 && prefixes.length > 0 && !prefixes.some((p) => state.national.startsWith(p));
  const complete = dialCode !== null && !state.foreign && !badStart && looksComplete(state.national, nationalLength);
  // **النصُّ بلفظ المالك**، والخلفيةُ ترفض بالحرف نفسِه (`ride_for_other.FOREIGN_PHONE`) — هذا يقوله قبل الإرسال لا بدلَها
  const problem =
    dialCode === null
      ? tr("مفتاحُ دولتك غير متاح الآن — أعد المحاولة بعد قليل.")
      : state.foreign
        ? tr("الرقم يجب أن يكون من نفس دولة حسابك")
        : badStart
          ? tr("رقمُ الجوّال في {0} يبدأ بـ{1}", { 0: COUNTRY_LABEL[code], 1: prefixes.join(tr(" أو ")) })
          : null;
  return {
    code,
    dialCode,
    nationalLength,
    prefixes,
    phone: state.national,
    setPhone: (input: string) => {
      if (dialCode !== null) setState(cleanSecondPhone(input, dialCode, others, nationalLength));
    },
    complete,
    problem,
    full: complete && dialCode !== null ? `+${dialCode}${state.national}` : null,
  };
}

/** **حقلُ رقمِ الطرف الثاني** — علمُ دولة الحساب ومفتاحُها ثابتان أمامه (`AuthPhone` بـ`fixed`)، **ولا زرَّ دولة**. وحقلٌ معطَّلٌ
 *  خيرٌ من رقمٍ بمفتاحٍ خاطئ — قاعدةُ شاشة التحويل بعينها. والخطأُ نصٌّ يمرّره صاحبُ الورقة (`draft.problem` أوّلاً، ثمّ ما يخصّه). */
export function PhoneFieldsT2({
  draft,
  id,
  label,
  error,
  valid,
  disabled = false,
}: {
  draft: ReturnType<typeof usePhoneDraft>;
  id: string;
  label: string;
  error: string | null;
  valid: boolean;
  disabled?: boolean;
}) {
  const { code, dialCode, nationalLength, prefixes, phone, setPhone } = draft;
  return (
    <AuthBlock label={label} htmlFor={id} error={error}>
      <AuthPhone
        id={id}
        type="tel"
        autoComplete="off"
        dial={dialCode}
        fixed={{ code, name: COUNTRY_LABEL[code] }}
        value={phone}
        placeholder={(prefixes[0] ?? "").padEnd(nationalLength, "X")}
        valid={valid}
        disabled={disabled || dialCode === null}
        invalid={Boolean(error)}
        onChange={(event) => setPhone(event.target.value)}
      />
    </AuthBlock>
  );
}

/** **ورقةُ الراكب الفعليّ** — اسمُه ورقمُه ومن يدفع، **وسطرُ الحفظ والمحو** بنصّ الوعد (ثلاثون يوماً، `PASSENGER_RETENTION_DAYS`).
 *
 *  **والرقمُ من دولة الحساب وحدَها** (أمرُ المالك ٢٠٢٦-١١-٢١ — كان يُكتب رقمٌ أردنيٌّ أو ليبيٌّ أيّاً كانت دولةُ الحساب):
 *  علمُها ومفتاحُها ثابتان أمام الحقل، ويُرسل E.164. **ورقمُه هو يُقال قبل الإرسال** بنصِّ الخلفية نفسِه:
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
  // **حالُ الرقم من بيته** (`usePhoneDraft`) — ورقةُ الطرد تقرؤه كذلك
  const phoneDraft = usePhoneDraft(initial?.phone ?? null);
  const { complete, full } = phoneDraft;
  const [name, setName] = useState(initial?.name ?? "");
  const [payer, setPayer] = useState<RidePayer>(
    initial?.payer ?? (requesterPayable ? "requester" : "passenger_cash"),
  );

  const myCountry = useCountryConfig(user?.country_code);
  const requesterPhrase = methodsPhrase(myCountry, REQUESTER_METHODS);
  const own = full !== null && full === user?.phone;
  const phoneError = phoneDraft.problem ?? (own ? tr("هذا رقمُك — اطلب الرحلةَ لنفسك") : null);
  const ready = name.trim().length >= 2 && full !== null && !own && (payer !== "requester" || requesterPayable);

  const payers: Array<{ value: RidePayer; icon: string; label: string; hint: string; off: boolean }> = [
    {
      value: "requester",
      icon: "account_balance_wallet",
      label: requesterPhrase ? tr("أنا أدفع — {0}", { 0: requesterPhrase }) : tr("أنا أدفع"),
      hint: requesterPayable ? tr("من تطبيقك بعد الرحلة") : tr("لا محفظةَ ولا بطاقةَ مفعّلتان في بلدك"),
      off: !requesterPayable,
    },
    {
      value: "passenger_cash",
      icon: "payments",
      label: tr("الراكب يدفع نقداً عند الوصول"),
      hint: tr("يسلّم الأجرةَ للكابتن بيده"),
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
          {tr("تأكيد")}
        </button>
      }
    >
      <div className="t2-picker-title">{tr("لشخص آخر")}</div>
      <AuthBlock label={tr("اسم الراكب")} htmlFor="for-other-name">
        <AuthInput
          id="for-other-name"
          value={name}
          maxLength={80}
          autoComplete="off"
          placeholder={tr("الاسم كما يناديه الكابتن")}
          onChange={(event) => setName(event.target.value)}
        />
      </AuthBlock>
      <PhoneFieldsT2
        draft={phoneDraft}
        id="for-other-phone"
        label={tr("رقم هاتفه")}
        error={phoneError}
        valid={complete && !own}
      />

      <div className="t2-pick-head">
        <span className="t2-pick-title">{tr("من يدفع؟")}</span>
      </div>
      <div className="t2-cats t2-fo-payers" role="radiogroup" aria-label={tr("من يدفع")}>
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
                <Icon name={option.icon} />
              </span>
              <span className="t2-cat-main">
                <span className="t2-cat-name">{option.label}</span>
                <span className="t2-cat-hint">{option.hint}</span>
              </span>
            </button>
          );
        })}
      </div>

      {/* **سطرُ الخصوصيّة** (أمرُ المالك ٢٠٢٦-١١-٢١) — وهو ما تفعله الخلفيةُ فعلاً (`PASSENGER_VISIBLE`) */}
      <p className="t2-note t2-fo-keep">
        <Icon name="visibility" />
        {tr("يرى الكابتنُ الرقمَ أثناء هذه الرحلة فقط، ويُخفى عنه بعد انتهائها.")}
      </p>
      <p className="t2-note t2-fo-keep">
        <Icon name="lock" />
        {tr("نحفظ اسمه ورقمه لهذه الرحلة وحدها، ونحذفهما بعد ثلاثين يوماً.")}
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
  const { user } = useSession();
  const myCountry = useCountryConfig(user?.country_code);
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
      if (outcome === "copied") notify(tr("نُسخ رابط التتبّع"), tr("أرسله إلى الراكب ليتابع رحلته."));
      if (outcome === "failed") setError(tr("تعذّر نسخ الرابط — انسخه من هنا: {0}", { 0: url }));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : tr("تعذّر إنشاء رابط التتبّع"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="t2-fo-ride">
      <div className="t2-fo-ride-card">
        {ride.passenger_name ? (
          <div className="t2-fo-ride-name">
            <Icon name="person" />
            <span>
              {tr("الراكب:")}{" "}<b>{ride.passenger_name}</b>
            </span>
          </div>
        ) : null}
        <div className="t2-fo-ride-payer">
          <Icon name={ride.payer === "passenger_cash" ? "payments" : "account_balance_wallet"} />
          <span>{payerLine(ride.payer, myCountry)}</span>
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
          <Icon name="ios_share" />
          {tr("شارك رابط التتبّع")}
        </button>
      ) : null}
      <ErrorNote message={error} className="t2-error" />
    </div>
  );
}
