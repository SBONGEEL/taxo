/** الأمان: العامل الثاني وسياسةُ دخول اللوحة — SPEC §14.1، المرحلة 12-د.
 *
 * **شاشةٌ واحدة ببطاقتين، ومداهما مختلف عمداً:**
 *
 * 1. **«التحقق الثنائي لحسابي»** لكل من يدخل اللوحة — `admin` و`support`.
 *    فالإلزامُ للـ`admin` (قرارُ المالك)، لكن العاملَ المؤكَّد يسري على صاحبه
 *    أيّاً كان دورُه، ومن أراد أن يحمي حسابه فله ذلك بلا انتظار قرار.
 * 2. **«سياسةُ دخول اللوحة»** لـ`admin` حصراً: مفتاحُ الإلزام ومهلةُ الخمول
 *    قرارٌ على الطاقم كلّه لا إجراءُ دعمٍ فنيّ — كصفحة العقود (القسم 13/8).
 *    و`support` لا يقرأ `GET /admin/security` أصلاً، فالبطاقةُ لا تُطلب له.
 *
 * **وليست هذه شاشةَ إعداداتٍ per-country**، ولذلك لا تقرأ مبدّلَ الدولة: أمنُ
 * لوحةٍ مكتبية ليس سياسةَ سوق، وصفُّ `security_settings` عالميٌّ واحد — وجعلُه
 * per-country يفتح ثقباً يُتجاوَز بحسابٍ دولتُه الأخرى.
 *
 * **وزرُّ الإلزام يُعطَّل بسببٍ مكتوب لا يُترك ليرتدّ 409**: الخلفيةُ ترفض
 * الإشعالَ قبل أن يُثبت الطالبُ نفسُه أن استردادَه يعمل، وزرٌّ يعمل ثم يرتدّ
 * يُعلّم المشرفَ أن يعيد المحاولة، وزرٌّ معطَّلٌ يقول سببَه يُعلّمه أن يُصلح —
 * وهي قاعدةُ زرِّ «اعتماد الكبتن» في شاشة السائقين.
 */

import { AlertTriangle, KeyRound, ShieldCheck, ShieldOff } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  confirmTotp,
  disableTotp,
  enrollTotp,
  getMyTotp,
  getSecurityPolicy,
  updateSecurityPolicy,
  verifyRecoveryCode,
} from "@/api/endpoints";
import type { SecurityPolicy, TotpEnrollment, TotpStatus } from "@/api/types";
import { QrCode } from "@/components/QrCode";
import { Shell } from "@/components/Shell";
import { AdminAccountCard } from "@/components/AdminAccountCard";
import { Backups } from "@/components/Backups";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { moment } from "@/lib/format";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { useSession } from "@/lib/session";
import { digits, cn } from "@/lib/utils";

/** حقلُ الرمز بقيم `DESIGN.md` §2.3 — تباعدُ `.42em` ومقاسُ 26. */
function CodeInput({
  id,
  value,
  onChange,
  autoFocus,
}: {
  id: string;
  value: string;
  onChange: (next: string) => void;
  autoFocus?: boolean;
}) {
  return (
    <input
      id={id}
      dir="ltr"
      inputMode="numeric"
      autoComplete="one-time-code"
      autoFocus={autoFocus}
      maxLength={6}
      placeholder="······"
      className="fld p-15 text-center text-26 font-bold tracking-code"
      value={value}
      onChange={(event) => onChange(event.target.value.replace(/[^0-9]/g, ""))}
    />
  );
}

/** رموزُ الاسترداد كما تُعرض **مرةً واحدة**.
 *
 * **وبلا تحويلٍ إلى الأرقام العربية-الهندية**: هذه مُعرّفاتٌ تُنسخ حرفاً حرفاً
 * ويقارنها صاحبُها بما كتبه على ورقة — لا كمياتٌ تُقرأ. وهي قاعدةُ `Cards.tsx`
 * و`Vehicle.tsx` في تطبيق الكبتن: الأرقامُ العربية للكميات والتواريخ، واللاتينية
 * لما يُطابق حرفاً بحرف.
 */
