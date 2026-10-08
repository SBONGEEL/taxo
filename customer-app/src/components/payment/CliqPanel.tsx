/** صفحة دفع كليك داخل التطبيق — الميزة التي تسمّيها المرحلة 9 (SPEC 16.9).
 *
 * تنفّذ خطوات القسم 6.2 بترتيبها:
 *
 * 1. **رمزٌ ديناميكي** يحمل alias الكبتن والمبلغ ومرجعاً داخلياً يولّده TAXO
 *    — الحمولة تأتي مبنيّةً من الخلفية (`services/cliq_qr.py`) وتُرسم هنا.
 * 2. **deep link** يفتح تطبيق البنك على شاشة تحويلٍ مملوءة.
 * 3. **إدخال مرجع الحوالة** بعد أن يحوّل الراكب من بنكه.
 * 4. ثم **إشعارٌ فوري للكبتن** ليؤكد «وصلني» أو ينازع — وذلك من الخلفية.
 *
 * وقاعدةٌ واحدة تحكم الشاشة كلها: **المرجع يُكتب مرةً ولا يُعدَّل** (القسم
 * 6.5). فبعد إرساله تتحول الشاشة إلى «بانتظار تأكيد الكبتن» ولا يبقى حقلٌ
 * يُكتب فيه — والخطأ في الرقم يعالجه نزاعُ الكبتن وفصلُ الإدارة (13.4).
 *
 * ولا زرَّ «تم الدفع» هنا: المال يذهب إلى alias الكبتن مباشرةً ولا يمر
 * بالمنصة، فلا أحد عندنا يشهد عليه — والتأكيد قولُ الكبتن وحده (القسم 6).
 *
 * **بلغة TAXO 2.0** (لوحةُ `design/t2-new/rider/R19b`): بطاقةٌ بيضاءُ بزاوية R10 — الرمزُ، ثمّ ما يُنسخ، ثمّ «افتح تطبيق البنك»، ثمّ
 * المرجعُ بحقل R03 وسببُ خطئه تحته.
 *
 * **والرمزُ يُنزع حيث `unconfirmed_payments_enabled` مشتعل** (`design/PAYMENTS-UNCONFIRMED.md` §٤-٢، SPEC §٦٤-ز): يُعرض على هاتف
 * الدافع نفسِه فلا يُمسح، **وقيمُه مخمَّنة** (ترتيبُ حقول Jo-QR غيرُ منشور) — «زرٌّ يبدو عاملاً ولا يعمل». **ومطفأً كما كان
 * حرفاً**: المفتاحُ يحكم المسارَ كلَّه، و«مطفأً يبقى كلُّ شيءٍ كما كان» (§٦٤-ز). وما يُنسخ هو البديلُ الموثوق — الاسمُ المستعار
 * والمبلغُ والمرجع.
 */

import { motion } from "framer-motion";
import { useState } from "react";

import { ApiError } from "@/api/client";
import { submitCliqReference } from "@/api/endpoints";
import type { CliqCharge, RidePayments } from "@/api/types";
import { QrCode } from "@/components/QrCode";
import { useFeature } from "@/lib/config";
import { UNCONFIRMED_FLAG } from "@/lib/payment";
import { useSession } from "@/lib/session";
import { formatMoney } from "@/lib/utils";
import { AuthBlock, AuthInput, Icon } from "@/taxo2";
import { BusyLabel } from "@/screens/t2/MoneyT2";

