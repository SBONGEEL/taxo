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
import { PAYER_LINE } from "@/lib/for-other";
import { AuthBlock, AuthInput, Icon } from "@/taxo2";

import { PAYER_SHORT, PhoneFieldsT2, usePhoneDraft } from "./ForOtherT2";
import { SheetModalT2 } from "./MoneyT2";
import "./t2.css";
import "./for-other.css";
import "./parcel.css";

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
          <span className="t2-icon">{fetch ? "inventory_2" : "package_2"}</span>
        </span>
        <span className="t2-fo-chip-main">
          <span className="t2-fo-chip-title">
            {fetch ? `من: ${draft.recipient_name} · ${draft.item ?? ""}` : `إلى: ${draft.recipient_name}`}
          </span>
          <span className="t2-fo-chip-sub">
            <span dir="ltr">{draft.recipient_phone}</span> · {fetch ? "تدفع أنت" : PAYER_SHORT[draft.payer]}
          </span>
        </span>
        <button
          type="button"
          className="t2-fo-chip-btn"
          onClick={onOpen}
          aria-label={fetch ? "تعديل بيانات الغرض" : "تعديل بيانات الطرد"}
        >
          <span className="t2-icon" aria-hidden="true">edit</span>
        </button>
      </div>
    );
  }
  return (
    <button type="button" className="t2-share t2-fo-open" onClick={onOpen}>
      <span className="t2-share-main">
        <span className="t2-share-title">
          <span className="t2-icon" aria-hidden="true">{fetch ? "inventory_2" : "package_2"}</span>
          {fetch ? "بيانات الغرض" : "بيانات الطرد"}
        </span>
        <span className="t2-share-body">
          {fetch ? "اقرأ الشروط، واكتب الغرضَ ومن يسلّمه للكبتن." : "اقرأ الشروط، واكتب المستلمَ ومن يدفع."}
        </span>
      </span>
      <span className="t2-icon t2-fo-open-go" aria-hidden="true">chevron_left</span>
    </button>
  );
}

/** **ورقةُ الطرد** — الشروطُ الأربعُ بلفظ الخلفية ومربّعُ الإقرار بها، **ثمّ المستلم** (اسمُه ورقمُه وعنوانُ التسليم) **ومن يدفع**،
 *  وسطرُ الحفظ والمحو بنصّ الوعد (ثلاثون يوماً — كنسُ الراكب الفعليّ نفسُه في الخلفية).
 *
 *  **والإقرارُ لا يُعطى قبل أن تُقرأ الشروط**: المربّعُ معطَّلٌ ما دامت لم تصل، **وورقةٌ تعود للتعديل تبدأ بإقرارها كما كان** —
 *  الشروطُ هي هي ما دام الطلبُ نفسَه. **والرقمُ بحقل «لشخص آخر» نفسِه** (`PhoneFieldsT2`): دولتُه ومفتاحُه من `/config`، ويُرسل
 *  E.164 — **ورقمُه هو لا يُرفض**: من يرسل طرداً إلى نفسه في مكانٍ آخر يُرسله. */
