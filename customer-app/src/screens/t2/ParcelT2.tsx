/** **الطرد** (§٦٣-ج/٤) — وجوهُه في تطبيق الراكب: الشارةُ في ورقة الطلب «R06»، وورقتُه (الشروطُ والمستلمُ ومن يدفع)، وكتلتُه
 * في ورقة التتبّع.
 *
 * **لا لوحةَ لها في Claude Design** — فتُركَّب من عُدّة الهوية كما هي، **ولا شكلَ يُخترع**: الشارةُ شارةُ «لشخص آخر» نفسُها
 * (`t2-fo-chip` · `t2-fo-open`)، والورقةُ ورقةُ المال (`SheetModalT2`) بحقول التحويل (`AuthBlock` · `AuthInput` · `PhoneFieldsT2`)،
 * **والشروطُ بمربّع الموافقة في التسجيل** (`t2-auth-consent`)، ومن يدفع بطاقتا «اختر الفئة»، والملاحظةُ `t2-note`. **والتخطيطُ
 * وحدَه في `parcel.css`** بالرموز.
 *
 * **و«أحضر غرضي»** (§٧٢-ج/١) — **الوجوهُ نفسُها معكوسةً** كما رُسمت في لوحتها (Claude Design «أحضر غرضي»، R2–R4): الغرضُ ومن يسلّمه
 * وعنوانُ الاستلام، **ولا اختيارَ للدافع** — صاحبُ الطلب يدفع بما يختاره في ورقة الطلب.
 *
 * **ولا قرارَ مالٍ هنا ولا نصَّ شرطٍ** (§14): الشروطُ والرسمُ من تقدير الخلفية، والرقمُ يُطبَّع هناك، وما يخالف القواعدَ
 * (بلا إقرار · فئةٌ غيرُ الاقتصادي · خدمةٌ مخفيّة) ترفضه هي.
 */

import { useState } from "react";

import type { Ride, RideParcel } from "@/api/types";
import { payerLine } from "@/lib/for-other";
import { useCountryConfig } from "@/lib/config";
import { methodsPhrase } from "@/lib/payment";
import { useSession } from "@/lib/session";
import { AuthBlock, AuthInput, Icon } from "@/taxo2";

import { PAYER_SHORT, PhoneFieldsT2, usePhoneDraft } from "./ForOtherT2";
import { SheetModalT2 } from "./MoneyT2";
import "./t2.css";
import "./for-other.css";
import "./parcel.css"; import { tr } from "@/lib/i18n";

/** **شارةُ الطرد في ورقة الطلب** — قبل كتابة المستلم زرٌّ يفتح ورقتَه (بطاقةُ «لشخص آخر» نفسُها)، **وبعده «إلى: الاسم»**
 *  برقمه ومن يدفع وزرِّ التعديل. **ولا زرَّ إزالة**: الطردُ طلبٌ بدأته البلاطة، والخروجُ منه سهمُ الرجوع فوق الخريطة. */
