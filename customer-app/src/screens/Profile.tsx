/** حسابي: بياناتك، وإشعارات العروض والكوبونات، والخروج (SPEC القسم 11.8).
 *
 * **مفتاحٌ واحد لا اثنان**: `marketing_push_enabled` وحده. إشعارات الرحلة
 * ليست خياراً — «من يطفئ (وصل الكبتن) ينتظر كبتناً لا يعرف أنه وصل» (القسم
 * 10/11.8). ولا يظهر مفتاحٌ ثانٍ حتى مطفأً: خيارٌ معروضٌ غيرُ قابلٍ للتغيير
 * يقرأ كعطل.
 *
 * وحين يكون الرقم غير محقق (أُنشئ الحساب والمفتاح مطفأ للطوارئ — القسم 4)
 * تطالبه الشاشة بالتحقق عند أول فرصة عبر `POST /auth/me/verify-phone`.
 */

import { LogOut, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import type { GenderPreference } from "@/api/types";
import {
  startChallenge,
  updateMe,
  verifyMyPhone,
} from "@/api/endpoints";
import { PhoneVerification } from "@/components/PhoneVerification";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Screen } from "@/components/ui/Screen";
import { useConfig, usePhoneCountry } from "@/lib/config";
import { useSession } from "@/lib/session";
import { useBrand } from "@/lib/brand";
import { useWomenService } from "@/lib/women";
import { cn } from "@/lib/utils";

