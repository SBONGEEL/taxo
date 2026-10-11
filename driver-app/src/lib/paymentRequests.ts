/** **تسمياتُ نظام الدفع الجديد** (SPEC §٧٣-هـ) — بيتُها في تطبيق الكبتن، ونصُّها نصُّ تطبيق الراكب حرفاً. */
import type { PaymentRequestStatus } from "@/api/types"; import { tr } from "@/lib/i18n";

/** **حالاتُ الدفعة في النظام الجديد** (SPEC §٧٣-هـ) — كما يقرؤها صاحبُها. */
export const PAYMENT_REQUEST_STATUS_LABEL: Record<PaymentRequestStatus, string> = {
  pending: tr("قيد المراجعة"),
  approved: tr("اعتُمدت"),
  rejected: tr("رُفضت"),
  refunded: tr("رُدّت"),
  cancelled: tr("أُلغيت"),
};
