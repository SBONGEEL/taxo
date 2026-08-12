/** دفعات الرحلة — **قائمةٌ دائماً وإن كان فيها عنصر واحد**.
 *
 * الدفع المختلط رحلةٌ واحدة بصفّين: ما كفاه رصيد المحفظة والباقي كاش (SPEC
 * القسم 6). فعرضُ «الدفعة» مفرداً يخفي نصف ما دُفع.
 *
 * **وصفُّ `promo` خصمٌ لا دفعة** (12-ز): تدفعه الشركةُ عن الراكب، فيُرسم
 * بإشارة ناقصٍ وبلون `--ok` بلا حالةٍ ولا تاريخ — «مؤكَّد» على خصمٍ تلقائيٍّ
 * كلامٌ زائد، وعرضُه كدفعةٍ عادية يجعل الراكب يظن أنه دفع مبلغين.
 */

import { TicketPercent } from "lucide-react";

import type { Payment } from "@/api/types";
import { Badge } from "@/components/ui/Feedback";
import { PAYMENT_METHOD_LABEL, PAYMENT_STATUS_LABEL } from "@/lib/labels";
import { formatDateTime, formatMoney } from "@/lib/utils";

const TONE = {
  confirmed: "success",
  pending: "warning",
  disputed: "danger",
  failed: "danger",
  refunded: "neutral",
} as const;

export function PaymentsList({ payments }: { payments: Payment[] }) {
  return (
    <section className="space-y-8">
      <h2 className="label">دفعات هذه الرحلة</h2>
      <ul className="space-y-8">
        {payments.map((payment) =>
          payment.method === "promo" ? (
            <li
              key={payment.id}
              className="card flex items-center justify-between gap-8 p-12"
            >
              <span className="flex items-center gap-8 font-medium text-ok">
                <TicketPercent className="size-16" />
                {PAYMENT_METHOD_LABEL.promo}
              </span>
              <span className="font-semibold text-ok">
                −{formatMoney(payment.amount, payment.currency)}
              </span>
            </li>
          ) : (
          <li key={payment.id} className="card p-12">
            <div className="flex items-center justify-between gap-8">
              <span className="font-medium text-ink">
                {PAYMENT_METHOD_LABEL[payment.method]}
              </span>
              <span className="font-semibold text-ink">
                {formatMoney(payment.amount, payment.currency)}
              </span>
            </div>
            <div className="mt-6 flex items-center justify-between gap-8 text-12 text-muted">
              <Badge tone={TONE[payment.status]}>
                {PAYMENT_STATUS_LABEL[payment.status]}
              </Badge>
              <span>{formatDateTime(payment.confirmed_at ?? payment.created_at)}</span>
            </div>

            {payment.cliq_transfer_reference ? (
              <p className="mt-8 text-12 text-muted">
                مرجع الحوالة:{" "}
                <span dir="ltr" className="text-ink">
                  {payment.cliq_transfer_reference}
                </span>
              </p>
            ) : null}

            {payment.status === "disputed" && payment.dispute_reason ? (
              <p className="mt-8 text-12 text-danger">
                نزاع: {payment.dispute_reason} — تفصل فيه الإدارة.
              </p>
            ) : null}
          </li>
          ),
        )}
      </ul>
    </section>
  );
}
