/** الملف الشخصي: بياناتك، وإشعارات العروض، والخروج (SPEC القسم 11.8).
 *
 * **مفتاحٌ واحد لا اثنان**: `marketing_push_enabled` وحده. إشعارات الرحلة
 * ليست خياراً — «من يطفئ (وصل الكبتن) ينتظر كبتناً لا يعرف أنه وصل» (القسم
 * 10/11.8). ولا يظهر مفتاحٌ ثانٍ حتى مطفأً: خيارٌ معروضٌ غيرُ قابلٍ للتغيير
 * يقرأ كعطل.
 *
 * وحين يكون الرقم غير محقق (أُنشئ الحساب والمفتاح مطفأ للطوارئ — القسم 4)
 * تطالبه الشاشة بالتحقق عند أول فرصة عبر `POST /auth/me/verify-phone`.
 */

import {
  BellRing,
  LogOut,
  Moon,
  ShieldAlert,
  Sun,
  SunMoon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  getNotificationPreferences,
  setNotificationPreferences,
  startChallenge,
  verifyMyPhone,
} from "@/api/endpoints";
import { PhoneVerification } from "@/components/PhoneVerification";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Screen } from "@/components/ui/Screen";
import { useConfig, usePhoneCountry } from "@/lib/config";
import { useSession } from "@/lib/session";
import { useBrand } from "@/lib/brand";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

export function ProfileScreen() {
  const navigate = useNavigate();
  const { user, signOut, refreshUser } = useSession();
  const { config } = useConfig();
  const { choice, setChoice } = useTheme();
  const { pink, available, setPink } = useBrand();
  const { dialCode } = usePhoneCountry(user?.country_code);

  const [marketing, setMarketing] = useState<boolean | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    getNotificationPreferences()
      .then((preferences) => setMarketing(preferences.marketing_push_enabled))
      .catch(() => setMarketing(null));
  }, []);

  async function toggleMarketing(value: boolean) {
    setMarketing(value);
    setError(null);
    try {
      await setNotificationPreferences(value);
    } catch (caught) {
      setMarketing(!value);
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر حفظ التفضيل",
      );
    }
  }

  async function provePhone(token: string) {
    setError(null);
    try {
      await verifyMyPhone(token);
      await refreshUser();
      setVerifying(false);
      setDone("تم إثبات رقمك.");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر إثبات الرقم",
      );
    }
  }

  if (!user) return null;

  return (
    <Screen title="الملف الشخصي" back="/menu">
      <div className="space-y-5">
        <div className="card space-y-2 p-4">
          <p className="text-lg font-semibold text-ink">{user.name}</p>
          <p dir="ltr" className="text-sm text-muted">
            {user.phone}
          </p>
        </div>

        {!user.phone_verified ? (
          <section className="card space-y-3 border-brand/50 p-4">
            <p className="flex items-center gap-2 font-medium text-ink">
              <ShieldAlert className="size-5 text-brand" />
              رقمك غير مُثبَت
            </p>
            <p className="text-sm text-muted">
              أثبت ملكية رقمك لتأمين حسابك — يُطلب مرةً واحدة.
            </p>

            {verifying ? (
              <PhoneVerification
                phone={user.phone}
                dialCode={dialCode}
                method={config?.auth.verification ?? "none"}
                otpLength={config?.auth.otp_length ?? null}
                requestChallenge={() =>
                  startChallenge(user.phone, user.country_code)
                }
                onProven={provePhone}
                onBack={() => setVerifying(false)}
              />
            ) : (
              <Button onClick={() => setVerifying(true)}>أثبت رقمي الآن</Button>
            )}
          </section>
        ) : null}

        <section className="card space-y-3 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="flex items-center gap-2 font-medium text-ink">
                <BellRing className="size-5" />
                إشعارات العروض
              </p>
              <p className="mt-0.5 text-sm text-muted">
                عروضٌ وتخفيضات. إشعارات رحلتك تصلك دائماً.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={marketing === true}
              aria-label="إشعارات العروض"
              disabled={marketing === null}
              onClick={() => toggleMarketing(!marketing)}
              className={cn(
                "relative h-7 w-12 shrink-0 rounded-full transition",
                marketing ? "bg-brand" : "bg-line",
              )}
            >
              <span
                className={cn(
                  "absolute top-1 size-5 rounded-full bg-white transition-all",
                  marketing ? "start-6" : "start-1",
                )}
              />
            </button>
          </div>
        </section>

        <section className="card space-y-3 p-4">
          <p className="font-medium text-ink">مظهر التطبيق</p>
          <div className="grid grid-cols-3 gap-2">
            {(
              [
                { value: "system", label: "النظام", icon: SunMoon },
                { value: "light", label: "نهاري", icon: Sun },
                { value: "dark", label: "ليلي", icon: Moon },
              ] as const
            ).map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                type="button"
                onClick={() => setChoice(value)}
                className={cn(
                  "flex flex-col items-center gap-1 rounded-xl border px-2 py-3 text-sm transition",
                  choice === value
                    ? "border-brand bg-brand/10 text-ink"
                    : "border-line text-muted hover:bg-line/30",
                )}
              >
                <Icon className="size-5" />
                {label}
              </button>
            ))}
          </div>
        </section>

        {/* السِمة الوردية — لا تظهر إلا لمن لها أن تختارها: الخدمة مفعّلة
            في دولتها وقد أعلنت جنسها. ومن ليست كذلك لا ترى مفتاحاً معطّلاً
            ولا رسالةَ اعتذار (المرحلة 10-ج) */}
        {available ? (
          <section className="card space-y-3 p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-medium text-ink">السِمة الوردية</p>
                {/* السببُ مكتوبٌ لأنه ليس ذوقاً: القرارُ عن المكان الذي أنتِ
                    فيه لا عن جمال اللون */}
                <p className="mt-1 text-xs leading-relaxed text-muted">
                  هوية خدمة التوصيل النسائي. أطفئيها متى شئتِ — الشاشة يراها
                  من حولك.
                </p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={pink}
                aria-label="السِمة الوردية"
                onClick={() => setPink(!pink)}
                className={cn(
                  "relative h-7 w-12 flex-none rounded-full transition",
                  pink ? "bg-brand" : "bg-line",
                )}
              >
                <span
                  className={cn(
                    "absolute top-1 size-5 rounded-full bg-surface transition-all",
                    pink ? "start-6" : "start-1",
                  )}
                />
              </button>
            </div>
          </section>
        ) : null}

        <ErrorNote message={error} />
        <SuccessNote message={done} />

        <Button
          variant="secondary"
          size="lg"
          onClick={async () => {
            await signOut();
            navigate("/login", { replace: true });
          }}
        >
          <LogOut className="size-4" />
          تسجيل الخروج
        </Button>
      </div>
    </Screen>
  );
}
