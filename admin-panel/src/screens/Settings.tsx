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
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  listCommission,
  listFeatureFlags,
  listPaymentSettings,
  listWalletSettings,
  setFeatureFlag,
  updateCommission,
  updatePaymentSettings,
  updateWalletSettings,
} from "@/api/endpoints";
import type {
  CommissionSetting,
  CountryFeatureFlags,
  FeatureKey,
  PaymentSetting,
  WalletSetting,
} from "@/api/types";
import { Shell } from "@/components/Shell";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
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
  whatsapp_otp_enabled: {
    title: "التحقق عبر واتساب",
    hint: "يُرسل رمزَ التحقق في واتساب بدل الرسائل القصيرة — ويشترط عقد WhatsApp مفعّلاً في صفحة العقود. ولا تُشعَل قبل اعتماد قالب المصادقة بلغة هذا السوق: قالبٌ غير معتمد يجعل كلَّ تسجيلٍ يرتدّ. وعند فشل الإرسال يُعرض على المستخدم الارتداد إلى الرسائل.",
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
  "otp_verification_enabled",
];

export function SettingsScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();

  const [flags, setFlags] = useState<CountryFeatureFlags[] | null>(null);
  const [commission, setCommission] = useState<CommissionSetting[]>([]);
  const [wallet, setWallet] = useState<WalletSetting[]>([]);
  const [payment, setPayment] = useState<PaymentSetting[]>([]);
  const [guard, setGuard] = useState<{ key: FeatureKey } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [f, c, w, p] = await Promise.all([
      listFeatureFlags(),
      listCommission(),
      listWalletSettings(),
      listPaymentSettings(),
    ]);
    setFlags(f);
    setCommission(c);
    setWallet(w);
    setPayment(p);
  }, []);

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

          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">
              مهلة تأكيد حوالة كليك
            </h2>
            <p className="mb-12 text-11 leading-snug text-muted">
              بعدها تصير الدفعةُ نزاعاً ويُخطر الطرفان.{" "}
              <b className="text-ink">ولا أثرَ رجعياً</b>: المهلةُ تُجمَّد على
              الدفعة لحظة إدخال المرجع، فتعديلُها هنا يحكم ما يأتي بعده لا ما
              ينتظر الآن.
            </p>
            {paymentRow ? (
              <PaymentForm
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
  const [busy, setBusy] = useState(false);

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
        onClick={() => {
          setBusy(true);
          updatePaymentSettings(row.country_code, {
            cliq_confirmation_hours: Number(hours),
          })
            .then(() => onSaved("حُفظت المهلة — تسري على ما يأتي بعدها"))
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