export function ParcelOptionT2({
  draft,
  fetch = false,
  onOpen,
}: {
  draft: RideParcel | null;
  /** **«أحضر غرضي»** (§٧٢-ج/١) — «من: الاسم · الغرض» و«تدفع أنت». */
  fetch?: boolean;
  onOpen: () => void;
}) {
  if (draft) {
    return (
      <div className="t2-fo-chip">
        <span className="t2-fo-chip-icon" aria-hidden="true">
          <Icon name={fetch ? "inventory_2" : "package_2"} />
        </span>
        <span className="t2-fo-chip-main">
          <span className="t2-fo-chip-title">
            {fetch ? tr("من: {0} · {1}", { 0: draft.recipient_name, 1: draft.item ?? "" }) : tr("إلى: {0}", { 0: draft.recipient_name })}
          </span>
          <span className="t2-fo-chip-sub">
            <span dir="ltr">{draft.recipient_phone}</span> · {fetch ? tr("تدفع أنت") : PAYER_SHORT[draft.payer]}
          </span>
        </span>
        <button
          type="button"
          className="t2-fo-chip-btn"
          onClick={onOpen}
          aria-label={fetch ? tr("تعديل بيانات الغرض") : tr("تعديل بيانات الطرد")}
        >
          <Icon name="edit" />
        </button>
      </div>
    );
  }
  return (
    <button type="button" className="t2-share t2-fo-open" onClick={onOpen}>
      <span className="t2-share-main">
        <span className="t2-share-title">
          <Icon name={fetch ? "inventory_2" : "package_2"} />
          {fetch ? tr("بيانات الغرض") : tr("بيانات الطرد")}
        </span>
        <span className="t2-share-body">
          {fetch ? tr("اقرأ الشروط، واكتب الغرضَ ومن يسلّمه للكابتن.") : tr("اقرأ الشروط، واكتب المستلمَ ومن يدفع.")}
        </span>
      </span>
      <Icon name="chevron_left" className="t2-fo-open-go" />
    </button>
  );
}

/** **ورقةُ الطرد** — الشروطُ الأربعُ بلفظ الخلفية ومربّعُ الإقرار بها، **ثمّ المستلم** (اسمُه ورقمُه وعنوانُ التسليم) **ومن يدفع**،
 *  وسطرُ الحفظ والمحو بنصّ الوعد (ثلاثون يوماً — كنسُ الراكب الفعليّ نفسُه في الخلفية).
 *
 *  **والإقرارُ لا يُعطى قبل أن تُقرأ الشروط**: المربّعُ معطَّلٌ ما دامت لم تصل، **وورقةٌ تعود للتعديل تبدأ بإقرارها كما كان** —
 *  الشروطُ هي هي ما دام الطلبُ نفسَه. **والرقمُ بحقل «لشخص آخر» نفسِه** (`PhoneFieldsT2`): دولتُه ومفتاحُه من `/config`، ويُرسل
 *  E.164 — **ورقمُه هو لا يُرفض**: من يرسل طرداً إلى نفسه في مكانٍ آخر يُرسله. */
/** **ملخّصُ الطلب قبل «تأكيد»** (أمرُ المالك ٢٠٢٦-١١-٢١): النقطتان والسعرُ التقديريُّ وطريقةُ الدفع — **كما ترسمها ورقةُ الطلب**:
 *  السعرُ هو هو المعروضُ على زرّها (من تقدير الخلفية، بتقريب الدولة)، ولا حسابَ هنا (§14). */
export type ParcelSummary = { from: string; to: string; fare: string | null; payment: string | null };

