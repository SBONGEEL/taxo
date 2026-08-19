/** جلسةُ بوابة واتساب الذاتية — **الشاشةُ التي تمنع سقوطاً صامتاً**.
 *
 * جلسةٌ تسقط ولا يعلم بها أحد تعني **توقّفَ تسجيل المستخدمين الجدد كلِّهم**،
 * ويُكتشف ذلك بعد ساعاتٍ من أرقامٍ تنقص لا من رسالةٍ تصل. ولذلك بابان: هذه
 * البطاقة (لمن يفتح اللوحة)، وتنبيهٌ يصل المشرفين على **تحوّل** الحال
 * (`tasks/whatsapp.py`) — لأن من لا يفتح اللوحة لا تراه بطاقة.
 *
 * **وخمسُ حالاتٍ لا اثنتان**، وهو كلُّ ما تشتريه هذه البطاقة: «غير متصل» لا
 * تقول أينتظر إنساناً يمسح رمزاً أم شبكةً تعود وحدها — والفرقُ بينهما هو
 * الفرقُ بين أن يتحرك المشرفُ الآن أو ينتظر دقيقة.
 *
 * **والرمزُ يُرسم في المتصفح** كرمز العامل الثاني: خدمةُ QR خارجية تعني إرسالَ
 * مفتاحِ ربطِ حسابنا إلى طرفٍ ثالث في نداءٍ لا يراه أحد.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { getWhatsAppSession, logoutWhatsAppSession } from "@/api/endpoints";
import type { WhatsAppSession as SessionRow } from "@/api/types";
import { QrCode } from "@/components/QrCode";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { moment } from "@/lib/format";

const TONE: Record<string, Parameters<typeof Badge>[0]["tone"]> = {
  linked: "ok",
  awaiting_qr: "warn",
  disconnected: "warn",
  unreachable: "danger",
  off: "muted",
};

const LABEL: Record<string, string> = {
  linked: "مرتبطة",
  awaiting_qr: "بانتظار مسح الرمز",
  disconnected: "منقطعة — تحاول العودة",
  unreachable: "البوابة لا تُجيب",
  off: "غير مستعملة",
};

/** ما **يفعله** المشرف، لا ما وقع: حالةٌ بلا فعلٍ تُقرأ ثم تُترك. */
const ACTION: Record<string, string> = {
  linked: "لا شيء مطلوب — إرسالُ الرموز يعمل.",
  awaiting_qr:
    "امسح الرمز من هاتف الرقم المخصّص: واتساب › الإعدادات › الأجهزة المرتبطة › ربط جهاز. والتسجيلُ متوقفٌ حتى تفعل.",
  disconnected:
    "تعود وحدها غالباً خلال دقيقة. وإن طالت فالرموزُ ترتدّ إلى الرسائل القصيرة تلقائياً.",
  unreachable:
    "خدمةُ البوابة نفسُها لا تردّ — راجع الخادم (`docker compose ps whatsapp-gateway`).",
  off: "عقدُ واتساب على القناة الرسمية (cloud) أو غيرُ مفعّل — لا جلسةَ تُراقَب.",
};

// **خمسُ ثوانٍ ما دامت تنتظر رمزاً، وثلاثون فيما عداها**: من يقف أمام الشاشة
// يمسح رمزاً يحتاج أن يراها تتحوّل إلى «مرتبطة» في ثوانٍ؛ ومن يفتحها ليطمئنّ
// لا يحتاج نداءً كلَّ خمس. وهي حجّةُ استطلاعِ شاشةِ الدفع نفسُها
const FAST_MS = 5_000;
const SLOW_MS = 30_000;