export function ProfileScreen() {
  const navigate = useNavigate();
  const { user, signOut, refreshUser } = useSession();
  const { config } = useConfig();
  // **اسمان لا اسمٌ واحد** (البند 6 من قرار المالك 2026-08-13): إتاحةُ السِمة
  // إقرارٌ وحده، وإتاحةُ **ما يَعِد بخدمة** مفتاحٌ قُطريٌّ مع الإقرار. ودمجُهما
  // في `available` واحدٍ يعرض «من يقودني افتراضياً» في سوقٍ لا خدمةَ فيه —
  // وهو بعينه الرفضُ بلا مخرجٍ الذي وقع في 10-ج
  // إتاحةُ السِمة (الإقرارُ وحده) — تحكم **ملاحظةَ الخصوصية** هنا، والمفتاحُ
  // نفسُه صار في «الإعدادات» مع ما يخصّ الجهاز
  const { available: themeAvailable } = useBrand();
  // `available` من الخدمة: مفتاحٌ قُطريٌّ **مع** الإقرار — شرطُ ما يَعِد بمطابقة
  const { enabled, available, defaultPreference } = useWomenService();
  const [savingPreference, setSavingPreference] = useState(false);
  const { dialCode } = usePhoneCountry(user?.country_code);

  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);



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

  async function savePreference(next: GenderPreference) {
    setSavingPreference(true);
    setError(null);
    try {
      await updateMe({ ride_gender_preference: next });
      await refreshUser();
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر حفظ التفضيل",
      );
    } finally {
      setSavingPreference(false);
    }
  }

  return (
    <Screen title="بياناتي" back="/account" nav>
      <div className="space-y-20">
        <div className="card space-y-8 p-16">
          <p className="text-18 font-semibold text-ink">{user.name}</p>
          <p dir="ltr" className="text-14 text-muted">
            {user.phone}
          </p>
        </div>

        {!user.phone_verified ? (
          <section className="card space-y-12 border-brand-brd p-16">
            <p className="flex items-center gap-8 font-medium text-ink">
              <ShieldAlert className="size-20 text-brand" />
              رقمك غير مُثبَت
            </p>
            <p className="text-14 text-muted">
              أثبت ملكية رقمك لتأمين حسابك — يُطلب مرةً واحدة.
            </p>

            {verifying ? (
              <PhoneVerification
                phone={user.phone}
                dialCode={dialCode}
                method={config?.auth.verification ?? "none"}
                otpLength={config?.auth.otp_length ?? null}
                requestChallenge={(channel) =>
                  startChallenge(user.phone, user.country_code, channel)
                }
                onProven={provePhone}
                onBack={() => setVerifying(false)}
              />
            ) : (
              <Button onClick={() => setVerifying(true)}>أثبت رقمي الآن</Button>
            )}
          </section>
        ) : null}





        {/* **الجنسُ يُعرض ولا يُبدَّل من هنا** (قرارُ المالك 2026-08-15).
            كان زرّان يكتبان `gender` بضغطة، وثلاثةُ أشياء تتعلّق به لا يجوز
            أن تنقلب بضغطةٍ في شاشةِ بيانات: سمةُ الوردي، وإتاحةُ «سائقة
            تقودني»، ومطابقةُ الطلبات المجنَّسة. فمن يضغط «ذكر» يفقد الثلاثةَ
            بلا أن يُقال له، ومن يضغط «أنثى» يفتحها عن نفسه لحظةً بلا نيّة.
            وهو **إقرارٌ يُعطى مرةً عند التسجيل** — وتغييرُه واقعةٌ نادرةٌ
            يشهدها الدعم، لا خيارٌ من اثنين. والعرضُ باقٍ: من لا يرى ما أقرّه
            لا يعرف على أيِّ أساسٍ يُعامَل */}
        {enabled && user.gender ? (
          <section className="card space-y-8 p-16">
            <div className="flex items-baseline justify-between gap-8">
              <p className="font-medium text-ink">الجنس</p>
              <p className="text-14 text-ink">
                {user.gender === "female" ? "أنثى" : "ذكر"}
              </p>
            </div>
            <p className="text-12 leading-relaxed text-muted">
              إقرارٌ ذاتيّ أعطيتَه عند التسجيل — لا نطلب وثيقة، ولا يظهر لأي
              مستخدمٍ آخر. عليه تُبنى مطابقةُ تفضيلات الرحلات، ولتعديله راجع
              الدعم.
            </p>
          </section>
        ) : null}

        {/* التفضيلُ الافتراضي — يُنسخ إلى كل طلبٍ لا تختار فيه شيئاً، وتغييرُه
            يحكم ما يأتي لا رحلةً جاريةً الآن (المرحلة 10-ج).
            **وشرطُه إتاحةُ الخدمة لا إتاحةُ السِمة**: هذا يَعِد بمطابقة */}
        {available ? (
          <section className="card space-y-12 p-16">
            <div>
              <p className="font-medium text-ink">من يقودني افتراضياً</p>
              <p className="mt-2 text-12 leading-relaxed text-muted">
                يسري على كل طلبٍ لا تختارين فيه غيره — ولك تغييره لرحلةٍ واحدة
                من شاشة الطلب.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-8">
              {(
                [
                  { value: "female", label: "إناث" },
                  { value: "male", label: "ذكور" },
                  { value: "any", label: "الجميع" },
                ] as const
              ).map((option) => (
                <button
                  key={option.value}
                  type="button"
                  disabled={savingPreference}
                  onClick={() => savePreference(option.value)}
                  className={cn(
                    "pressable rounded-12 border px-8 py-12 text-14 font-medium transition",
                    defaultPreference === option.value
                      ? "border-brand bg-brand text-brand-ink"
                      : "border-line text-muted hover:bg-surface-2",
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </section>
        ) : null}


        {/* **بابُ «الإعدادات» انتقل إلى `tabAccount`** (الحزمة أ): القرارُ (د)
            فصل ما يخصّ **الجهاز** عمّا يخصّ **الحساب**، ووضع بابَها هنا لأن
            حاويةَ «حسابي» لم تكن قد بُنيت بعد — والنموذجُ يضعه في `accountRows`.
            وقد بُنيت، فبقاؤه هنا بابٌ ثانٍ لشاشةٍ واحدة يفترق عن الأول أوّلَ
            مرةٍ يتغيّر أحدُهما */}

        {/* **«الخصوصية» — التصميمُ النسائيُّ (شاشة ٧) يضعها هنا نصّاً**، وهي
            تخبرها **بأمانٍ تملكه ولا تعرفه**: أن جنسَها لا يُعرض لأحد، وأن
            خريطةَ السيارات القريبة مجهَّلةٌ أصلاً. وكلُّ حرفٍ فيها يصف سلوكاً
            **مبنيّاً ومختبَراً** لا وعداً: `drivers.anonymous_ref` يعطي كنيةً
            لكل اتصالٍ (إحداثياتٌ واتجاهٌ وفئةٌ فقط، SPEC §10)، و`RideDriverOut`
            وإطارُ `nearby_drivers` لا يحملان جنساً لأي طرف —
            و`test_admin_live_map.py::test_rider_facing_paths_still_carry_no_identity`
            يمنع انحرافَ ذلك.

            **وشرطُها الإقرارُ وحده** (كالسِمة): من لم تعلن جنسها ليس لديها ما
            تُطمأن عليه، والنصُّ لها لا عنها. ولا تذكر «سائقات» ولا خدمةً: هي
            حقيقةٌ عن **بياناتها** تسري والخدمةُ مطفأةٌ كما تسري وهي مشتعلة —
            فلا تُعلن عن غير موجود (قاعدةُ القرار 48). */}
        {themeAvailable ? (
          <section className="space-y-8 rounded-16 border border-brand-brd bg-brand-soft p-16">
            <p className="text-14 font-semibold text-ink">الخصوصية</p>
            <p className="text-12.5 leading-relaxed text-muted">
              جنسُكِ لا يُعرض لأي كبتن — لا قبل القبول ولا بعده. وخريطةُ
              السيارات القريبة تعرض موقعاً واتجاهاً وفئةَ مركبةٍ فقط، بلا اسمٍ
              ولا لوحةٍ ولا أي معرّفٍ يُتابَع بين الجلسات.
            </p>
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
          <LogOut className="size-16" />
          تسجيل الخروج
        </Button>
      </div>
    </Screen>
  );
}