export function ParcelSheetT2({
  terms,
  failed,
  initial,
  fetch = false,
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
  onSave: (next: RideParcel) => void;
  onClose: () => void;
}) {
  const phoneDraft = usePhoneDraft(initial?.recipient_phone ?? null);
  const { dialCode, complete, full } = phoneDraft;
  const [accepted, setAccepted] = useState(initial?.accepted_terms ?? false);
  const [name, setName] = useState(initial?.recipient_name ?? "");
  const [address, setAddress] = useState(initial?.recipient_address ?? "");
  const [payer, setPayer] = useState<RideParcel["payer"]>(initial?.payer ?? "requester");
  const [item, setItem] = useState(initial?.item ?? "");

  const phoneError = dialCode === null ? "مفتاحُ هذه الدولة غير متاح الآن — اختر دولةً أخرى أو أعد المحاولة." : null;
  // **حدودُ الخلفية نفسُها** (`ParcelIn`): اسمٌ بحرفين وعنوانٌ بثلاثة — وما بعدها ترفضه هي بنصّها
  const ready =
    terms !== null &&
    accepted &&
    name.trim().length >= 2 &&
    full !== null &&
    address.trim().length >= 3 &&
    (!fetch || item.trim().length >= 2);

  const payers: Array<{ value: RideParcel["payer"]; icon: string; label: string; hint: string }> = [
    { value: "requester", icon: "account_balance_wallet", label: "أنا أدفع", hint: "عند الاستلام منك — بأيِّ طريقة دفع" },
    {
      value: "recipient_cash",
      icon: "payments",
      label: "المستلم يدفع نقداً عند التسليم",
      hint: "يسلّم الأجرةَ للكبتن بيده",
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
          تأكيد
        </button>
      }
    >
      <div className="t2-picker-title">{fetch ? "أحضر غرضي" : "طرد"}</div>
      {fetch ? (
        <p className="t2-note t2-pf-lead">
          <span className="t2-icon" aria-hidden="true">inventory_2</span>
          يأخذ الكبتنُ غرضك من حيث تقول ويوصله إليك.
        </p>
      ) : null}

      {/* **الشروطُ أوّلاً** (§٦٣-ج/٤: «يُعرض على المرسل قبل أن يطلب») — بلفظ الخلفية، ومربّعُ الإقرار تحتها */}
      <div className="t2-auth-consent t2-pc-terms">
        <div className="t2-pc-terms-title">
          <Icon name="gavel" />
          {fetch ? "الشروط" : "شروط الطرد"}
        </div>
        {terms ? (
          <ul className="t2-pc-terms-list">
            {terms.map((term) => (
              <li key={term}>{term}</li>
            ))}
          </ul>
        ) : (
          <p className="t2-pc-terms-wait">
            {failed ? "تعذّرت قراءة الشروط — أغلق الورقة وأعد المحاولة." : "نقرأ الشروط…"}
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
          <span>قرأتُ الشروط وأوافق عليها</span>
        </button>
      </div>

      {fetch ? (
        <>
          <AuthBlock label="ما الغرض؟" htmlFor="parcel-item">
            <AuthInput
              id="parcel-item"
              value={item}
              maxLength={120}
              autoComplete="off"
              placeholder="مثلاً: شاحن هاتف على طاولة المدخل"
              onChange={(event) => setItem(event.target.value)}
            />
          </AuthBlock>
          <div className="t2-pick-head">
            <span className="t2-pick-title">من يسلّمه للكبتن؟</span>
          </div>
        </>
      ) : null}
      <AuthBlock label={fetch ? "الاسم" : "اسم المستلم"} htmlFor="parcel-name">
        <AuthInput
          id="parcel-name"
          value={name}
          maxLength={80}
          autoComplete="off"
          placeholder="الاسم كما يناديه الكبتن"
          onChange={(event) => setName(event.target.value)}
        />
      </AuthBlock>
      <PhoneFieldsT2
        draft={phoneDraft}
        id="parcel-phone"
        label={fetch ? "رقمه" : "رقم المستلم"}
        error={phoneError}
        valid={complete}
      />
      <AuthBlock label={fetch ? "عنوان الاستلام" : "عنوان التسليم"} htmlFor="parcel-address">
        <AuthInput
          id="parcel-address"
          value={address}
          maxLength={255}
          autoComplete="off"
          placeholder={fetch ? "الحيّ والشارع والبناية والطابق" : "الحيّ والشارع والبناية"}
          onChange={(event) => setAddress(event.target.value)}
        />
      </AuthBlock>

      {fetch ? (
        <p className="t2-note t2-fo-keep">
          <span className="t2-icon" aria-hidden="true">payments</span>
          تدفع أنت حين يصلك — بالمحفظة أو البطاقة أو نقداً عند التسليم.
        </p>
      ) : (
        <>
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
        </>
      )}

      <p className="t2-note t2-fo-keep">
        <span className="t2-icon" aria-hidden="true">lock</span>
        {fetch
          ? "نحفظ اسمَ من يسلّم الغرضَ ورقمَه ووصفَ الغرض لهذا الطلب وحده، ونحذفها بعد ثلاثين يوماً."
          : "نحفظ بيانات المستلم لهذا التوصيل وحده، ونحذفها بعد ثلاثين يوماً."}
      </p>
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
            <span className="t2-icon" aria-hidden="true">inventory_2</span>
            <span className="t2-pc-ride-to">
              <span>
                من: <b>{ride.recipient_name}</b>
              </span>
              {ride.recipient_address ? <span className="t2-pc-ride-addr">{ride.recipient_address}</span> : null}
            </span>
          </div>
          {ride.parcel_item ? (
            <div className="t2-fo-ride-payer">
              <span className="t2-icon" aria-hidden="true">package_2</span>
              <span>الغرض: {ride.parcel_item}</span>
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
            <span className="t2-icon" aria-hidden="true">package_2</span>
            <span className="t2-pc-ride-to">
              <span>
                إلى: <b>{ride.recipient_name}</b>
              </span>
              {ride.recipient_address ? <span className="t2-pc-ride-addr">{ride.recipient_address}</span> : null}
            </span>
          </div>
        ) : null}
        {ride.payer === "recipient_cash" ? (
          <div className="t2-fo-ride-payer">
            <span className="t2-icon" aria-hidden="true">payments</span>
            <span>{PAYER_LINE.recipient_cash}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
