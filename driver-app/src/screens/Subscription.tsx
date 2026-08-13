/** الاشتراك — SPEC القسم 12/5 و8، وشكلُه من `DESIGN.md` §5.3.
 *
 * **أربع حالاتٍ لا حالتان**، وهي ما يقرأه الكبتن قبل أن يقرأ أي شيء آخر:
 *
 * | الحال | اللون | ماذا يعني |
 * |---|---|---|
 * | ساري | `--ok` | يستقبل الطلبات |
 * | ينتهي قريباً (< ٢٤ ساعة) | `--warn` | ما زال يستقبل، ويوشك ألّا يفعل |
 * | منتهٍ | `--dng` | **خارج التوزيع الآن** |
 * | لا اشتراك بعد | `--mut` | لم يبدأ أصلاً |
 *
 * والفرقُ بين «منتهٍ» و«لا اشتراك» ليس تجميلاً: الأول يعرف ما فقده والثاني
 * لا يعرف أن عليه شيئاً. والفرقُ بين «ساري» و«ينتهي قريباً» هو الفرقُ بين
 * كبتنٍ يعمل غداً وكبتنٍ يكتشف صباحاً أنه خارج التوزيع.
 *
 * **والاشتراك سؤالٌ عن الساعة لا عن عمود**: `is_active` من الخلفية يقرأ
 * `starts_at <= now < expires_at` لا حالةَ الصف وحدها — والمهمةُ الدورية
 * تعلّم المنتهي كل خمس دقائق (`subscriptions.coverage_condition`). و
 * `coverage_until` **أقصى** انتهاء لا الأحدث: من جدّد مبكراً له صفّان
 * متتاليان، وعدُّ أيام أولهما يقول له إن اشتراكه ينتهي غداً وهو مغطّى شهراً.
 *
 * **قناتان من التطبيق: المحفظة والبطاقة.** والكاش وكليك **تسجّلهما الإدارة
 * بعد قبض المال** ولا تُشترى من التطبيق أصلاً (القسم 8) — فزرٌّ لهما هنا يعد
 * بما لا يقع.
 *
 * والبطاقةُ تفتح صفحة المزود المستضافة ثم تعود إلى `/payments/card/return`
 * **على هذا التطبيق**: صار لكل تطبيق عنوانُ عودةٍ تختاره الخلفية من دور
 * الدافع، وكان العنوانُ واحداً يشير إلى تطبيق الراكب فتعيد الصفحةُ الكبتنَ
 * إلى تطبيقٍ ليس تطبيقه.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { Stagger, StaggerItem } from "@/components/ui/Motion";
import {
  buySubscription,
  buySubscriptionWithCard,
  getMySubscription,
  getSubscriptionHistory,
} from "@/api/endpoints";
import type {
  DriverSubscription,
  MySubscription,
  SubscriptionDuration,
  SubscriptionPlan,
} from "@/api/types";
import { BottomNav } from "@/components/BottomNav";
import { useFeature } from "@/lib/config";
import { useSession } from "@/lib/session";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { arabicDigits, cn } from "@/lib/utils";

const DURATION_LABEL: Record<SubscriptionDuration, string> = {
  daily: "٢٤ ساعة من لحظة الشراء",
  weekly: "٧ أيام · الأوفر للدوام الجزئي",
  monthly: "٣٠ يوماً · الأوفر للمتفرغ",
};

type State = "active" | "expiring" | "expired" | "none";

/** الحالُ الأربع من جوابٍ واحد — لا حقلَ لها في الخلفية فتُشتق هنا. */
function stateOf(subscription: MySubscription | null): State {
  if (!subscription) return "none";
  if (subscription.is_active) {
    // «ينتهي قريباً» هي نفسها نافذة تنبيه القسم 8: أقل من يومٍ واحد
    return subscription.days_remaining <= 1 ? "expiring" : "active";
  }
  // فرَّقَ بين من انتهى اشتراكه ومن لم يشترِ قط: `coverage_until` يبقى
  // محفوظاً للأول
  return subscription.coverage_until ? "expired" : "none";
}

const COPY: Record<
  State,
  { title: string; body: string; tone: string; dot: string }
> = {
  active: {
    title: "اشتراكك ساري",
    body: "لا تجديد تلقائي — جدّد قبل انتهائه.",
    tone: "border-line",
    dot: "bg-ok",
  },
  expiring: {
    title: "ينتهي اشتراكك قريباً",
    body: "جدّد الآن لتبقى في التوزيع.",
    tone: "border-warn",
    dot: "bg-warn",
  },
  expired: {
    title: "انتهى اشتراكك",
    body: "أنت خارج التوزيع حتى التجديد.",
    tone: "border-danger",
    dot: "bg-danger",
  },
  none: {
    title: "لا اشتراك بعد",
    body: "اشترك لتبدأ استقبال الطلبات.",
    tone: "border-line",
    dot: "bg-muted",
  },
};

