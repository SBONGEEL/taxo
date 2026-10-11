/** **تسمياتُ نظام الدفع الجديد** (SPEC §٧٣-هـ) — بيتُها في تطبيق الكبتن، ونصُّها نصُّ تطبيق الراكب حرفاً. */
import type { PaymentRequestStatus } from "@/api/types";

/** **حالاتُ الدفعة في النظام الجديد** (SPEC §٧٣-هـ) — كما يقرؤها صاحبُها. */
export const PAYMENT_REQUEST_STATUS_LABEL: Record<PaymentRequestStatus, string> = {
  pending: "قيد المراجعة",
  approved: "اعتُمدت",
  rejected: "رُفضت",
  refunded: "رُدّت",
  cancelled: "أُلغيت",
};
