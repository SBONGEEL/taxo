/** الإعدادات per-country — SPEC القسم 13/6، و`DESIGN.md` §3.2.
 *
 * كلُّ ما في هذه الصفحة **يسري على التطبيقين فور الحفظ** بلا نشر: مفتاحٌ
 * يُطفأ هنا يختفي أثرُه من شاشة الدفع، ونسبةٌ تُغيَّر هنا تُجمَّد على الرحلة
 * القادمة لا على الماضية.
 *
 * **وثلاث قواعد تظهر في الشاشة لأنها تحكم ما يقع:**
 *
 * 1. **`otp_verification_enabled` حارسٌ لا ميزة** — الاستثناء الوحيد لقاعدة
 *    «غياب الصف = معطّل». إطفاؤه إجراءُ طوارئ يفتح باباً، فيطلب **سبباً
 *    مكتوباً** يدخل سجل التدقيق، ويحمل تحذيره في وجهه. ولا يعطّل استعادة
 *    كلمة المرور أبداً.
 * 2. **لا مفتاحَ للعمولة بين المفاتيح**: مصدرها الوحيد `commission_settings`
 *    حيث تسكن نسبتُها ونطاقُها معاً — مفتاحٌ ثانٍ يعني حالتين ماليتين قابلتين
 *    للاختلاف.
 * 3. **صفرُ حدِّ التحويل يعني «لم يُضبط»** فيمنع التحويل، لا «حدٌّ مقداره
 *    صفر». والشاشة تقولها بدل أن يقرأ المشرف صفراً ويظنه سخاءً.
 *
 * ولا تُحسب هنا نسبةٌ ولا مبلغ: الحقولُ تُرسل كما تُكتب، والخلفيةُ تتحقق.
 *
 * **و`key={row.country_code}` على النماذج الثلاثة ليس تفصيلاً في React بل حارسٌ
 * ماليّ**: كلُّ نموذجٍ يبدأ حالتَه من `row`، وReact لا يعيد قراءة قيمةِ
 * `useState` الأولى عند تغيّر الـprop — فمبدّلُ الدولة كان يُبقي أرقامَ السوق
 * السابق في الحقول (النسبة، وحدود التحويل، ومبالغ البقشيش) بينما تحت الحقل
 * سطرٌ يقول القيمةَ الصحيحة. ومن ضغط «حفظ» بعده يكتب **أرقام الأردن في ليبيا**.
 * والمفتاحُ يُعيد تركيبَ النموذج فتُقرأ القيمُ من جديد. كشفه فحصٌ بصريٌّ في
 * متصفح: `tsc` لا يرى حالةً قديمة.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  listCommission,
  listFeatureFlags,
  getReferralSettings,
  listPaymentSettings,
  listWalletSettings,
  setFeatureFlag,
  updateCommission,
  updatePaymentSettings,
  updateReferralSettings,
  updateWalletSettings,
} from "@/api/endpoints";
import type {
  CommissionSetting,
  CountryFeatureFlags,
  FeatureKey,
  PaymentSetting,
  ReferralSetting,
  WalletSetting,
} from "@/api/types";
import { Shell } from "@/components/Shell";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { currencyLabel, currencyOf, money } from "@/lib/format";
import { useSession } from "@/lib/session";
import { arabicDigits, cn } from "@/lib/utils";

const FLAG_LABEL: Record<FeatureKey, { title: string; hint: string }> = {
  cliq_enabled: {
    title: "الدفع بكليك",
    hint: "يظهر كليك خياراً في شاشة دفع الراكب، ويُفعّل شحن المحفظة به.",
  },
  card_enabled: {
    title: "الدفع بالبطاقة",
    hint: "صفحةُ دفعٍ مستضافة عبر Telr — تحتاج عقداً مفعّلاً في صفحة العقود.",
  },
  wallet_enabled: {
    title: "المحفظة",
    hint: "الشحنُ والدفعُ منها. وإطفاؤه لا يخفي رصيداً قائماً عن صاحبه.",
  },
  wallet_transfer_enabled: {
    title: "التحويل بين الركّاب",
    hint: "يحتاج حدّي تحويلٍ غير صفريّين أدناه، وإلا رُفض التحويل.",
  },
  otp_verification_enabled: {
    title: "التحقق من الرقم",
    hint: "حارسٌ لا ميزة — إطفاؤه للطوارئ فقط، ويسمح بحساباتٍ برقمٍ غير مُثبت.",
  },
  multi_stop_enabled: {
    title: "تعدد الوجهات",
    hint: "يظهر زرُّ «إضافة محطة» في شاشة الطلب — حتى ثلاث وجهات. واضبط رسوم المحطات في «التسعيرة» أولاً، فصفرُها يعني محطاتٍ بلا كلفة. والإطفاءُ يمنع الطلبات الجديدة ولا يقطع رحلةً جارية.",
  },
  tips_enabled: {
    title: "البقشيش",
    hint: "أزرارُ شكرٍ في شاشة تقييم الراكب — يُخصم من محفظته ويصل الكبتنَ كاملاً بلا عمولة. ويشترط المحفظةَ مفعّلةً (قناتُه الوحيدة) ومبالغَ مضبوطةً أدناه؛ وصفرُ السقف يُخفي الميزةَ ولو كان المفتاح مشتعلاً.",
  },
  whatsapp_otp_enabled: {
    title: "التحقق عبر واتساب",
    hint: "يُرسل رمزَ التحقق في واتساب بدل الرسائل القصيرة — ويشترط عقد WhatsApp مفعّلاً في صفحة العقود. ولا تُشعَل قبل اعتماد قالب المصادقة بلغة هذا السوق: قالبٌ غير معتمد يجعل كلَّ تسجيلٍ يرتدّ. وعند فشل الإرسال يُعرض على المستخدم الارتداد إلى الرسائل.",
  },
  promo_codes_enabled: {
    title: "رموز الخصم",
    hint: "تظهر ورقةُ «عندي كوبون» في شاشة تأكيد الرحلة. والخصمُ **تتحمّله الشركة**: يُسجَّل دفعةً بقناة «كوبون» فلا يَنقص أجرةَ الكبتن ولا عمولته. وأنشئ الرموزَ في «العروض والحملات» — مفتاحٌ مشتعلٌ بلا رموز يفتح حقلاً لا يُقبل فيه شيء.",
  },
  driver_referrals_enabled: {
    title: "حافز إحالة السائقات",
    hint: "مكافأةٌ لمن يُحيل سائقةً تُدفع في محفظته بعد اعتماد حسابها وإكمالها عددَ الرحلات المطلوب — واضبط المبلغَ أدناه، فصفرُه يعني «لم يُحدَّد» فلا تُدفع مكافأة ولا يُوعَد بها أحد. والرمزُ يظهر للكبتن على كل حال فالإحالاتُ تُسجَّل ولو كان المفتاح مطفأً.",
  },
  scheduled_rides_enabled: {
    title: "الرحلات المجدولة",
    hint: "يظهر «حدّد موعداً» في ورقة تأكيد الرحلة، ويبدأ البحثُ عن كبتنٍ قبل الموعد بعشر دقائق. والسعرُ يُحسب عند التنفيذ لا عند الحجز. وإطفاؤه يمنع حجوزاً جديدة **ويُنفّذ القائمةَ منها**: موعدٌ رتّب صاحبُه صباحَه عليه لا يُلغى بمفتاح.",
  },
  women_service_enabled: {
    title: "خدمة التوصيل النسائي",
    hint: "لا تُشعَل قبل مراجعة أجناس الكباتن المعتمدين — خدمةٌ بلا سائقاتٍ يمكن ترشيحُهنّ تُقرأ ميزةً معطوبة. اعرض «من لم يُثبَّت جنسُه» في صفحة السائقين.",
  },
};

/** المفاتيحُ التي يملك المشرف إطفاءها من هنا، وحارسُها آخرُ القائمة عمداً. */
const FLAGS: FeatureKey[] = [
  "cliq_enabled",
  "card_enabled",
  "wallet_enabled",
  "wallet_transfer_enabled",
  "multi_stop_enabled",
  "women_service_enabled",
  "whatsapp_otp_enabled",
  "tips_enabled",
  "promo_codes_enabled",
  "driver_referrals_enabled",
  "scheduled_rides_enabled",
  "otp_verification_enabled",
];