export function ParcelSheetT2({
  terms,
  failed,
  initial,
  fetch = false,
  summary = null,
  onSave,
  onClose,
}: {
  /** **الشروطُ من التقدير** (`parcel_terms`) — و`null` ما دام يُحسب أو إن تعثّر. */
  terms: string[] | null;
  /** **تعثّر التقدير** — فلا يُقال «نقرأ الشروط…» عن شيءٍ لن يصل. */
  failed: boolean;
  initial: RideParcel | null;
  /** **«أحضر غرضي»** (§٧٢-ج/١) — الغرضُ ومن يسلّمه وعنوانُ الاستلام، **ولا «من يدفع»**: صاحبُ الطلب. */
  fetch?: boolean;
  summary?: ParcelSummary | null;
  onSave: (next: RideParcel) => void;
  onClose: () => void;
}) {
  const phoneDraft = usePhoneDraft(initial?.recipient_phone ?? null);
  const { complete, full } = phoneDraft;
  const { user } = useSession();
  // **قنواتُ الدفع العاملةُ في دولة الراكب** — لا «أو البطاقة» لليبيّ (أمرُ المالك ٢٢/١١)
  const payPhrase = methodsPhrase(useCountryConfig(user?.country_code));
  const [accepted, setAccepted] = useState(initial?.accepted_terms ?? false);
  const [name, setName] = useState(initial?.recipient_name ?? "");
  const [address, setAddress] = useState(initial?.recipient_address ?? "");
  const [payer, setPayer] = useState<RideParcel["payer"]>(initial?.payer ?? "requester");
  const [item, setItem] = useState(initial?.item ?? "");

  // **الخطأُ نصُّ الحقل المشترك** — دولةٌ أخرى · بدايةٌ خاطئة · مفتاحٌ غائب (`usePhoneDraft`)
  const phoneError = phoneDraft.problem;
  // **حدودُ الخلفية نفسُها** (`ParcelIn`): اسمٌ بحرفين وعنوانٌ بثلاثة — وما بعدها ترفضه هي بنصّها.
  // **والزرُّ المعطَّلُ يقول ما ينقص** (أمرُ المالك ٢٠٢٦-١١-٢١) — بترتيب الورقة من أعلاها، فأوّلُ ناقصٍ يُرى هو أوّلُ ما يُملأ
  const missing =
    terms === null
      ? failed
        ? tr("تعذّرت قراءة الشروط — أغلق الورقة وأعد المحاولة.")
        : tr("نقرأ الشروط…")
      : !accepted
        ? tr("وافق على الشروط أولاً")
        : fetch && item.trim().length < 2
          ? tr("اكتب ما الغرض")
          : name.trim().length < 2
            ? fetch
              ? tr("اكتب اسم المُسلِّم")
              : tr("اكتب اسم المستلم")
            : full === null
              ? fetch
                ? tr("أدخل رقم المُسلِّم")
                : tr("أدخل رقم المستلم")
              : address.trim().length < 3
                ? fetch
                  ? tr("اكتب عنوان الاستلام")
                  : tr("اكتب عنوان التسليم")
                : null;
  const ready = missing === null;

  const payers: Array<{ value: RideParcel["payer"]; icon: string; label: string; hint: string }> = [
    { value: "requester", icon: "account_balance_wallet", label: tr("أنا أدفع"), hint: tr("عند الاستلام منك — بأيِّ طريقة دفع") },
    {
      value: "recipient_cash",
      icon: "payments",
      label: tr("المستلم يدفع نقداً عند التسليم"),
      hint: tr("يسلّم الأجرةَ للكابتن بيده"),
    },
  ];

  return (
    <SheetModalT2
      onClose={onClose}
      footer={
        <>
        {missing ? (
          <p className="t2-pc-missing" role="status">
            <Icon name="info" />
            {missing}
          </p>
        ) : null}
        <button
          type="button"
          className="t2-button primary t2-fo-save t2-pc-confirm"
          disabled={!ready}
          onClick={() =>
            full !== null &&
            onSave(
              fetch
                ? {
                    recipient_name: name.trim(),
                    recipient_phone: full,
                    recipient_address: address.trim(),
                    payer: "requester",
                    accepted_terms: true,
                    fetch: true,
                    item: item.trim(),
                  }
                : {
                    recipient_name: name.trim(),
                    recipient_phone: full,
                    recipient_address: address.trim(),
                    payer,
                    accepted_terms: true,
                  },
            )
          }
        >
          {tr("تأكيد")}
        </button>
        </>
      }
    >
      <div className="t2-picker-title">{fetch ? tr("أحضر غرضي") : tr("طرد")}</div>
      {fetch ? (
        <p className="t2-note t2-pf-lead">
          <Icon name="inventory_2" />
          {tr("يأخذ الكابتنُ غرضك من حيث تقول ويوصله إليك.")}
        </p>
      ) : null}

      {/* **الشروطُ أوّلاً** (§٦٣-ج/٤: «يُعرض على المرسل قبل أن يطلب») — بلفظ الخلفية، ومربّعُ الإقرار تحتها */}
      <div className="t2-auth-consent t2-pc-terms">
        <div className="t2-pc-terms-title">
          {/* **وثيقةٌ لا مطرقة** (أمرُ المالك ٢٠٢٦-١١-٢١): «gavel» بدت مطرقةً مشطوبة */}
          <Icon name="verified_user" />
          {fetch ? tr("الشروط") : tr("شروط الطرد")}
        </div>
        {terms ? (
          <ul className="t2-pc-terms-list">
            {terms.map((term) => (
              <li key={term}>{term}</li>
            ))}
          </ul>
        ) : (
          <p className="t2-pc-terms-wait">
            {failed ? tr("تعذّرت قراءة الشروط — أغلق الورقة وأعد المحاولة.") : tr("نقرأ الشروط…")}
          </p>
        )}
        <button
          type="button"
          role="checkbox"
          aria-checked={accepted}
          className="t2-auth-consent-row t2-pc-terms-accept"
          disabled={terms === null}
          onClick={() => setAccepted((value) => !value)}
        >
          <span className="t2-auth-box" aria-hidden="true">
            <Icon name="check" />
          </span>
          <span>{tr("قرأتُ الشروط وأوافق عليها")}</span>
        </button>
      </div>

      {fetch ? (
        <>
          <AuthBlock label={tr("ما الغرض؟")} htmlFor="parcel-item">
            <AuthInput
              id="parcel-item"
              value={item}
              maxLength={120}
              autoComplete="off"
              placeholder={tr("مثلاً: شاحن هاتف على طاولة المدخل")}
              onChange={(event) => setItem(event.target.value)}
            />
          </AuthBlock>
          <div className="t2-pick-head">
            <span className="t2-pick-title">{tr("من يسلّمه للكابتن؟")}</span>
          </div>
        </>
      ) : null}
      <AuthBlock label={fetch ? tr("الاسم") : tr("اسم المستلم")} htmlFor="parcel-name">
        <AuthInput
          id="parcel-name"
          value={name}
          maxLength={80}
          autoComplete="off"
          placeholder={tr("الاسم كما يناديه الكابتن")}
          onChange={(event) => setName(event.target.value)}
        />
      </AuthBlock>
      <PhoneFieldsT2
        draft={phoneDraft}
        id="parcel-phone"
        label={fetch ? tr("رقمه") : tr("رقم المستلم")}
        error={phoneError}
        valid={complete}
      />
      <AuthBlock label={fetch ? tr("عنوان الاستلام") : tr("عنوان التسليم")} htmlFor="parcel-address">
        <AuthInput
          id="parcel-address"
          value={address}
          maxLength={255}
          autoComplete="off"
          placeholder={fetch ? tr("الحيّ والشارع والبناية والطابق") : tr("الحيّ والشارع والبناية")}
          onChange={(event) => setAddress(event.target.value)}
        />
      </AuthBlock>

      {fetch ? (
        <p className="t2-note t2-fo-keep">
          <Icon name="payments" />
          {payPhrase ? tr("تدفع أنت حين يصلك — {0}.", { 0: payPhrase }) : tr("تدفع أنت حين يصلك.")}
        </p>
      ) : (
        <>
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
        </>
      )}

      {/* **سطرُ الخصوصيّة** (أمرُ المالك ٢٠٢٦-١١-٢١) — وهو ما تفعله الخلفيةُ فعلاً: الرقمُ في أطوار القبول وحدَها (`PASSENGER_VISIBLE`) */}
      <p className="t2-note t2-fo-keep">
        <Icon name="visibility" />
        {tr("يرى الكابتنُ الرقمَ أثناء هذا الطلب فقط، ويُخفى عنه بعد انتهائه.")}
      </p>
      <p className="t2-note t2-fo-keep">
        <Icon name="lock" />
        {fetch
          ? tr("نحفظ اسمَ من يسلّم الغرضَ ورقمَه ووصفَ الغرض لهذا الطلب وحده، ونحذفها بعد ثلاثين يوماً.")
          : tr("نحفظ بيانات المستلم لهذا التوصيل وحده، ونحذفها بعد ثلاثين يوماً.")}
      </p>

      {/* **ملخّصُ الطلب قبل «تأكيد»** (أمرُ المالك ٢٠٢٦-١١-٢١) — من ورقة الطلب نفسِها */}
      {summary ? (
        <div className="t2-pc-sum" aria-label={tr("ملخّص الطلب")}>
          <div className="t2-pc-sum-row">
            <span className="t2-route-from" aria-hidden="true" />
            <span className="t2-pc-sum-label">{tr("من")}</span>
            <span className="t2-pc-sum-value">{summary.from}</span>
          </div>
          <div className="t2-pc-sum-row">
            <span className="t2-route-to" aria-hidden="true" />
            <span className="t2-pc-sum-label">{tr("إلى")}</span>
            <span className="t2-pc-sum-value">{summary.to}</span>
          </div>
          {summary.fare ? (
            <div className="t2-pc-sum-row">
              <Icon name="sell" />
              <span className="t2-pc-sum-label">{tr("السعر التقديري")}</span>
              <span className="t2-pc-sum-value strong" dir="ltr">{summary.fare}</span>
            </div>
          ) : null}
          {summary.payment ? (
            <div className="t2-pc-sum-row">
              <Icon name="payments" />
              <span className="t2-pc-sum-label">{tr("الدفع")}</span>
              <span className="t2-pc-sum-value">{summary.payment}</span>
            </div>
          ) : null}
        </div>
      ) : null}
    </SheetModalT2>
  );
}