export function WhatsAppSession({ onError }: { onError: (m: string) => void }) {
  const [row, setRow] = useState<SessionRow | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    getWhatsAppSession()
      .then(setRow)
      .catch((caught) =>
        onError(caught instanceof ApiError ? caught.message : "تعذّر قراءة الحالة"),
      );
  }, [onError]);

  useEffect(load, [load]);

  const waiting = row?.state === "awaiting_qr";
  useEffect(() => {
    const timer = window.setInterval(load, waiting ? FAST_MS : SLOW_MS);
    return () => window.clearInterval(timer);
  }, [load, waiting]);

  if (row === null || row.state === "off") return null;

  return (
    <article className="rounded-16 border border-line bg-surface p-18">
      <div className="mb-8 flex items-start gap-12">
        <div className="flex-1">
          <h2 className="text-14 font-bold text-ink">جلسة واتساب الذاتية</h2>
          <p className="mt-3 text-11 text-muted">
            بوابةٌ داخليةٌ على رقمٍ مخصّص — لا تكلّمها إلا الخلفية
          </p>
        </div>
        <span className="flex items-center gap-6">
          <Badge tone={TONE[row.state] ?? "muted"}>
            {LABEL[row.state] ?? row.state}
          </Badge>
        </span>
      </div>

      <p className="mb-12 text-11.5 leading-note text-muted">
        {ACTION[row.state] ?? ""}
      </p>

      {row.phone ? (
        <p className="mb-10 text-12 text-ink">
          الرقم <span dir="ltr">{row.phone}</span>
          {row.since ? (
            <span className="text-muted"> · منذ {moment(row.since)}</span>
          ) : null}
        </p>
      ) : null}

      {/* **الاحتياطُ يُرى، لا يُكتفى بتسجيله** (قرارُ المالك 2026-08-19):
          هذا العطبُ نفسُه عمل شهراً لأن أثرَه كان سطراً في سجلِّ حاوية — شاشةُ
          القوالب تحفظ وتعاين، والسلكُ يحمل النصَّ المدمج، ولا شيءَ يفشل. */}
      {row.template_rules_loaded === false ? (
        <p className="mb-10 text-11 leading-note text-danger">
          البوابةُ لا تقرأ ملفَّ شروط القالب، فترفض <b>كلَّ</b> قالبٍ محرَّرٍ
          وتُرسل نصَّها المدمج.
          {row.template_rules_error ? ` (${row.template_rules_error})` : ""}
        </p>
      ) : row.last_template_fallback ? (
        <p className="mb-10 text-11 leading-note text-warn">
          آخرُ رسالةٍ خرجت بالنصِّ المدمج لا بقالبك
          {row.last_template_fallback.purpose
            ? ` (${row.last_template_fallback.purpose})`
            : ""}
          {row.last_template_fallback.violations?.length
            ? ` — ${row.last_template_fallback.violations.join("، ")}`
            : ""}
        </p>
      ) : null}

      {row.last_error && row.state !== "linked" ? (
        <p className="mb-10 text-11 text-danger">{row.last_error}</p>
      ) : null}

      {row.qr ? (
        <div className="mb-12 flex flex-col items-center gap-8">
          <QrCode payload={row.qr} size={200} />
          <p className="text-11 text-muted">
            الرمزُ يتجدّد من نفسه — إن انتهى فانتظر ثوانيَ ليظهر غيرُه.
          </p>
        </div>
      ) : null}

      {/* **والفصلُ آخرُ ما يُعرض وبتحذيره**: يوقف التسجيلَ حتى يمسح إنسانٌ
          رمزاً جديداً، فليس زرَّ إصلاحٍ بل زرَّ تبديلِ رقم */}
      <Button
        size="sm"
        variant="secondary"
        loading={busy}
        onClick={() => {
          setBusy(true);
          logoutWhatsAppSession()
            .then(setRow)
            .catch((caught) =>
              onError(caught instanceof ApiError ? caught.message : "تعذّر الفصل"),
            )
            .finally(() => setBusy(false));
        }}
      >
        افصِل الجلسة لربط رقمٍ آخر
      </Button>
      <p className="mt-6 text-11 leading-note text-muted">
        الفصلُ يمحو الجلسةَ ويوقف الإرسالَ عبر واتساب حتى تُربط من جديد —
        والرموزُ ترتدّ إلى الرسائل القصيرة في أثناء ذلك.
      </p>
    </article>
  );
}
