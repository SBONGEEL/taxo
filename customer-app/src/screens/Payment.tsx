/** شاشة الدفع: القنوات المتاحة **حسب الدولة** (SPEC القسم 11.5/6).
 *
 * ثلاث قواعد من SPEC تنعكس هنا حرفياً:
 *
 * - **المحفظة خياراً أول وكليك ثانياً** (القسم 6.2) — والترتيب في `METHODS`.
 * - **القنوات تتبع مفاتيح الدولة**: الكاش وحده بلا مفتاح (إعدادُ ليبيا
 *   الافتراضي «كاش فقط»)، وما عداه يظهر إن كان مفتاحه مرفوعاً (القسم 4).
 * - **لا مبلغ يُرسل**: المبلغ هو المتبقي من `final_fare` تحسبه الخلفية
 *   (القسم 14). الشاشة تعرض `outstanding` وتختار قناةً لا غير.
 *
 * ومفتاحُ عدم التكرار يُولَّد **مرةً لكل محاولة قناة** ويُعاد استعماله في
 * إعادة المحاولة: ضغطتان لا تفتحان دفعتين (القسم 14).
 */

import { AnimatePresence, motion } from "framer-motion";
import { Banknote, CreditCard, Smartphone, Wallet } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getRide, getRidePayments, payRide } from "@/api/endpoints";
import type { PaymentMethod, Ride, RidePayments } from "@/api/types";
import { CardChoice } from "@/components/payment/CardChoice";
import { CliqPanel } from "@/components/payment/CliqPanel";
import { PaymentsList } from "@/components/payment/PaymentsList";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Screen } from "@/components/ui/Screen";
import { useCountryConfig } from "@/lib/config";
import { PAYMENT_METHOD_LABEL } from "@/lib/labels";
import { useRide } from "@/lib/ride";
import { useSession } from "@/lib/session";
import { cn, formatMoney, newIdempotencyKey } from "@/lib/utils";

/** الترتيب مقصود: المحفظة أولاً وكليك ثانياً (SPEC القسم 6.2). */
const METHODS: {
  method: PaymentMethod;
  icon: typeof Wallet;
  /** المفتاح الذي يحكم القناة — والكاش بلا مفتاح لأنه يعمل بلا إعداد. */
  feature?: string;
  hint: string;
}[] = [
  { method: "wallet", icon: Wallet, feature: "wallet_enabled", hint: "خصمٌ فوري من رصيدك" },
  { method: "cliq", icon: Smartphone, feature: "cliq_enabled", hint: "حوّل على alias الكبتن" },
  { method: "card", icon: CreditCard, feature: "card_enabled", hint: "بطاقة أو محفظة الهاتف" },
  { method: "cash", icon: Banknote, hint: "سلّم المبلغ للكبتن" },
];

