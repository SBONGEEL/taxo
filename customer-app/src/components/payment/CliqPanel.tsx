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
 */

import { motion } from "framer-motion";
import { Check, Copy, ExternalLink, Hourglass } from "lucide-react";
import { useState } from "react";

import { ApiError } from "@/api/client";
import { submitCliqReference } from "@/api/endpoints";
import type { CliqCharge, RidePayments } from "@/api/types";
import { QrCode } from "@/components/QrCode";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { formatMoney } from "@/lib/utils";

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
      className="card space-y-16 p-16"
    >
      <header>
        <h2 className="font-semibold text-ink">الدفع عبر كليك</h2>
        <p className="text-14 text-muted">
          حوّل {formatMoney(charge.amount, charge.currency)} إلى alias الكبتن، ثم أدخل
          مرجع الحوالة.
        </p>
      </header>

      <div className="flex justify-center">
        <QrCode payload={charge.qr_payload} />
      </div>

      <dl className="space-y-8 text-14">
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
        <div className="flex items-center justify-between gap-8">
          <dt className="text-muted">المبلغ</dt>
          <dd className="font-semibold text-ink">
            {formatMoney(charge.amount, charge.currency)}
          </dd>
        </div>
      </dl>

      <Button variant="secondary" className="w-full" asChild>
        <a href={charge.deep_link}>
          <ExternalLink className="size-16" />
          افتح تطبيق البنك
        </a>
      </Button>

      {submitted ? (
        <div className="flex items-start gap-8 rounded-12 border border-line bg-bg p-12 text-14">
          <Hourglass className="mt-2 size-16 shrink-0 text-muted" />
          <div>
            <p className="font-medium text-ink">أرسلنا مرجعك للكبتن — بانتظار تأكيده</p>
            <p dir="ltr" className="mt-2 text-muted">
              {charge.transfer_reference}
            </p>
            <p className="mt-4 text-12 text-muted">
              المرجع يُسجَّل مرةً واحدة ولا يُعدَّل. إن لم تصل الحوالة الكبتنَ سيفتح
              نزاعاً تفصل فيه الإدارة.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-12 border-t border-line pt-12">
          <Field
            label="مرجع الحوالة من تطبيق بنكك"
            value={reference}
            dir="ltr"
            className="text-start"
            onChange={(event) => setReference(event.target.value)}
            placeholder="FT24…"
            hint="يُسجَّل مرةً واحدة ولا يُعدَّل — تأكّد منه قبل الإرسال."
          />
          <ErrorNote message={error} />
          <Button
            className="w-full"
            loading={busy}
            disabled={reference.trim().length < 3}
            onClick={submit}
          >
            حوّلتُ — أرسل المرجع للكبتن
          </Button>
        </div>
      )}
    </motion.section>
  );
}

function CopyRow({
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
    <div className="flex items-center justify-between gap-8">
      <dt className="text-muted">{label}</dt>
      <dd className="flex items-center gap-8">
        <span dir="ltr" className="font-semibold text-ink">
          {value}
        </span>
        <button
          type="button"
          onClick={onCopy}
          className="rounded-8 p-6 text-muted transition hover:bg-surface-2 hover:text-ink"
          aria-label={`نسخ ${label}`}
        >
          {copied ? (
            <Check className="size-16 text-ok" />
          ) : (
            <Copy className="size-16" />
          )}
        </button>
      </dd>
    </div>
  );
}
