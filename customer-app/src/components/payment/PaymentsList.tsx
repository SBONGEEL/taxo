/** دفعات الرحلة — **قائمةٌ دائماً وإن كان فيها عنصر واحد**.
 *
 * الدفع المختلط رحلةٌ واحدة بصفّين: ما كفاه رصيد المحفظة والباقي كاش (SPEC
 * القسم 6). فعرضُ «الدفعة» مفرداً يخفي نصف ما دُفع.
 *
 * **وصفُّ `promo` خصمٌ لا دفعة** (12-ز): تدفعه الشركةُ عن الراكب، فيُرسم
 * بإشارة ناقصٍ وبلون النجاح بلا حالةٍ ولا تاريخ — «مؤكَّد» على خصمٍ تلقائيٍّ
 * كلامٌ زائد، وعرضُه كدفعةٍ عادية يجعل الراكب يظن أنه دفع مبلغين.
 *
 * **بلغة TAXO 2.0** (لوحتا `design/t2-new/rider/R18b` · `R19b`): قائمةُ «الحركات» في R11 — أيقونةُ القناة في بئرها، والتاريخُ
 * تحت اسمها، والمبلغُ وشارةُ حاله في الطرف.
 */

import type { Payment, PaymentMethod, PaymentStatus } from "@/api/types";
import { PAYMENT_METHOD_LABEL, PAYMENT_STATUS_LABEL } from "@/lib/labels";
import { formatDateTime, formatMoney } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "@/screens/t2/money.css";

/** نبرةُ الشارة بالحال — المؤكَّدُ نجاحٌ، والمنتظَرُ تنبيه، والنزاعُ والفشلُ خطأ، والمستردُّ محايد. */
const TONE: Record<PaymentStatus, string> = {
  confirmed: "t2-chip ok",
  pending: "t2-chip warn",
  disputed: "t2-chip danger",
  failed: "t2-chip danger",
  refunded: "t2-chip",
};

/** أيقونةُ القناة — رموزُ منتقي الدفع، والخصمان بأيقونتيهما. */
const ICON: Record<PaymentMethod, string> = {
  wallet: "account_balance_wallet",
  cliq: "smartphone",
  card: "credit_card",
  cash: "payments",
  promo: "sell",
  share: "group",
};

export function PaymentsList({ payments }: { payments: Payment[] }) {
  return (
    <section>
      <h2 className="t2-section">دفعات هذه الرحلة</h2>
      <div className="t2-list">
        {payments.map((payment) =>
          payment.method === "promo" ? (
            <div key={payment.id} className="t2-m-pay promo">
              <span className="t2-m-pay-icon">
                <Icon name={ICON.promo} />
              </span>
              <span className="t2-m-pay-main">
                <span className="t2-m-pay-title">{PAYMENT_METHOD_LABEL.promo}</span>
              </span>
              <span className="t2-m-pay-amt">−{formatMoney(payment.amount, payment.currency)}</span>
            </div>
          ) : (
            <div key={payment.id} className="t2-m-pay">
              <span className="t2-m-pay-icon">
                <Icon name={ICON[payment.method]} />
              </span>
              <span className="t2-m-pay-main">
                <span className="t2-m-pay-title">{PAYMENT_METHOD_LABEL[payment.method]}</span>
                <span className="t2-m-pay-sub">{formatDateTime(payment.confirmed_at ?? payment.created_at)}</span>
                {payment.cliq_transfer_reference ? (
                  <span className="t2-m-pay-sub">
                    مرجع الحوالة: <b dir="ltr">{payment.cliq_transfer_reference}</b>
                  </span>
                ) : null}
                {payment.status === "disputed" && payment.dispute_reason ? (
                  <span className="t2-m-pay-dispute">نزاع: {payment.dispute_reason} — تفصل فيه الإدارة.</span>
                ) : null}
              </span>
              <span className="t2-m-pay-end">
                <span className="t2-m-pay-amt">{formatMoney(payment.amount, payment.currency)}</span>
                <span className={TONE[payment.status]}>{PAYMENT_STATUS_LABEL[payment.status]}</span>
              </span>
            </div>
          ),
        )}
      </div>
    </section>
  );
}