export function SettingsScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();

  const [flags, setFlags] = useState<CountryFeatureFlags[] | null>(null);
  const [commission, setCommission] = useState<CommissionSetting[]>([]);
  const [wallet, setWallet] = useState<WalletSetting[]>([]);
  const [payment, setPayment] = useState<PaymentSetting[]>([]);
  const [referral, setReferral] = useState<ReferralSetting | null>(null);
  const [guard, setGuard] = useState<{ key: FeatureKey } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [f, c, w, p, r] = await Promise.all([
      listFeatureFlags(),
      listCommission(),
      listWalletSettings(),
      listPaymentSettings(),
      // **منفذُ الإحالة لدولةٍ واحدة** لا قائمة، فيدخل السوقُ في التبعيات —
      // وبغيره يبقى معروضاً إعدادُ السوق الأول بعد تبديل الرأس
      getReferralSettings(country),
    ]);
    setFlags(f);
    setCommission(c);
    setWallet(w);
    setPayment(p);
    setReferral(r);
  }, [country]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الإعدادات",
      ),
    );
  }, [load]);

  const current = flags?.find((entry) => entry.country_code === country);
  const commissionRow = commission.find((row) => row.country_code === country);
  const walletRow = wallet.find((row) => row.country_code === country);
  const paymentRow = payment.find((row) => row.country_code === country);

  async function flip(key: FeatureKey, enabled: boolean, reason?: string) {
    setError(null);
    setDone(null);
    try {
      await setFeatureFlag({
        country_code: country,
        feature_key: key,
        enabled,
        reason,
      });
      await load();
      setDone("حُفظ الإعداد — يسري على التطبيقين الآن");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    }
  }

  return (
    <Shell
      title="الإعدادات العامة"
      subtitle="إعداداتٌ تسري على تطبيقَي الراكب والسائق فور الحفظ"
    >
      <ErrorNote message={error} />
      <SuccessNote message={done} />

      {flags === null ? (
        <Spinner className="mx-auto" />
      ) : (
        <div className="mt-12 grid gap-14 lg:grid-cols-2">
          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-12 text-14 font-bold text-ink">مفاتيح الميزات</h2>
            <ul className="flex flex-col gap-12">
              {FLAGS.map((key) => {
                const on = current?.flags[key] === true;
                const isGuard = key === "otp_verification_enabled";
                return (
                  <li key={key} className="flex items-start gap-12">
                    <span className="flex-1">
                      <span className="block text-13 font-semibold text-ink">
                        {FLAG_LABEL[key].title}
                        {isGuard ? (
                          <span className="ms-8 text-10.5 font-bold text-warn">
                            حارس
                          </span>
                        ) : null}
                      </span>
                      <span className="block text-11 leading-snug text-muted">
                        {FLAG_LABEL[key].hint}
                      </span>
                    </span>
                    <button
                      type="button"
                      disabled={!isAdmin}
                      onClick={() => {
                        // إطفاءُ الحارس وحده يطلب سبباً — والخلفية ترفض بدونه
                        if (isGuard && on) setGuard({ key });
                        else void flip(key, !on);
                      }}
                      className={cn(
                        "relative block h-27 w-46 flex-none rounded-full transition-colors disabled:opacity-60",
                        on ? "bg-ok" : "bg-line",
                      )}
                      aria-label={FLAG_LABEL[key].title}
                    >
                      <span
                        className={cn(
                          "absolute top-3 block size-21 rounded-full bg-surface transition-all",
                          on ? "start-22" : "start-3",
                        )}
                      />
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>

          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">عمولة المنصة</h2>
            <p className="mb-12 text-11 leading-snug text-muted">
              لا مفتاحَ لها بين المفاتيح: المصدرُ واحد — النسبةُ ونطاقُها هنا،
              فلا تختلف حالتان على أمرٍ مالي. والنسبةُ تُجمَّد على الرحلة عند
              إنشائها ولا يُعاد حسابُها بأثرٍ رجعي.
            </p>
            {commissionRow ? (
              <CommissionForm
                key={commissionRow.country_code}
                row={commissionRow}
                disabled={!isAdmin}
                onSaved={(message) => {
                  setDone(message);
                  void load();
                }}
                onError={setError}
              />
            ) : (
              <p className="text-12.5 text-muted">
                لا إعداد عمولة لهذه الدولة.
              </p>
            )}
          </section>

          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">
              حدود المحفظة والسحب
            </h2>
            <p className="mb-12 text-11 leading-snug text-muted">
              الصفرُ هنا يعني «لم يُضبط» فيمنع التحويل — لا «حدٌّ مقداره صفر».
            </p>
            {walletRow ? (
              <WalletForm
                key={walletRow.country_code}
                row={walletRow}
                disabled={!isAdmin}
                onSaved={(message) => {
                  setDone(message);
                  void load();
                }}
                onError={setError}
              />
            ) : (
              <p className="text-12.5 text-muted">
                لا حدود محفوظة لهذه الدولة.
              </p>
            )}
          </section>

          {/* **«سياسات الدفع» لا «مهلة تأكيد كليك»**: البطاقةُ صارت تحمل شيئين
              (المهلةَ ومبالغَ البقشيش)، وعنوانٌ يسمّي أحدَهما يجعل الآخرَ لا
              يُوجد لمن يبحث عنه. والاسمُ هو اسمُ جدولها `payment_settings` —
              نفسُ السبب الذي جعلها جدولاً مستقلاً عن `wallet_settings`. */}
          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">سياسات الدفع</h2>
            <h3 className="mb-2 mt-12 text-12.5 font-bold text-ink">
              مهلة تأكيد حوالة كليك
            </h3>
            <p className="mb-12 text-11 leading-snug text-muted">
              بعدها تصير الدفعةُ نزاعاً ويُخطر الطرفان.{" "}
              <b className="text-ink">ولا أثرَ رجعياً</b>: المهلةُ تُجمَّد على
              الدفعة لحظة إدخال المرجع، فتعديلُها هنا يحكم ما يأتي بعده لا ما
              ينتظر الآن.
            </p>
            {paymentRow ? (
              <PaymentForm
                key={paymentRow.country_code}
                row={paymentRow}
                disabled={!isAdmin}
                onSaved={(message) => {
                  setDone(message);
                  void load();
                }}
                onError={setError}
              />
            ) : (
              <p className="text-12.5 text-muted">لا إعداد دفعٍ لهذه الدولة.</p>
            )}
          </section>

          {/* حافزُ الإحالة (12-ح) — بطاقةٌ مستقلةٌ لأن جدولَه مستقل
              (`referral_settings`)، ونفسُ سببِ استقلال «سياسات الدفع» عن
              «حدود المحفظة»: حقلٌ يسكن شاشةً غير جدوله يصير البحثُ عنه تخميناً */}
          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">حافز إحالة السائقات</h2>
            <p className="mb-12 text-11 leading-snug text-muted">
              مكافأةٌ تُدفع في محفظة من أحال، بعد أن يُعتمد حسابُ المُحالة{" "}
              <b className="text-ink">ويُثبَّت جنسُها</b> وتُكمل عددَ الرحلات
              أدناه. <b className="text-ink">وصفرُ المبلغ يعني «لم يُحدَّد»</b>{" "}
              فلا تُدفع مكافأةٌ ولا يُوعَد بها أحد — والإحالاتُ تُسجَّل على كل
              حال. وتعديلُ الحدِّ يعيد تقييمَ ما لم يُدفع، ولا يمسّ ما دُفع.
            </p>
            {referral ? (
              <ReferralForm
                key={referral.country_code}
                row={referral}
                disabled={!isAdmin}
                onSaved={(message) => {
                  setDone(message);
                  void load();
                }}
                onError={setError}
              />
            ) : (
              <p className="text-12.5 text-muted">لا إعداد إحالةٍ لهذه الدولة.</p>
            )}
          </section>
        </div>
      )}

      {guard ? (
        <GuardModal
          onClose={() => setGuard(null)}
          onConfirm={(reason) => {
            setGuard(null);
            void flip(guard.key, false, reason);
          }}
        />
      ) : null}
    </Shell>
  );
}

function CommissionForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: CommissionSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (message: string) => void;
}) {
  const [percent, setPercent] = useState(row.commission_percent);
  const [enabled, setEnabled] = useState(row.commission_enabled);
  const [scope, setScope] = useState(row.applies_to);
  const [busy, setBusy] = useState(false);

  return (
    <>
      <Field
        label="النسبة ٪"
        dir="ltr"
        inputMode="decimal"
        value={percent}
        disabled={disabled}
        onChange={(event) =>
          setPercent(event.target.value.replace(/[^0-9.]/g, ""))
        }
      />

      <div className="mt-12">
        <span className="label">النطاق</span>
        <div className="flex gap-8">
          {(["all_rides", "cashless_rides"] as const).map((key) => (
            <button
              key={key}
              type="button"
              disabled={disabled}
              onClick={() => setScope(key)}
              className={cn(
                "flex-1 rounded-12 border px-12 py-10 text-12",
                scope === key
                  ? "border-ink font-semibold text-ink"
                  : "border-line text-muted",
              )}
            >
              {key === "all_rides"
                ? "كل الرحلات (ومنها الكاش)"
                : "ما يمر بالمنصة فقط (محفظة وبطاقة)"}
            </button>
          ))}
        </div>
        <p className="mt-6 text-11 leading-snug text-muted">
          «كل الرحلات» تعني أن عمولة رحلة الكاش تُخصم من محفظة الكبتن — وقد
          تُنقص رصيده.
        </p>
      </div>

      {/* مفتاحٌ لا مربّعُ اختيار: الصفحةُ كلُّها مفاتيح، ومربّعٌ خامٌ بينها
          يقرأ كأنه من نموذجٍ آخر */}
      <div className="mt-14 flex items-center gap-10">
        <button
          type="button"
          disabled={disabled}
          onClick={() => setEnabled(!enabled)}
          aria-label="تفعيل العمولة"
          className={cn(
            "relative block h-27 w-46 flex-none rounded-full transition-colors disabled:opacity-60",
            enabled ? "bg-ok" : "bg-line",
          )}
        >
          <span
            className={cn(
              "absolute top-3 block size-21 rounded-full bg-surface transition-all",
              enabled ? "start-22" : "start-3",
            )}
          />
        </button>
        <span className="text-12.5 text-ink">
          {enabled ? "مفعّلة" : "معطّلة"}
        </span>
      </div>

      <Button
        className="mt-14"
        size="sm"
        disabled={disabled}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateCommission(row.country_code, {
            commission_enabled: enabled,
            commission_percent: percent,
            applies_to: scope,
          })
            .then(() => onSaved("حُفظت العمولة"))
            .catch((caught) =>
              onError(
                caught instanceof ApiError ? caught.message : "تعذّر الحفظ",
              ),
            )
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </>
  );
}

function WalletForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: WalletSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (message: string) => void;
}) {
  const [daily, setDaily] = useState(row.transfer_daily_limit);
  const [monthly, setMonthly] = useState(row.transfer_monthly_limit);
  const [minimum, setMinimum] = useState(row.min_withdrawal_amount);
  const [busy, setBusy] = useState(false);

  const clean = (value: string) => value.replace(/[^0-9.]/g, "");

  return (
    <>
      <Field
        label="حد التحويل اليومي"
        dir="ltr"
        inputMode="decimal"
        value={daily}
        disabled={disabled}
        onChange={(event) => setDaily(clean(event.target.value))}
      />
      <div className="mt-12">
        <Field
          label="حد التحويل الشهري"
          dir="ltr"
          inputMode="decimal"
          value={monthly}
          disabled={disabled}
          onChange={(event) => setMonthly(clean(event.target.value))}
        />
      </div>
      <div className="mt-12">
        <Field
          label="الحد الأدنى للسحب"
          dir="ltr"
          inputMode="decimal"
          value={minimum}
          disabled={disabled}
          onChange={(event) => setMinimum(clean(event.target.value))}
        />
      </div>

      <Button
        className="mt-14"
        size="sm"
        disabled={disabled}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateWalletSettings(row.country_code, {
            transfer_daily_limit: daily,
            transfer_monthly_limit: monthly,
            min_withdrawal_amount: minimum,
          })
            .then(() => onSaved("حُفظت الحدود"))
            .catch((caught) =>
              onError(
                caught instanceof ApiError ? caught.message : "تعذّر الحفظ",
              ),
            )
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </>
  );
}