export function SubscriptionScreen() {
  const navigate = useNavigate();
  const { user } = useSession();
  // القناةُ تظهر إن كان مفتاحُها مرفوعاً في دولة الكبتن — والغيابُ معطَّل
  // دائماً (القسم 4). ولا اسمَ ميزةٍ مكتوبٌ هنا إلا هذا الواحد
  const cardEnabled = useFeature(user?.country_code, "card_enabled");
  const [subscription, setSubscription] = useState<MySubscription | null>(null);
  const [history, setHistory] = useState<DriverSubscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [buying, setBuying] = useState<string | null>(null);
  // خطوةُ تأكيدٍ قبل الخصم: ضغطةٌ واحدة تُخرج ثمانين ديناراً من محفظته،
  // و«خصمتم مني بالخطأ» تذكرةُ دعمٍ لا تُغلق بغير قيدٍ مضاد
  const [confirming, setConfirming] = useState<SubscriptionPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [mine, past] = await Promise.all([
      getMySubscription(),
      getSubscriptionHistory().catch(() => []),
    ]);
    setSubscription(mine);
    setHistory(past);
  }, []);

  useEffect(() => {
    load()
      .catch((caught) =>
        setError(
          caught instanceof ApiError ? caught.message : "تعذّر قراءة الاشتراك",
        ),
      )
      .finally(() => setLoading(false));
  }, [load]);

  async function buy(planId: string) {
    setBuying(planId);
    setError(null);
    setDone(null);
    try {
      // مفتاحُ عدم التكرار من العميل (القسم 14): ضغطتان لا تشتريان شهرين
      await buySubscription(planId, `sub-${planId}-${Date.now()}`);
      await load();
      setDone("تم التجديد — اشتراكك ساري ✓");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر إتمام الشراء",
      );
    } finally {
      setBuying(null);
    }
  }

  async function buyWithCard(planId: string) {
    setBuying(planId);
    setError(null);
    setDone(null);
    try {
      const order = await buySubscriptionWithCard(planId);
      if (!order.redirect_url) {
        // لا اشتراكَ يُنشأ قبل جواب المزود، فغيابُ الرابط ليس نصفَ شراء
        setError("تعذّر فتح صفحة الدفع — جرّب مرة أخرى أو ادفع من محفظتك.");
        return;
      }
      // مغادرةٌ إلى صفحة المزود: الحسمُ يقع هناك، والعودةُ إلى
      // `/payments/card/return` على هذا التطبيق
      window.location.assign(order.redirect_url);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر فتح صفحة الدفع",
      );
    } finally {
      setBuying(null);
    }
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center bg-bg">
        <Spinner />
      </div>
    );
  }

  const state = stateOf(subscription);
  const copy = COPY[state];

  return (
    <div className="relative h-full bg-bg">
      <div className="scr h-full px-16 pb-nav pt-safe">
        <div className="mb-16 flex items-center gap-10">
          <button
            type="button"
            onClick={() => navigate(-1)}
            aria-label="رجوع"
            className="pressable text-18 text-muted"
          >
            →
          </button>
          <h1 className="text-20 font-bold text-ink">الاشتراك</h1>
        </div>

        <section
          className={cn("mb-16 rounded-18 border bg-surface p-17", copy.tone)}
        >
          <div className="mb-6 flex items-center gap-10">
            <span className={cn("block size-9 rounded-full", copy.dot)} />
            <span className="text-14 font-bold text-ink">{copy.title}</span>
          </div>
          <p className="text-12.5 leading-snug text-muted">
            {subscription?.current
              ? `${subscription.current.plan_name} · `
              : ""}
            {copy.body}
          </p>
          {subscription?.is_active ? (
            <p className="mt-6 text-12.5 font-semibold text-ink">
              {subscription.days_remaining <= 1
                ? "ينتهي خلال أقل من يوم"
                : `باقٍ ${arabicDigits(String(subscription.days_remaining))} يوماً`}
            </p>
          ) : null}
        </section>

        <ErrorNote message={error} />
        {done ? (
          <p className="mb-12 text-12.5 font-semibold text-ok">{done}</p>
        ) : null}

        <h2 className="mb-10 mt-16 text-13 font-bold text-muted">
          الخطط المتاحة
        </h2>
        <div className="flex flex-col gap-10">
          {(subscription?.plans ?? []).map((plan) => (
            <button
              key={plan.id}
              type="button"
              disabled={buying !== null}
              onClick={() => setConfirming(plan)}
              className={cn(
                // ولا خطةَ «موصى بها» بإطار: الإطارُ الأبيض في هذا التطبيق
                // معناه **مختار**، وإبرازُ الأسبوعي كان افتراضاً مكتوباً في
                // الكود عن أسعارٍ تديرها الإدارة وقد تنقلب غداً
                "flex items-center gap-12 rounded-16 border bg-surface p-15 text-start",
                subscription?.current?.plan_name === plan.name
                  ? "border-ink"
                  : "border-line",
                buying !== null && "opacity-60",
              )}
            >
              <span className="flex-1">
                <span className="block text-14 font-bold text-ink">
                  {plan.name}
                  {/* الإطارُ وحده غامض: كلمةٌ تقول لماذا هذه الخطة مؤطَّرة */}
                  {subscription?.current?.plan_name === plan.name ? (
                    <span className="ms-8 text-10.5 font-semibold text-muted">
                      خطتك الحالية
                    </span>
                  ) : null}
                </span>
                <span className="block text-11.5 text-muted">
                  {DURATION_LABEL[plan.duration_type]}
                </span>
              </span>
              {/* العملةُ بجانب الرقم كما في كل شاشةٍ مالية، لا سطراً تحته */}
              <span className="whitespace-nowrap text-17 font-bold text-ink">
                {buying === plan.id ? "…" : arabicDigits(plan.price)}{" "}
                <span className="text-11 font-medium text-muted">
                  {CURRENCY_LABEL[plan.currency]}
                </span>
              </span>
            </button>
          ))}
        </div>

        <p className="mt-14 text-11.5 leading-note text-muted">
          {cardEnabled
            ? "الشراء هنا من محفظتك أو ببطاقتك. والكاش وكليك تسجّلهما الإدارة بعد قبض المال — ليست من التطبيق."
            : "الشراء هنا من رصيد محفظتك. والكاش وكليك تسجّلهما الإدارة بعد قبض المال — ليست من التطبيق."}
        </p>

        {history.length > 0 ? (
          <>
            <h2 className="mb-10 mt-18 text-13 font-bold text-muted">
              اشتراكات سابقة
            </h2>
            <Stagger className="flex flex-col gap-8">
              {history.map((item) => (
                <StaggerItem
                  key={item.id}
                  className="flex items-center gap-10 rounded-14 border border-line bg-surface px-14 py-12"
                >
                  <span className="flex-1">
                    <span className="block text-12.5 font-semibold text-ink">
                      {item.plan_name}
                    </span>
                    <span className="block text-11 text-muted">
                      {formatRange(item.starts_at, item.expires_at)}
                    </span>
                  </span>
                  <span className="text-end">
                    <span className="block text-13 font-bold text-ink">
                      {arabicDigits(item.amount_paid)}{" "}
                      {CURRENCY_LABEL[item.currency]}
                    </span>
                    <span
                      className={cn(
                        "block text-10",
                        item.status === "active" ? "text-ok" : "text-muted",
                      )}
                    >
                      {item.status === "active" ? "ساري" : "منتهٍ"}
                    </span>
                  </span>
                </StaggerItem>
              ))}
            </Stagger>
          </>
        ) : null}
      </div>

      {confirming ? (
        <div
          className="absolute inset-0 z-50 animate-fadein-fast bg-dim"
          onClick={() => setConfirming(null)}
        >
          <div
            className="absolute inset-x-0 bottom-0 animate-slideup rounded-t-24 border-t border-line bg-surface px-18 pb-24 pt-20"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 className="mb-4 text-16 font-bold text-ink">
              تأكيد شراء {confirming.name}
            </h2>
            <p className="mb-16 text-12 leading-note text-muted">
              يُخصم المبلغ من رصيد محفظتك فوراً، ويبدأ الاشتراك من انتهاء تغطيتك
              الحالية إن كانت سارية.
            </p>
            <div className="mb-16 flex items-baseline justify-between rounded-14 border border-line bg-surface-2 px-14 py-12">
              <span className="text-12.5 text-muted">المبلغ</span>
              <span className="text-17 font-bold text-ink">
                {arabicDigits(confirming.price)}{" "}
                <span className="text-11 font-medium text-muted">
                  {CURRENCY_LABEL[confirming.currency]}
                </span>
              </span>
            </div>
            <div className="flex flex-col gap-9">
              <Button
                size="md"
                loading={buying !== null}
                onClick={() => {
                  const plan = confirming;
                  setConfirming(null);
                  void buy(plan.id);
                }}
              >
                خصم من المحفظة
              </Button>
              {cardEnabled ? (
                <Button
                  size="md"
                  variant="secondary"
                  disabled={buying !== null}
                  onClick={() => {
                    const plan = confirming;
                    setConfirming(null);
                    void buyWithCard(plan.id);
                  }}
                >
                  الدفع ببطاقة
                </Button>
              ) : null}
              <button
                type="button"
                onClick={() => setConfirming(null)}
                className="pressable w-full py-8 text-center text-12.5 font-semibold text-muted"
              >
                تراجع
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <BottomNav />
    </div>
  );
}

function formatRange(from: string, to: string): string {
  const format = (value: string) =>
    new Date(value).toLocaleDateString("ar-EG", {
      day: "numeric",
      month: "long",
    });
  return `${format(from)} – ${format(to)}`;
}
