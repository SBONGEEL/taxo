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

import { ApiError } from "@/api/client";
import { Stagger, StaggerItem } from "@/components/ui/Motion";
import {
  buySubscription,
  buySubscriptionWithCard,
  getMySubscription,
  getSubscriptionHistory,
  updateDriver,
  payySubscriptionWithCliq,
} from "@/api/endpoints";
import type {
  DriverSubscription,
  MySubscription,
  SubscriptionDuration,
  SubscriptionPlan,
} from "@/api/types";
import { useNavigate } from "react-router-dom";

import { useCountryConfig, useFeature } from "@/lib/config";
import { useDriver } from "@/lib/driver";
import { useSession } from "@/lib/session";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits, cn,
  DISPLAY_LOCALE,
} from "@/lib/utils";
import { useGoBack } from "@/lib/back";

const DURATION_LABEL: Record<SubscriptionDuration, string> = {
  daily: "24 ساعة من لحظة الشراء",
  weekly: "7 أيام · الأوفر للدوام الجزئي",
  monthly: "30 يوماً · الأوفر للمتفرغ",
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
  const goBack = useGoBack();
  const { user } = useSession();
  // القناةُ تظهر إن كان مفتاحُها مرفوعاً في دولة الكبتن — والغيابُ معطَّل
  // دائماً (القسم 4). ولا اسمَ ميزةٍ مكتوبٌ هنا إلا هذا الواحد
  const navigate = useNavigate();
  const cardEnabled = useFeature(user?.country_code, "card_enabled");
  // **حسابُ كليك لسوقه** — و`null` تعني «لم يُضبط»، فالطريقةُ تُعطَّل بعلّتها
  const cliqAlias = useCountryConfig(user?.country_code)?.cliq_alias ?? null;
  // **المفتاحُ تفاؤليٌّ ويعود عند الرفض**: يجب أن يتحرك تحت الإصبع، ولا يجوز
  // أن يبقى مرفوعاً وقد رفضت الخلفيةُ — إذنٌ بمالٍ يُقرأ من الشاشة
  const { profile, refresh: refreshDriver } = useDriver();
  const [autoRenew, setAutoRenew] = useState(false);
  const [savingRenew, setSavingRenew] = useState(false);
  useEffect(() => {
    setAutoRenew(profile?.driver.auto_renew ?? false);
  }, [profile?.driver.auto_renew]);

  const toggleRenew = useCallback(async () => {
    const next = !autoRenew;
    setAutoRenew(next);
    setSavingRenew(true);
    try {
      await updateDriver({ auto_renew: next });
      await refreshDriver();
    } catch {
      setAutoRenew(!next);
    } finally {
      setSavingRenew(false);
    }
  }, [autoRenew, refreshDriver]);
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

  /** **يفتح مطالبةً يدويّةً ثمّ ينتقل إلى شاشة الدفع** — ولا اشتراكَ قبل
   *  تأكيد المشرف. */
  async function payWithCliq(planId: string) {
    setBuying(planId);
    setError(null);
    try {
      const claim = await payySubscriptionWithCliq(planId);
      navigate(`/subscription/cliq/${claim.id}`);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر فتح صفحة الدفع",
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
            onClick={() => goBack()}
            aria-label="رجوع"
            className="pressable text-18 text-muted"
          >
            →
          </button>
          <h1 className="text-20 font-bold text-ink">الاشتراك</h1>
        </div>

        {/* **مفتاحُ التجديد التلقائي** (البند ١٤): موضعُه هنا لا في «الإعدادات»
            — يُقرأ معناه بجوار حالة الاشتراك وثمنِه، لا بين أصواتٍ ومظهر.
            **والنصُّ يقول ما يقع بالضبط**: من أين يُخصم، ومتى، وأنه لن يقع
            بلا رصيد — فإذنٌ بمالٍ لا يُنتزع بجملةٍ عامة. */}
        <section className="mb-16 card p-15">
          <button
            type="button"
            role="switch"
            aria-checked={autoRenew}
            aria-label="التجديد التلقائي"
            disabled={savingRenew}
            onClick={() => void toggleRenew()}
            className="pressable flex w-full items-center gap-12 text-start"
          >
            <span className="flex-1">
              <span className="block text-13.5 font-semibold text-ink">
                التجديد التلقائي
              </span>
              <span className="block text-11 leading-snug text-muted">
                يُخصم ثمنُ خطتك من محفظتك قبل الانتهاء بيوم. لا يقع بلا رصيدٍ
                كافٍ، ونُخبرك إن تعذّر.
              </span>
            </span>
            <span
              className={cn(
                "relative block h-27 w-46 flex-none rounded-full transition-colors",
                autoRenew ? "bg-brand" : "bg-surface-2 border border-line",
              )}
            >
              <span
                className={cn(
                  "absolute top-3 block size-21 rounded-full bg-surface transition-all",
                  autoRenew ? "start-22" : "start-3",
                )}
              />
            </span>
          </button>
        </section>

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
                : `باقٍ ${digits(String(subscription.days_remaining))} يوماً`}
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
                {/* **اسمُ العرض وموعدُ انتهائه** — والاسمُ وحدَه بلا موعدٍ يجعل
                    الكبتنَ يؤجّل ظانّاً أن الخصمَ باقٍ (البند ٥٤). ولا يُرسم
                    شيءٌ لمن لا يستحقّ: الخلفيةُ لا ترسل له عرضاً أصلاً */}
                {/* **«استفدتَ منه من قبل» يُقال، والصمتُ لمن لم يستحقّ قطُّ**:
                    من رأى الخصمَ ثم اختفى يظنّ العرضَ انتهى أو التطبيقَ عطب،
                    ومن لم يُعرض عليه شيءٌ لا يُقال له عن عرضٍ لغيره (الفرع و). */}
                {!plan.offer_name && plan.exhausted_offer_name ? (
                  <span className="mt-4 block text-10.5 text-muted">
                    استفدتَ من «{plan.exhausted_offer_name}» من قبل
                  </span>
                ) : null}
                {plan.offer_name ? (
                  <span className="mt-4 block text-10.5 font-semibold text-ok">
                    {plan.offer_name}
                    {plan.offer_ends_at
                      ? ` — حتى ${digits(
                          new Date(plan.offer_ends_at).toLocaleDateString(DISPLAY_LOCALE,
                            { day: "numeric", month: "numeric" },
                          ),
                        )}`
                      : ""}
                  </span>
                ) : null}
              </span>
              {/* العملةُ بجانب الرقم كما في كل شاشةٍ مالية، لا سطراً تحته */}
              <span className="whitespace-nowrap text-17 font-bold text-ink">
                {/* **السعرُ المشطوب بجانب المخفَّض** — والمخفَّضُ محسوبٌ في
                    الخلفية، فلا طرحَ هنا: المالُ لا يُحسب في المتصفح (§14) */}
                {buying === plan.id ? (
                  "…"
                ) : plan.price_after_discount ? (
                  <>
                    <span className="me-6 text-12 font-medium text-muted line-through">
                      {digits(plan.price)}
                    </span>
                    {digits(plan.price_after_discount)}
                  </>
                ) : (
                  digits(plan.price)
                )}{" "}
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
                    {/* **ما وُفِّر فعلاً لا ما قرّره العرض** (شرطُ المالك):
                        `discount_amount` هو الفرقُ بين السعر المجمَّد وما دُفع،
                        فلو حصّل المشرفُ السعرَ كاملاً بالخطأ لم يُعرض خصمٌ
                        لم يَنَله. ولا طرحَ هنا — الرقمُ يصل محسوباً */}
                    {Number(item.discount_amount) > 0 ? (
                      <span className="mt-3 block text-10.5 font-semibold text-ok">
                        وفّرتَ {digits(item.discount_amount)}{" "}
                        {CURRENCY_LABEL[item.currency]}
                      </span>
                    ) : null}
                  </span>
                  <span className="text-end">
                    <span className="block text-13 font-bold text-ink">
                      {digits(item.amount_paid)}{" "}
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
            {/* **المبلغُ هنا هو ما يُخصم فعلاً، لا سعرُ الخطة** (قِيس على
                هاتفٍ حقيقي 2026-08-19): كانت الورقةُ تعرض ١٫٥٠٠ ويُخصم ١٫٢٧٥.
                والفرقُ لصالح الكبتن، لكنها **آخرُ شاشةٍ يقرؤها قبل أن يتحرك
                المال** — ورقمٌ فيها غيرُ المخصوم يجعلها تكذب في مبلغها.
                ولم يكشفه شيء: الفحصُ على سطح المكتب نادى الـAPI مباشرةً فلم
                يفتح الورقةَ أصلاً. */}
            <div className="mb-16 rounded-14 border border-line bg-surface-2 px-14 py-12">
              <div className="flex items-baseline justify-between">
                <span className="text-12.5 text-muted">المبلغ</span>
                <span className="text-17 font-bold text-ink">
                  {digits(
                    confirming.price_after_discount ?? confirming.price,
                  )}{" "}
                  <span className="text-11 font-medium text-muted">
                    {CURRENCY_LABEL[confirming.currency]}
                  </span>
                </span>
              </div>
              {/* والسعرُ الأصليُّ يبقى مرئياً مشطوباً: من رأى «١٫٥٠٠» في
                  البطاقة ثم «١٫٢٧٥» وحدَها هنا يظنّها خطةً أخرى */}
              {confirming.price_after_discount && confirming.offer_name ? (
                <div className="mt-8 flex items-baseline justify-between">
                  <span className="text-11 text-ok">{confirming.offer_name}</span>
                  <span className="text-11.5 text-muted line-through">
                    {digits(confirming.price)}{" "}
                    {CURRENCY_LABEL[confirming.currency]}
                  </span>
                </div>
              ) : null}
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
              {/* **ما لا عقدَ له يُعرض معطَّلاً بعلّته لا يُخفى** (قرارُ
                  المالك 2026-08-29): الإخفاءُ يجعل الكبتنَ يظنّ الطريقةَ
                  **غيرَ مدعومةٍ في التطبيق** فيسأل الدعمَ عن ميزةٍ يراها في
                  غيره؛ **والمعطَّلُ بعلّته يقول «قادمة» لا «غيرُ موجودة»**.
                  وهي قاعدةُ شاشة الإقلاع نفسُها: **يقول ما يعرفه.** */}
              <Button
                size="md"
                variant="secondary"
                disabled={!cardEnabled || buying !== null}
                onClick={() => {
                  const plan = confirming;
                  setConfirming(null);
                  void buyWithCard(plan.id);
                }}
              >
                الدفع ببطاقة
              </Button>
              {!cardEnabled ? (
                <p className="-mt-4 text-11 leading-note text-muted">
                  الدفع بالبطاقة غير متاح بعد — لم يُفعَّل عقد المزوّد.
                </p>
              ) : null}

              {/* **كليك اليدويّ** — يظهر حين يكون لسوقه حسابٌ مضبوط، ويُعطَّل
                  بعلّته حين لا يكون. **ولا يُدّعى أنه بوّابةٌ آلية**: الشاشةُ
                  التالية تقول إن التحصيل يدويّ. */}
              <Button
                size="md"
                variant="secondary"
                disabled={!cliqAlias || buying !== null}
                onClick={() => {
                  const plan = confirming;
                  setConfirming(null);
                  void payWithCliq(plan.id);
                }}
              >
                الدفع بكليك
              </Button>
              {!cliqAlias ? (
                <p className="-mt-4 text-11 leading-note text-muted">
                  الدفع بكليك غير متاح في سوقك — لم يُضبط حساب الاستقبال.
                </p>
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

    </div>
  );
}

function formatRange(from: string, to: string): string {
  const format = (value: string) =>
    new Date(value).toLocaleDateString(DISPLAY_LOCALE, {
      day: "numeric",
      month: "long",
    });
  return `${format(from)} – ${format(to)}`;
}