function RecoveryCodes({ codes }: { codes: string[] }) {
  const [copied, setCopied] = useState(false);
  const text = codes.join("\n");

  return (
    <div className="mt-14 rounded-14 border border-warn bg-surface-2 p-14">
      <div className="mb-10 flex items-center gap-8 text-12.5 font-bold text-ink">
        <AlertTriangle size={15} className="text-warn" />
        احفظها الآن — لن تُعرض مرةً أخرى
      </div>
      <p className="mb-12 text-11 leading-snug text-muted">
        كلُّ رمزٍ يعمل مرةً واحدة، وبها تدخل اللوحة إن فقدت هاتفك. ولا مسارَ في
        النظام يعيد عرضها: من أغلق هذه الشاشة بلا نسخٍ يُطفئ عاملَه برمزٍ حاضر
        ويسجّل من جديد.
      </p>
      <ul dir="ltr" className="grid grid-cols-2 gap-8">
        {codes.map((code) => (
          <li
            key={code}
            className="rounded-10 border border-line bg-surface px-10 py-8 text-center text-13 font-bold tracking-brand text-ink"
          >
            {code}
          </li>
        ))}
      </ul>
      <div className="mt-12 flex gap-10">
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            void navigator.clipboard
              .writeText(text)
              .then(() => setCopied(true))
              .catch(() => setCopied(false));
          }}
        >
          {copied ? "نُسخت" : "انسخ الرموز"}
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            // تنزيلٌ محليٌّ من Blob — لا نداءَ شبكةٍ يمرّ برموزٍ سرّية
            const url = URL.createObjectURL(
              new Blob([`${text}\n`], { type: "text/plain;charset=utf-8" }),
            );
            const link = document.createElement("a");
            link.href = url;
            link.download = "taxo-recovery-codes.txt";
            link.click();
            URL.revokeObjectURL(url);
          }}
        >
          نزّلها ملفاً
        </Button>
      </div>
    </div>
  );
}

