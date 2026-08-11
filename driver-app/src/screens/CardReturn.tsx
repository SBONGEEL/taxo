/** العودة من صفحة الدفع المستضافة — SPEC القسم 6.4.
 *
 * صارت للكبتن عنواناً خاصاً به: `settings.card_return_url_driver` يشير إلى
 * هذا المسار على 5174، والخلفية تختاره من **دور الدافع**. وقبله كان العنوان
 * واحداً يشير إلى تطبيق الراكب، فصفحةُ المزود تعيد الكبتن إلى تطبيقٍ ليس
 * تطبيقه — ولذلك كانت قناةُ البطاقة معطّلةً عنده كلُّها.
 *
 * **والاستعلامُ شريكُ الإشعار لا احتياطُه**: أيُّهما وصل أولاً سوّى، والآخر
 * يجد الطلب محسوماً فلا يقيّد شيئاً. فهذه الشاشة تسأل عن الحال ولا تفترض.
 *
 * **ولا تخمينَ على غير محسوم**: طلبٌ ما زال `created`/`pending` يبقى معلّقاً
 * — لا نجاحاً يُفرح ولا فشلاً يُقلق — وتُعاد المحاولة بضغطة.
 */

import { CheckCircle2, Clock, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getCardOrder } from "@/api/endpoints";
import type { CardOrder } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { arabicDigits } from "@/lib/utils";

const SETTLED = {
  paid: {
    icon: CheckCircle2,
    tone: "text-ok",
    title: "تم الدفع",
    body: "فُعّل اشتراكك — تجد تفاصيله في شاشة الاشتراك.",
  },
  failed: {
    icon: XCircle,
    tone: "text-danger",
    title: "لم يتم الدفع",
    body: "لم يُخصم من بطاقتك شيء. جرّب مرة أخرى أو ادفع من محفظتك.",
  },
  cancelled: {
    icon: XCircle,
    tone: "text-muted",
    title: "أُلغيت العملية",
    body: "لم يُخصم من بطاقتك شيء.",
  },
  refunded: {
    icon: CheckCircle2,
    tone: "text-muted",
    title: "استُرجع المبلغ",
    body: "أعادت الإدارة المبلغ إلى بطاقتك.",
  },
} as const;

export function CardReturnScreen() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  // بعضُ المزودين يعيدون المفتاح بحروفٍ صغيرة — والاثنان مقبولان
  const cartId = params.get("cart_id") ?? params.get("cartid") ?? "";

  const [order, setOrder] = useState<CardOrder | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const check = useCallback(async () => {
    if (!cartId) {
      setError("لا معرّف عملية في الرابط — افتح شاشة الاشتراك مجدداً.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setOrder(await getCardOrder(cartId));
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "تعذّر الاستعلام عن حال الدفع",
      );
    } finally {
      setLoading(false);
    }
  }, [cartId]);

  useEffect(() => {
    void check();
  }, [check]);

  const settled = order ? SETTLED[order.status as keyof typeof SETTLED] : null;
  const Icon = settled?.icon ?? Clock;

  return (
    <div className="flex h-full flex-col justify-center bg-bg px-26 pb-safe pt-safe text-center">
      {loading ? (
        <Spinner className="mx-auto" />
      ) : (
        <>
          <Icon
            size={54}
            className={`mx-auto mb-16 ${settled?.tone ?? "text-warn"}`}
          />
          <h1 className="text-19 font-bold text-ink">
            {settled?.title ?? "لم يُحسم بعد"}
          </h1>
          <p className="mt-8 text-12.5 leading-note text-muted">
            {settled?.body ??
              "لم يصل جواب المزود بعد. لا تدفع مرة أخرى — أعد الاستعلام بعد لحظات."}
          </p>

          {order ? (
            <p className="mt-14 text-15 font-bold text-ink">
              {arabicDigits(order.amount)} {CURRENCY_LABEL[order.currency]}
            </p>
          ) : null}

          <div className="mt-16">
            <ErrorNote message={error} />
          </div>

          {settled ? (
            <Button
              className="mt-16"
              onClick={() => navigate("/subscription", { replace: true })}
            >
              إلى الاشتراك
            </Button>
          ) : (
            <Button className="mt-16" onClick={() => void check()}>
              أعد الاستعلام
            </Button>
          )}
        </>
      )}
    </div>
  );
}
