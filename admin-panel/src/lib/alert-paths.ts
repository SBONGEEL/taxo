/** **سجلُّ الإشعار ← مسارُه في اللوحة** (SPEC §٨١) — بلا استيراد، فيقرؤه الجرسُ والقائمةُ ونقرُ الهاتف معاً بلا حلقة.
 *
 * **ولا مسارَ يصل من الخادم ولا من الإشعار**: نوعُ السجلّ ومعرّفُه وحدَهما — فإشعارٌ مزوَّرٌ لا يفتح بابَ شيء. **والصفُّ المجموعُ**
 * (بلا سجلّ) يفتح القائمةَ مرشَّحةً بنوعه. **ونسختُه في عامل المتصفّح** (`public/alerts-sw.js`) حرفاً — من عدّل هذه عدّل تلك.
 */

export interface AlertRecord {
  record_type: string | null;
  record_id: string | null;
  kind: string;
}

export function recordPath(alert: AlertRecord): string {
  const id = alert.record_id ? encodeURIComponent(alert.record_id) : "";
  switch (alert.record_type) {
    case "ride":
      return `/rides?open=${id}`;
    case "driver":
      return `/drivers?open=${id}`;
    case "rider":
      return `/riders?open=${id}`;
    case "withdrawal":
      return "/finance";
    case "topup_request":
      return "/finance?tab=topups";
    case "payment_request":
      return "/payment-system";
    // **تحويلُ BaridiMob** (SPEC §٨٢-ب/٤) — صفحةُ مراجعته
    case "transfer":
      return "/transfers";
    case "feedback":
      return "/feedback";
    case "chat_report":
      return "/chat-reports";
    case "photo_report":
      return "/photo-reports";
    default:
      return `/alerts?kind=${encodeURIComponent(alert.kind)}`;
  }
}