function MyFactorCard({
  status,
  onChanged,
  onError,
  onDone,
}: {
  status: TotpStatus;
  onChanged: () => void;
  onError: (caught: unknown) => void;
  onDone: (message: string | null) => void;
}) {
  const [enrollment, setEnrollment] = useState<TotpEnrollment | null>(null);
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [recovery, setRecovery] = useState("");
  const [disabling, setDisabling] = useState(false);
  const [disableCode, setDisableCode] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    onError(null);
    onDone(null);
    try {
      await action();
    } catch (caught) {
      onError(caught);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-16 border border-line bg-surface p-18">
      <h2 className="mb-4 flex items-center gap-8 text-14 font-bold text-ink">
        {status.confirmed ? (
          <ShieldCheck size={16} className="text-ok" />
        ) : (
          <ShieldOff size={16} className="text-muted" />
        )}
        التحقق الثنائي لحسابي
      </h2>
      <p className="mb-12 text-11 leading-snug text-muted">
        رمزٌ من تطبيق مصادقة على هاتفك (Google Authenticator أو ما يشبهه) يُطلب
        بعد كلمة المرور. ولا رسائلَ ولا شرائح: الرمزُ يولّده هاتفك بلا شبكة.
      </p>

      {/* **قبل كل شيء آخر**: لا يُثبت أحدٌ رمزاً لم يره بعد، ولا يُقرأ «جرّب رمزاً
          من ورقتك» قبل أن تظهر الورقة. وهي معروضةٌ مرةً واحدةً في عمر الحساب،
          فمكانُها أعلى ما في البطاقة لا أسفلَه */}
      {codes ? <RecoveryCodes codes={codes} /> : null}

      {status.confirmed ? (
        <>
          <dl className="mb-14 grid grid-cols-2 gap-y-8 text-12.5">
            <dt className="text-muted">مُفعَّل منذ</dt>
            <dd className="text-ink">
              {status.confirmed_at ? moment(status.confirmed_at) : "—"}
            </dd>
            <dt className="text-muted">رموزُ استرداد متبقّية</dt>
            <dd className="text-ink">
              {digits(String(status.recovery_codes_remaining))}
            </dd>
            <dt className="text-muted">إثباتُ الاسترداد</dt>
            <dd
              className={cn(
                status.recovery_verified_at ? "text-ok" : "text-warn",
              )}
            >
              {status.recovery_verified_at
                ? `جُرِّب — ${moment(status.recovery_verified_at)}`
                : "لم يُجرَّب بعد"}
            </dd>
          </dl>

          {status.recovery_verified_at ? null : (
            <div className="mb-14 rounded-14 border border-warn bg-surface-2 p-14">
              <div className="mb-8 text-12.5 font-bold text-ink">
                أثبت أن رمز الاسترداد يعمل
              </div>
              <p className="mb-10 text-11 leading-snug text-muted">
                جرّب رمزاً من ورقتك الآن. يُستهلك واحدٌ من عشرة — إثباتٌ يُجرَّب
                لا مربَّعٌ يُؤشَّر، وهو <b>شرطُ إلزام بقية المشرفين</b>: لا
                يُلزَم أحدٌ قبل أن يثبت أن مخرج الاسترداد يعمل فعلاً.
              </p>
              <Field
                label="رمز استرداد"
                id="prove-recovery"
                dir="ltr"
                placeholder="XXXXX-XXXXX"
                value={recovery}
                onChange={(event) => setRecovery(event.target.value)}
              />
              <Button
                className="mt-12"
                size="sm"
                loading={busy}
                disabled={recovery.trim().length < 8}
                onClick={() =>
                  void run(async () => {
                    await verifyRecoveryCode(recovery.trim());
                    setRecovery("");
                    onDone("الاسترداد يعمل — واستُهلك رمزٌ واحد");
                    onChanged();
                  })
                }
              >
                جرّب الرمز
              </Button>
            </div>
          )}

          {disabling ? (
            <div className="rounded-14 border border-line bg-surface-2 p-14">
              <div className="mb-8 text-12.5 font-bold text-ink">
                إطفاء التحقق الثنائي
              </div>
              <p className="mb-10 text-11 leading-snug text-muted">
                يلزم رمزٌ حاضرٌ من تطبيقك — لا جلسةٌ مفتوحة: جلسةٌ مسروقة تُسقط
                العاملَ الذي وُضع لأجلها إن كفى وجودُها.
              </p>
              <CodeInput
                id="disable-code"
                value={disableCode}
                onChange={setDisableCode}
                autoFocus
              />
              <div className="mt-12 flex gap-10">
                <Button
                  size="sm"
                  variant="danger"
                  loading={busy}
                  disabled={disableCode.length < 6}
                  onClick={() =>
                    void run(async () => {
                      await disableTotp({ code: disableCode });
                      setDisableCode("");
                      setDisabling(false);
                      onDone("أُطفئ التحقق الثنائي، وأُبطلت جلساتك الأخرى");
                      onChanged();
                    })
                  }
                >
                  أطفئه
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setDisabling(false);
                    setDisableCode("");
                  }}
                >
                  إلغاء
                </Button>
              </div>
            </div>
          ) : status.required ? (
            <p className="rounded-12 bg-surface-2 px-12 py-10 text-11 leading-snug text-muted">
              التحقق الثنائي <b>مُلزَمٌ على دورك</b>، فلا يمكن إطفاؤه من هنا —
              ومفتاحٌ يخرج منه كلُّ مشرفٍ بنقرةٍ ليس إلزاماً. ومن فقد هاتفه
              وورقةَ رموزه فمخرجُه أمرٌ على الخادم يشغّله من يملك القاعدة.
            </p>
          ) : (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setDisabling(true)}
            >
              إطفاء التحقق الثنائي
            </Button>
          )}
        </>
      ) : enrollment ? (
        <>
          <div className="flex flex-col items-center gap-12 sm:flex-row sm:items-start">
            <QrCode payload={enrollment.uri} size={180} />
            <div className="min-w-0 flex-1">
              <p className="mb-8 text-11 leading-snug text-muted">
                امسح الرمز بتطبيق المصادقة، أو أدخل السرّ يدوياً إن رفض الكاميرا:
              </p>
              <code
                dir="ltr"
                className="block break-all rounded-10 border border-line bg-surface-2 px-10 py-8 text-12 text-ink"
              >
                {enrollment.secret}
              </code>
              <label className="label mt-14" htmlFor="confirm-code">
                ثم اكتب الرمز الذي يعرضه التطبيق
              </label>
              <CodeInput id="confirm-code" value={code} onChange={setCode} />
              <Button
                className="mt-12"
                size="sm"
                loading={busy}
                disabled={code.length < 6}
                onClick={() =>
                  void run(async () => {
                    const result = await confirmTotp(code);
                    setCodes(result.recovery_codes);
                    setCode("");
                    setEnrollment(null);
                    onDone("فُعِّل التحقق الثنائي على حسابك");
                    onChanged();
                  })
                }
              >
                تأكيد
              </Button>
            </div>
          </div>
          <p className="mt-12 text-11 leading-snug text-muted">
            ولا يُعتبر مُفعَّلاً قبل أن تُدخل رمزاً صحيحاً: سرٌّ لم يثبت أنه وصل
            هاتفك يقفلك خارج اللوحة برمزٍ لا تملك مصدره.
          </p>
        </>
      ) : (
        <>
          {status.required ? (
            <p className="mb-12 rounded-12 border border-warn bg-surface-2 px-12 py-10 text-11.5 leading-snug text-ink">
              التحقق الثنائي مُلزَمٌ على دورك، ولا يفتح لك بابٌ إداريٌّ قبل
              تسجيله.
            </p>
          ) : null}
          <Button
            size="sm"
            loading={busy}
            onClick={() =>
              void run(async () => {
                setEnrollment(await enrollTotp());
              })
            }
          >
            سجّل التحقق الثنائي
          </Button>
        </>
      )}

    </section>
  );
}