export function CliqPanel({
  charge,
  onSubmitted,
}: {
  charge: CliqCharge;
  onSubmitted: (state: RidePayments) => void;
}) {
  const [reference, setReference] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  // **الرمزُ المخمَّن خارجَ المسار الجديد** (§٤-٢) — والسوقُ المطفأُ يرى الشاشةَ كما كانت
  const { user } = useSession();
  const guessedQrRemoved = useFeature(user?.country_code, UNCONFIRMED_FLAG);

  const submitted = charge.transfer_reference !== null;

  async function copy(value: string, label: string) {
    await navigator.clipboard?.writeText(value).catch(() => undefined);
    setCopied(label);
    window.setTimeout(() => setCopied(null), 2_000);
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      onSubmitted(await submitCliqReference(charge.payment_id, reference.trim()));
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر تسجيل مرجع الحوالة",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="t2-m-card t2-m-gap"
    >
      <h2 className="t2-m-cliq-title sm">الدفع عبر كليك</h2>
      <p className="t2-m-cliq-text sm">
        حوّل {formatMoney(charge.amount, charge.currency)} إلى alias الكبتن، ثم أدخل
        مرجع الحوالة.
      </p>

      {guessedQrRemoved ? null : <QrCode payload={charge.qr_payload} size={180} />}

      <dl className="t2-m-copies">
        <CopyRow
          label="alias الكبتن"
          value={charge.alias}
          copied={copied === "alias"}
          onCopy={() => copy(charge.alias, "alias")}
        />
        <CopyRow
          label="المرجع (اكتبه في ملاحظة الحوالة)"
          value={charge.reference}
          copied={copied === "reference"}
          onCopy={() => copy(charge.reference, "reference")}
        />
        <div className="t2-m-copy">
          <dt>المبلغ</dt>
          <dd>{formatMoney(charge.amount, charge.currency)}</dd>
        </div>
      </dl>

      <a href={charge.deep_link} className="t2-button secondary t2-m-open">
        <Icon name="open_in_new" />
        افتح تطبيق البنك
      </a>

      {submitted ? (
        <div className="t2-callout t2-m-callout">
          <Icon name="hourglass_top" />
          <div className="t2-callout-main">
            <p className="t2-callout-title">أرسلنا مرجعك للكبتن — بانتظار تأكيده</p>
            <p dir="ltr" className="t2-callout-body t2-m-ref">
              {charge.transfer_reference}
            </p>
            <p className="t2-callout-body">
              المرجع يُسجَّل مرةً واحدة ولا يُعدَّل. إن لم تصل الحوالة الكبتنَ سيفتح
              نزاعاً تفصل فيه الإدارة.
            </p>
          </div>
        </div>
      ) : (
        <>
          <div className="t2-m-dash" aria-hidden="true" />
          {/* **سببُ الخطأ تحت حقله** (§٦٢/٢٠) — والتلميحُ مكانَه حين لا خطأ */}
          <AuthBlock
            label="مرجع الحوالة من تطبيق بنكك"
            htmlFor="cliq-reference"
            error={error}
            hint="يُسجَّل مرةً واحدة ولا يُعدَّل — تأكّد منه قبل الإرسال."
          >
            <AuthInput
              id="cliq-reference"
              dir="ltr"
              autoComplete="off"
              value={reference}
              invalid={Boolean(error)}
              onChange={(event) => setReference(event.target.value)}
              placeholder="FT24…"
            />
          </AuthBlock>
          <button
            type="button"
            className="t2-button primary t2-m-cta t2-m-field-gap"
            disabled={busy || reference.trim().length < 3}
            aria-busy={busy}
            onClick={submit}
          >
            <BusyLabel busy={busy}>حوّلتُ — أرسل المرجع للكبتن</BusyLabel>
          </button>
        </>
      )}
    </motion.section>
  );
}

/** **سطرُ نسخٍ واحد** — تسميتُه وقيمتُه وزرُّه. **مُصدَّرٌ لورقة «انسخ بيانات التحويل»** (`UnconfirmedT2`): الشكلُ هو هو في
 *  الموضعين، وسطرٌ يُنسخ مرّتين يفترق أوّلَ تعديل. */
export function CopyRow({
  label,
  value,
  copied,
  onCopy,
}: {
  label: string;
  value: string;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <div className="t2-m-copy">
      <dt>{label}</dt>
      <dd>
        <span dir="ltr">{value}</span>
        <button
          type="button"
          onClick={onCopy}
          className={copied ? "t2-m-copy-btn done" : "t2-m-copy-btn"}
          aria-label={`نسخ ${label}`}
        >
          <Icon name={copied ? "check" : "content_copy"} />
        </button>
      </dd>
    </div>
  );
}
