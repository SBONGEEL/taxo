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
 *
 * **بلغة TAXO 2.0** «C29» (`design/t2-new/captain/C29*.dc.html`): شاشةُ حالٍ بدائرةٍ بنبرة الجواب (دائرةُ «C08» مكبَّرة)،
 * والمبلغُ كما يصل بخطّ الأرقام، وزرٌّ واحدٌ في ذيلٍ مثبَّت (C10). **والمنطقُ حرفاً.**
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getCardOrder } from "@/api/endpoints";
import type { CardOrder } from "@/api/types";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "@/screens/t2/account.css";

const SETTLED = {
  paid: {
    icon: "check",
    tone: "ok",
    title: "تم الدفع",
    body: "فُعّل اشتراكك — تجد تفاصيله في شاشة الاشتراك.",
  },
  failed: {
    icon: "close",
    tone: "danger",
    title: "لم يتم الدفع",
    body: "لم يُخصم من بطاقتك شيء. جرّب مرة أخرى أو ادفع من محفظتك.",
  },
  cancelled: {
    icon: "close",
    tone: "",
    title: "أُلغيت العملية",
    body: "لم يُخصم من بطاقتك شيء.",
  },
  refunded: {
    icon: "undo",
    tone: "",
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
  // **غيرُ المحسوم بالكهرمان وساعته** — لا أخضرَ يُفرح ولا أحمرَ يُقلق
  const tone = settled ? settled.tone : "warn";

  return (
    <div className="t2 t2-ax t2-cret">
      <div className={loading ? "t2-ax-scroll" : "t2-ax-scroll has-foot"}>
        {loading ? (
          <div className="t2-ax-center">
            <span className="t2-ax-spin" role="status" aria-label="جارٍ التحميل" />
          </div>
        ) : (
          <div className="t2-cret-body">
            <span className={tone ? `t2-cret-badge ${tone}` : "t2-cret-badge"} aria-hidden="true">
              <Icon name={settled?.icon ?? "schedule"} />
            </span>
            <h1 className="t2-cret-title">
              {settled?.title ?? "لم يُحسم بعد"}
            </h1>
            <p className="t2-cret-text">
              {settled?.body ??
                "لم يصل جواب المزود بعد. لا تدفع مرة أخرى — أعد الاستعلام بعد لحظات."}
            </p>

            {order ? (
              <div className="t2-ax-money t2-cret-amount">
                <span className="t2-ax-money-num" dir="ltr">
                  {digits(order.amount)}
                </span>
                <span className="t2-ax-money-cur">{CURRENCY_LABEL[order.currency]}</span>
              </div>
            ) : null}

            {error ? (
              <p className="t2-note danger" role="alert">
                <Icon name="error" />
                {error}
              </p>
            ) : null}
          </div>
        )}
      </div>

      {loading ? null : (
        <div className="t2-ax-foot">
          {settled ? (
            <button
              type="button"
              className="t2-ax-cta"
              onClick={() => navigate("/subscription", { replace: true })}
            >
              إلى الاشتراك
            </button>
          ) : (
            <button type="button" className="t2-ax-cta" onClick={() => void check()}>
              أعد الاستعلام
            </button>
          )}
        </div>
      )}
    </div>
  );
}
