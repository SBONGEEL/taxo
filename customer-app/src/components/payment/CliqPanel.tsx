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
 * ولا زرَّ «تم الدفع» هنا: المال يذهب إلى alias الكابتن مباشرةً ولا يمر
 * بالمنصة، فلا أحد عندنا يشهد عليه — والتأكيد قولُ الكابتن وحده (القسم 6).
 *
 * **ولا حقلَ مرجعٍ بعد ٢٠٢٦-١١-٢٦** (SPEC §١١٧، قرارُ المالك): «حوّلتُ — أرسل المرجع» كان خطوةً بيد الراكب، **والكابتنُ وحدَه
 * يؤكّد بـ«تم الاستلام»**. فالبطاقةُ: الاسمُ المستعارُ واسمُ الكابتن كما سُجّل، و«حوّل المبلغ من تطبيق بنكك عبر كليك»، والمبلغُ
 * الدقيقُ بزرّ نسخه. **وبابُ المرجع في الخلفية باقٍ للنسخ الأقدم** (`submitCliqReference`) ولا تناديه هذه الشاشة؛ ومرجعٌ أُرسل من
 * نسخةٍ أقدم يُعرض كما هو.
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

import type { CliqCharge } from "@/api/types";
import { QrCode } from "@/components/QrCode";
import { useFeature } from "@/lib/config";
import { UNCONFIRMED_FLAG } from "@/lib/payment";
import { useSession } from "@/lib/session";
import { formatMoney } from "@/lib/utils";
import { Icon } from "@/taxo2";
import { tr } from "@/lib/i18n";

export function CliqPanel({ charge }: { charge: CliqCharge }) {
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


  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="t2-m-card t2-m-gap"
    >
      <h2 className="t2-m-cliq-title sm">{tr("الدفع عبر كليك")}</h2>
      <p className="t2-m-cliq-text sm">{tr("حوّل المبلغ من تطبيق بنكك عبر كليك")}</p>

      {guessedQrRemoved ? null : <QrCode payload={charge.qr_payload} size={180} />}

      <dl className="t2-m-copies">
        <CopyRow
          label={tr("alias الكابتن")}
          value={charge.alias}
          copied={copied === "alias"}
          onCopy={() => copy(charge.alias, "alias")}
        />
        <CopyRow
          label={tr("المرجع (اكتبه في ملاحظة الحوالة)")}
          value={charge.reference}
          copied={copied === "reference"}
          onCopy={() => copy(charge.reference, "reference")}
        />
        {/* **المبلغُ الدقيقُ بزرّ نسخه** (§١١٧/٢) — كما أرسلته الخلفيةُ بخاناته، ويُرسم بعملته بجانبه */}
        <CopyRow
          label={tr("المبلغ بالضبط ({0})", { 0: formatMoney(charge.amount, charge.currency) })}
          value={charge.amount}
          copied={copied === "amount"}
          onCopy={() => copy(charge.amount, "amount")}
        />
      </dl>

      {/* **اسمُ الكابتن كما سُجّل** — يطابقه الراكبُ باسم المستفيد في بنكه قبل أن يرسل */}
      {charge.captain_name ? (
        <div className="t2-callout t2-m-callout">
          <Icon name="verified_user" />
          <div className="t2-callout-main">
            <p className="t2-callout-title">{tr("ستظهر في بنكك باسم:")}{" "}{charge.captain_name}</p>
            <p className="t2-callout-body">{tr("طابِق الاسمَ قبل أن ترسل — اسمٌ غيرُه يعني أن الحوالةَ لا تذهب إلى كابتن رحلتك.")}</p>
          </div>
        </div>
      ) : null}

      <a href={charge.deep_link} className="t2-button secondary t2-m-open">
        <Icon name="open_in_new" />
        {tr("افتح تطبيق البنك")}
      </a>

      {/* **الكابتنُ وحدَه يؤكّد** (§١١٧/١) — لا زرَّ بيد الراكب؛ ومرجعٌ أرسلته نسخةٌ أقدم يُعرض كما هو */}
      <div className="t2-callout t2-m-callout">
        <Icon name="hourglass_top" />
        <div className="t2-callout-main">
          <p className="t2-callout-title">{tr("بعد التحويل يؤكّد الكابتنُ الاستلام")}</p>
          {submitted ? (
            <p dir="ltr" className="t2-callout-body t2-m-ref">
              {charge.transfer_reference}
            </p>
          ) : null}
          <p className="t2-callout-body">{tr("تُغلق الرحلةُ حين يضغط الكابتنُ «تم الاستلام». وإن لم تصله الحوالةُ يتواصل معك فريقُ TAXO.")}</p>
        </div>
      </div>
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
          aria-label={tr("نسخ {0}", { 0: label })}
        >
          <Icon name={copied ? "check" : "content_copy"} />
        </button>
      </dd>
    </div>
  );
}