function PolicyCard({
  policy,
  onSaved,
  onError,
}: {
  policy: SecurityPolicy;
  onSaved: (next: SecurityPolicy, message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [minutes, setMinutes] = useState(
    String(policy.admin_idle_timeout_minutes),
  );
  const [busy, setBusy] = useState(false);

  const factor = policy.my_factor;
  const blocked = !factor.confirmed
    ? "سجّل تحققك الثنائي أولاً — لا تُلزم غيرك بما لم تفعله."
    : !factor.recovery_verified_at
      ? "أثبت أن رمز الاسترداد يعمل قبل إلزام الجميع — وهو نداءٌ يستهلك رمزاً حقيقياً."
      : null;

  async function save(body: Parameters<typeof updateSecurityPolicy>[0], message: string) {
    setBusy(true);
    onError(null);
    try {
      onSaved(await updateSecurityPolicy(body), message);
    } catch (caught) {
      onError(caught);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-16 border border-line bg-surface p-18">
      <h2 className="mb-4 flex items-center gap-8 text-14 font-bold text-ink">
        <KeyRound size={16} />
        سياسة دخول اللوحة
      </h2>
      <p className="mb-14 text-11 leading-snug text-muted">
        سياسةٌ واحدةٌ للسوقين — لا لكل دولة: أمنُ لوحةٍ مكتبية ليس سياسةَ سوق،
        وإلزامٌ يُقرأ من دولة الحساب يُتجاوَز بحسابٍ دولتُه الأخرى.
      </p>

      <div className="flex items-start gap-12 border-t border-line pt-14">
        <span className="flex-1">
          <span className="block text-13 font-semibold text-ink">
            إلزام المشرفين بالتحقق الثنائي
          </span>
          <span className="block text-11 leading-snug text-muted">
            يسري على دور <b>admin</b> وحده. ومن أُلزم ولم يسجّل بعد يدخل بكلمة
            مروره ويجد كلَّ بابٍ إداريٍّ مغلقاً إلا بابَ التسجيل.
          </span>
        </span>
        <button
          type="button"
          disabled={busy || (!policy.admin_totp_required && blocked !== null)}
          onClick={() =>
            void save(
              { admin_totp_required: !policy.admin_totp_required },
              policy.admin_totp_required
                ? "أُطفئ الإلزام"
                : "أصبح التحقق الثنائي مُلزَماً على المشرفين",
            )
          }
          className={cn(
            "relative block h-27 w-46 flex-none rounded-full transition-colors disabled:opacity-60",
            policy.admin_totp_required ? "bg-ok" : "bg-line",
          )}
          aria-label="إلزام المشرفين بالتحقق الثنائي"
        >
          <span
            className={cn(
              "absolute top-3 block size-21 rounded-full bg-surface transition-all",
              policy.admin_totp_required ? "start-22" : "start-3",
            )}
          />
        </button>
      </div>

      {blocked && !policy.admin_totp_required ? (
        <p className="mt-10 rounded-12 border border-warn bg-surface-2 px-12 py-10 text-11 leading-snug text-ink">
          {blocked}
        </p>
      ) : null}

      <div className="mt-16 border-t border-line pt-14">
        <Field
          label={`مهلة الخمول (دقائق — بين ${digits(
            String(policy.min_idle_timeout_minutes),
          )} و${digits(String(policy.max_idle_timeout_minutes))})`}
          id="idle"
          name="admin_idle_timeout_minutes"
          dir="ltr"
          inputMode="numeric"
          value={minutes}
          onChange={(event) =>
            setMinutes(event.target.value.replace(/[^0-9]/g, ""))
          }
        />
        <p className="mt-8 text-11 leading-snug text-muted">
          تعمل في طبقتين، ولكلٍّ ما تملكه: عمرُ توكن التجديد في الخلفية يُبطل
          توكناً مسروقاً، ومؤقّتٌ في هذا المتصفح <b>يقيس نقرَك وكتابتك لا حركةَ
          الشبكة</b> فيُقفل تبويباً متروكاً على مكتب — والخريطةُ الحيّة تستفتي كل
          خمس ثوانٍ، فمقياسٌ على النداءات يجدّد جلسةَ مكتبٍ خالٍ إلى الأبد.
          والسقفُ الأقصى في الكود لا هنا: اللوحة تفتح مفاتيح المزوّدين والدفع.
        </p>
        <Button
          className="mt-12"
          size="sm"
          variant="secondary"
          loading={busy}
          disabled={
            minutes === "" ||
            Number(minutes) === policy.admin_idle_timeout_minutes
          }
          onClick={() =>
            void save(
              { admin_idle_timeout_minutes: Number(minutes) },
              "حُفظت مهلة الخمول — تسري على الجلسات الجديدة",
            )
          }
        >
          حفظ المهلة
        </Button>
      </div>
    </section>
  );
}

export function SecurityScreen() {
  const { isAdmin, refreshFactor } = useSession();
  const [status, setStatus] = useState<TotpStatus | null>(null);
  const [policy, setPolicy] = useState<SecurityPolicy | null>(null);
  const form = useFormError();
  const error = form.message;
  const setError = form.setMessage;
  const [done, setDone] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const mine = await getMyTotp();
      setStatus(mine);
      // `support` لا يقرأ السياسة (403 من الخلفية) فلا تُطلب له أصلاً: نداءٌ
      // نعرف أنه يرتدّ يملأ شاشةَ الدعم بخطأٍ ليس خطأه
      if (isAdmin) setPolicy(await getSecurityPolicy());
      await refreshFactor();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر القراءة");
    } finally {
      setLoading(false);
    }
  }, [isAdmin, refreshFactor]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <FormErrors value={form.field}>
    <Shell
      title="الأمان"
      subtitle="التحقق الثنائي لحسابك، وسياسةُ دخول اللوحة"
    >
      <ErrorNote message={error} />
      <SuccessNote message={done} />

      {loading || !status ? (
        <Spinner className="mx-auto" />
      ) : (
        <div className="mt-12 grid gap-14 lg:grid-cols-2">
          <MyFactorCard
            status={status}
            onChanged={() => void load()}
            onError={(caught) => form.capture(caught, "تعذّر الإجراء")}
            onDone={setDone}
          />
          {isAdmin && policy ? (
            <PolicyCard
              policy={policy}
              onSaved={(next, message) => {
                setPolicy(next);
                setDone(message);
                void refreshFactor();
              }}
              onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
            />
          ) : null}
        </div>
      )}
      {/* **النسخُ الاحتياطي هنا لا في «الإعدادات»**: ذاك مكانُ ما يحكم سلوكَ
          السوق، وهذا — كالعامل الثاني — **ما يحمي النظامَ من فقدٍ لا رجعةَ فيه**.
          و`admin` حصراً: ملفٌ فيه كلُّ أرقام المستخدمين ودفترُ المحافظ */}
      {isAdmin ? (
        <div className="mt-24">
          {/* **حسابُ الدخول قبل العامل الثاني**: «ما يخصّ دخولي» سؤالٌ واحد */}
          <AdminAccountCard onError={setError} />

          <Backups onError={setError} onDone={setDone} />
        </div>
      ) : null}
    </Shell>
    </FormErrors>
  );
}
