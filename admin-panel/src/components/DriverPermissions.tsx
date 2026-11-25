/** **أذوناتُ هاتف الكبتن** (SPEC §١٠٣ المرحلة A/28) — ما أطفأه من الأساسيّة كما بلّغه مركزُ الأذونات في تطبيقه.
 *
 * **قراءةٌ لا قرار**: لا زرَّ هنا ولا حجب — الكبتنُ يرى الشارةَ نفسَها في رئيسيّته ويصلحها بزرّ. والمشرفُ يقرأ منها سببَ «لا تصله الطلبات»
 * قبل أن يتّصل به. **و`null` غيرُ `[]`**: الأوّلُ «لم يبلّغ» (غلافٌ أقدمُ أو المفتاحُ مطفأ)، والثاني «كلُّها مشتعلة».
 */
import { Facts, ProfileSection, useLoader } from "@/components/Profile";
import { exactMoment } from "@/lib/format";

export const PERMISSION_LABEL: Record<string, string> = {
  location: "الموقع",
  location_background: "الموقع في الخلفية",
  notifications: "الإشعارات",
  overlay: "الظهور فوق التطبيقات",
  battery: "الاستثناء من توفير البطارية",
  autostart: "التشغيل التلقائي",
  full_screen: "تنبيه الطلب بملء الشاشة",
  microphone: "الميكروفون",
};

export function permissionsSummary(off: string[] | null | undefined): { tone: "ok" | "warn" | "none"; text: string } {
  if (off == null) return { tone: "none", text: "لم يُبلّغ بعد — تطبيقٌ أقدم أو الميزةُ مطفأة في دولته" };
  if (off.length === 0) return { tone: "ok", text: "كلُّ الأذونات الأساسيّة مفعّلة" };
  return { tone: "warn", text: `مطفأ: ${off.map((key) => PERMISSION_LABEL[key] ?? key).join("، ")}` };
}

export function DriverPermissions({ off, reportedAt }: { off?: string[] | null; reportedAt?: string | null }) {
  const summary = permissionsSummary(off);
  const load = useLoader(() => Promise.resolve(summary), [summary.text]);
  return (
    <ProfileSection
      title="أذونات الهاتف"
      icon="verified_user"
      hint="ما أطفأه الكابتنُ من أذونات التطبيق الأساسيّة كما بلّغه مركزُ الأذونات — قراءةٌ لا قرار: لا يُحجب أحدٌ بها، والكابتنُ يرى التنبيهَ نفسَه ويصلحه بزرّ."
      badge={summary.tone === "warn" ? `${(off ?? []).length} مطفأ` : undefined}
      load={load}
    >
      {(value) => (
        <Facts
          rows={[
            { label: "الحال", value: value.text },
            { label: "آخر بلاغ", value: reportedAt ? exactMoment(reportedAt) : null },
          ]}
        />
      )}
    </ProfileSection>
  );
}