export function PaymentScreen() {
  const { rideId = "" } = useParams();
  const navigate = useNavigate();
  const { user } = useSession();
  const { refresh } = useRide();
  const country = useCountryConfig(user?.country_code);

  const [ride, setRideRow] = useState<Ride | null>(null);
  const [state, setState] = useState<RidePayments | null>(null);
  const [busy, setBusy] = useState<PaymentMethod | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // البطاقة وحدها تحتاج خطوةً وسطى: أيُّ بطاقة، وهل تُحفظ (SPEC القسم 6.4)
  const [choosingCard, setChoosingCard] = useState(false);
  // مفتاحٌ لكل قناة يعيش ما دامت الشاشة: إعادة المحاولة بنفس المفتاح لا تدفع
  // مرتين، وقناةٌ أخرى تحتاج مفتاحها الخاص لأن الأولى قد تكون سجّلت دفعة
  const keys = useRef(new Map<PaymentMethod, string>());

  const load = useCallback(async () => {
    const [row, payments] = await Promise.all([
      getRide(rideId),
      getRidePayments(rideId),
    ]);
    setRideRow(row);
    setState(payments);
    return payments;
  }, [rideId]);

  useEffect(() => {
    load()
      .catch((caught: unknown) =>
        setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة حال الدفع"),
      )
      .finally(() => setLoading(false));
  }, [load]);

  const available = useMemo(
    () =>
      METHODS.filter(
        (entry) => !entry.feature || country?.features[entry.feature] === true,
      ),
    [country],
  );

  const settled = state !== null && Number(state.outstanding) <= 0;

  async function pay(
    method: PaymentMethod,
    extras: { save_card?: boolean; saved_card_id?: string } = {},
  ) {
    setBusy(method);
    setError(null);
    try {
      const key =
        keys.current.get(method) ?? newIdempotencyKey(`pay-${method}-${rideId.slice(0, 8)}`);
      keys.current.set(method, key);

      const result = await payRide(rideId, method, key, extras);
      setState(result);
      setChoosingCard(false);
      void refresh();

      // البطاقة تعود برابط صفحة المزود — والعودة منها تسأل عن الحال (6.4).
      // وبطاقةٌ محفوظة تُحسم عند المزود بلا صفحة، فلا رابط يعود ولا توجيه
      const redirect = result.card_order?.redirect_url;
      if (method === "card" && redirect) {
        sessionStorage.setItem("taxo.card_return_ride", rideId);
        window.location.assign(redirect);
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر تنفيذ الدفع");
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <Screen title="الدفع" back="/">
        <Spinner label="نقرأ حال الدفع…" />
      </Screen>
    );
  }

  return (
    <Screen title="الدفع" back="/">
      <div className="space-y-20">
        <div className="card p-16 text-center">
          <p className="text-14 text-muted">
            {settled ? "إجمالي الأجرة" : "المتبقي على هذه الرحلة"}
          </p>
          <p className="mt-4 text-30 font-bold text-ink">
            {formatMoney(
              settled ? (state?.final_fare ?? null) : (state?.outstanding ?? null),
              state?.currency,
            )}
          </p>
          {ride?.actual_distance_km ? (
            <p className="mt-4 text-12 text-muted">
              حُسبت على المسافة الفعلية المسجَّلة للرحلة
            </p>
          ) : null}
        </div>

        <ErrorNote message={error} />

        {settled ? (
          <SuccessNote message="اكتمل دفع هذه الرحلة — شكراً لك." />
        ) : (
          <AnimatePresence mode="wait">
            <motion.div
              key="methods"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-8"
            >
              <p className="label">اختر طريقة الدفع</p>
              {available.map(({ method, icon: Icon, hint }) => (
                <button
                  key={method}
                  type="button"
                  disabled={busy !== null}
                  onClick={() =>
                    method === "card" ? setChoosingCard(true) : pay(method)
                  }
                  className={cn(
                    "flex w-full items-center gap-12 rounded-12 border border-line bg-surface px-16 py-14 text-start transition",
                    "hover:bg-surface-2 disabled:opacity-60",
                  )}
                >
                  <Icon className="size-20 text-ink" />
                  <span className="flex-1">
                    <span className="block font-medium text-ink">
                      {PAYMENT_METHOD_LABEL[method]}
                    </span>
                    <span className="block text-12 text-muted">{hint}</span>
                  </span>
                  {busy === method ? (
                    <span className="text-14 text-muted">لحظة…</span>
                  ) : null}
                </button>
              ))}
            </motion.div>
          </AnimatePresence>
        )}

        {choosingCard && !settled ? (
          <CardChoice
            busy={busy === "card"}
            onPay={(extras) => pay("card", extras)}
            onCancel={() => setChoosingCard(false)}
          />
        ) : null}

        {/* صفحة دفع كليك داخل التطبيق (SPEC القسم 6.2 — المرحلة 9) */}
        {state?.cliq_charge ? (
          <CliqPanel charge={state.cliq_charge} onSubmitted={setState} />
        ) : null}

        {state && state.payments.length > 0 ? (
          <PaymentsList payments={state.payments} />
        ) : null}

        {settled ? (
          <Button size="lg" onClick={() => navigate(`/rides/${rideId}/rate`)}>
            قيّم رحلتك
          </Button>
        ) : null}
      </div>
    </Screen>
  );
}