/** **كتلةُ الطرد في ورقة التتبّع** (R07–R09): «إلى: المستلم» وعنوانُه حين يُنشران (من القبول حتى الانتهاء)، **وسطرُ الدافع حين
 *  يدفع المستلم** — ومرسلُه الدافعُ يرى قناتَه في صفّ الدفع كأيِّ رحلة. **ولا رابطَ تتبّعٍ للطرد**: لم يُطلب (§٦٣-ج/٤). */
export function ParcelTrackT2({ ride }: { ride: Ride }) {
  // **«أحضر غرضي»** (§٧٢-ج/١، R4): «من: الاسم» وعنوانُ الاستلام، والغرضُ — كما يُنشر من القبول حتى الانتهاء
  if (ride.parcel_fetch) {
    if (!ride.recipient_name) return null;
    return (
      <div className="t2-fo-ride">
        <div className="t2-fo-ride-card">
          <div className="t2-fo-ride-name">
            <Icon name="inventory_2" />
            <span className="t2-pc-ride-to">
              <span>
                {tr("من:")}{" "}<b>{ride.recipient_name}</b>
              </span>
              {ride.recipient_address ? <span className="t2-pc-ride-addr">{ride.recipient_address}</span> : null}
            </span>
          </div>
          {ride.parcel_item ? (
            <div className="t2-fo-ride-payer">
              <Icon name="package_2" />
              <span>{tr("الغرض:")}{" "}{ride.parcel_item}</span>
            </div>
          ) : null}
        </div>
      </div>
    );
  }
  if (!ride.recipient_name && ride.payer !== "recipient_cash") return null;
  return (
    <div className="t2-fo-ride">
      <div className="t2-fo-ride-card">
        {ride.recipient_name ? (
          <div className="t2-fo-ride-name">
            <Icon name="package_2" />
            <span className="t2-pc-ride-to">
              <span>
                {tr("إلى:")}{" "}<b>{ride.recipient_name}</b>
              </span>
              {ride.recipient_address ? <span className="t2-pc-ride-addr">{ride.recipient_address}</span> : null}
            </span>
          </div>
        ) : null}
        {ride.payer === "recipient_cash" ? (
          <div className="t2-fo-ride-payer">
            <Icon name="payments" />
            <span>{payerLine("recipient_cash", null)}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