/** مبلغُ الحافز وحدُّ الرحلات. **و`key={country}` عليه كبقية النماذج**:
 *  `useState(row.…)` لا يُعاد قراءتُه عند تبدّل الخاصية، فتبديلُ السوق يكتب
 *  رقمَ سوقٍ في سوقٍ آخر — وهو عطبٌ وقع في هذه الشاشة نفسها. */
function ReferralForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: ReferralSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (message: string) => void;
}) {
  const [amount, setAmount] = useState(row.reward_amount);
  const [rides, setRides] = useState(String(row.required_rides));
  const [busy, setBusy] = useState(false);

  return (
    <>
      <div className="grid grid-cols-2 gap-10">
        <Field
          label={`مبلغ المكافأة (${currencyLabel(currencyOf(row.country_code))})`}
          dir="ltr"
          inputMode="decimal"
          value={amount}
          disabled={disabled}
          onChange={(event) =>
            setAmount(event.target.value.replace(/[^0-9.]/g, ""))
          }
        />
        <Field
          label="رحلات المُحالة المطلوبة"
          dir="ltr"
          inputMode="numeric"
          value={rides}
          disabled={disabled}
          onChange={(event) => setRides(event.target.value.replace(/[^0-9]/g, ""))}
        />
      </div>
      <p className="mt-6 text-11 text-muted">
        {Number(row.reward_amount) > 0
          ? `الحالي: ${money(row.reward_amount, currencyOf(row.country_code))} بعد ${arabicDigits(String(row.required_rides))} رحلات`
          : `لم يُحدَّد مبلغٌ بعد — والشرطُ ${arabicDigits(String(row.required_rides))} رحلات`}
      </p>
      <Button
        className="mt-14"
        size="sm"
        disabled={disabled || amount === "" || rides === ""}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateReferralSettings(row.country_code, {
            reward_amount: amount,
            required_rides: Number(rides),
          })
            .then(() =>
              onSaved("حُفظ الحافز — يُقيَّم ما لم يُدفع بالحدّ الجديد"),
            )
            .catch((caught) =>
              onError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ"),
            )
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </>
  );
}


function PaymentForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: PaymentSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (message: string) => void;
}) {
  const [hours, setHours] = useState(String(row.cliq_confirmation_hours));
  const [small, setSmall] = useState(row.tip_preset_small);
  const [medium, setMedium] = useState(row.tip_preset_medium);
  const [max, setMax] = useState(row.tip_max);
  const [busy, setBusy] = useState(false);

  /** مبلغُ مالٍ كما يُكتب — **بلا أرقامٍ عربية-هندية**: حقلٌ يُكتب فيه لا يُقرأ. */
  const money = (value: string) => value.replace(/[^0-9.]/g, "");

  function save(
    payload: Parameters<typeof updatePaymentSettings>[1],
    message: string,
  ) {
    setBusy(true);
    updatePaymentSettings(row.country_code, payload)
      .then(() => onSaved(message))
      .catch((caught) =>
        onError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ"),
      )
      .finally(() => setBusy(false));
  }

  return (
    <>
      <Field
        label="عدد الساعات"
        dir="ltr"
        inputMode="numeric"
        value={hours}
        disabled={disabled}
        onChange={(event) =>
          setHours(event.target.value.replace(/[^0-9]/g, ""))
        }
      />
      <p className="mt-6 text-11 text-muted">
        الحالي: {arabicDigits(String(row.cliq_confirmation_hours))} ساعة
      </p>

      <Button
        className="mt-14"
        size="sm"
        disabled={disabled || !hours}
        loading={busy}
        onClick={() =>
          save(
            { cliq_confirmation_hours: Number(hours) },
            "حُفظت المهلة — تسري على ما يأتي بعدها",
          )
        }
      >
        حفظ
      </Button>

      {/* مبالغُ البقشيش (12-و) — في بطاقة **سياسات الدفع** لا في «التسعيرة»:
          الجدولُ هو `payment_settings`، وحقلٌ يسكن شاشةً غير جدوله يجعل
          البحثَ عنه تخميناً. والصفرُ يُخفي الميزةَ فلا حدَّ أدنى يمنع إطفاءها */}
      <div className="mt-18 border-t border-line pt-14">
        <h3 className="mb-2 text-12.5 font-bold text-ink">مبالغ البقشيش</h3>
        <p className="mb-12 text-11 leading-snug text-muted">
          زرّان يراهما الراكب بعد التقييم، وسقفٌ يحرس من إصبعٍ تزلّ. والصفرُ يعني
          «لم يُضبط» فتُخفى الأزرار — لا بقشيشاً مقداره صفر. ويصل الكبتنَ كاملاً
          بلا عمولة.
        </p>
        <div className="grid grid-cols-3 gap-10">
          <Field
            label="الزر الأول"
            dir="ltr"
            inputMode="decimal"
            value={small}
            disabled={disabled}
            onChange={(event) => setSmall(money(event.target.value))}
          />
          <Field
            label="الزر الثاني"
            dir="ltr"
            inputMode="decimal"
            value={medium}
            disabled={disabled}
            onChange={(event) => setMedium(money(event.target.value))}
          />
          <Field
            label="السقف"
            dir="ltr"
            inputMode="decimal"
            value={max}
            disabled={disabled}
            onChange={(event) => setMax(money(event.target.value))}
          />
        </div>
        <Button
          className="mt-14"
          size="sm"
          variant="secondary"
          disabled={disabled || !small || !medium || !max}
          loading={busy}
          onClick={() =>
            save(
              {
                tip_preset_small: small,
                tip_preset_medium: medium,
                tip_max: max,
              },
              "حُفظت مبالغ البقشيش",
            )
          }
        >
          حفظ المبالغ
        </Button>
      </div>
    </>
  );
}

/** إطفاءُ الحارس — بتحذيرٍ صريح وسببٍ إلزامي يدخل سجل التدقيق. */
function GuardModal({
  onClose,
  onConfirm,
}: {
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-dim px-20"
      onClick={onClose}
    >
      <div
        className="w-modal max-w-full rounded-20 border border-danger bg-surface p-24"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="mb-4 text-16 font-bold text-danger">
          إطفاء التحقق من الرقم — للطوارئ فقط
        </h2>
        <p className="mb-16 text-12 leading-note text-muted">
          بعد الإطفاء تُنشأ حساباتٌ برقمٍ غير مُثبت، وتبقى موسومةً وقابلةً
          للفلترة في صفحة الركّاب.{" "}
          <b className="text-ink">
            ولا يُعتمد كبتنٌ غير مُثبت الرقم مهما كان هذا المفتاح
          </b>{" "}
          — رقمُه هو ما تصله عليه حوالاتُ السحب. ولا يمس هذا استعادةَ كلمة
          المرور إطلاقاً.
        </p>

        <Field
          label="سبب الإطفاء (يدخل سجل التدقيق)"
          placeholder="ثمانية أحرف على الأقل"
          value={reason}
          maxLength={280}
          onChange={(event) => setReason(event.target.value)}
        />

        <div className="mt-18 flex gap-10">
          <Button
            className="flex-1 border-danger text-danger"
            size="md"
            variant="secondary"
            disabled={reason.trim().length < 8}
            onClick={() => onConfirm(reason.trim())}
          >
            أطفئ الحارس
          </Button>
          <Button className="flex-1" size="md" onClick={onClose}>
            تراجع
          </Button>
        </div>
      </div>
    </div>
  );
}
