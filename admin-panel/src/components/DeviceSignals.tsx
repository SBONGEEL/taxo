/** **إشاراتُ جهاز الكبتن** (SPEC §١٠٣ B/17 و25) — موقعٌ مزيَّفٌ رُصد في آخر يوم، وجهازٌ معدَّل (root)، كما بلّغها تطبيقُه.
 *
 * **بلاغٌ لا قرار** (أمرُ المالك ١٨/١١): لا زرَّ هنا ولا حجبَ آليّ — والرصدُ تقريبيّ: يمسك الشائعَ لا المتعمِّد. **ومفتاحٌ غائبٌ «لم يُقس»**
 * لا «لا»: مفتاحُه مطفأٌ في دولته أو تطبيقُه أقدم.
 */
import { Facts, ProfileSection, useLoader } from "@/components/Profile";
import { exactMoment } from "@/lib/format";

type Signals = { mock_location?: boolean; rooted?: boolean } | null | undefined;

function line(value: boolean | undefined, yes: string, no: string): string {
  if (value === undefined) return "لم يُقس — المفتاحُ مطفأ أو التطبيقُ أقدم";
  return value ? yes : no;
}

export function signalsWarnings(signals: Signals): number {
  if (!signals) return 0;
  return (signals.mock_location ? 1 : 0) + (signals.rooted ? 1 : 0);
}

export function DeviceSignals({ signals, reportedAt }: { signals: Signals; reportedAt?: string | null }) {
  const warnings = signalsWarnings(signals);
  const key = JSON.stringify(signals ?? null);
  const load = useLoader(() => Promise.resolve(signals), [key]);
  return (
    <ProfileSection
      title="إشارات الجهاز"
      icon="shield"
      hint="ما رصده تطبيقُ الكابتن على هاتفه: موقعٌ مزيَّف (تطبيقُ تغيير الموقع) في آخر يوم، وجهازٌ معدَّل (root). بلاغٌ لا قرار — لا يُحجب أحدٌ به آليّاً، والرصدُ يمسك الشائعَ لا المتعمِّد."
      badge={warnings ? `${warnings} تنبيه` : undefined}
      load={load}
    >
      {(value) =>
        value == null ? (
          <Facts rows={[{ label: "الحال", value: "لم يُبلّغ بعد — تطبيقٌ أقدم أو المفتاحان مطفآن في دولته" }]} />
        ) : (
          <Facts
            rows={[
              { label: "موقعٌ مزيَّف", value: line(value.mock_location, "رُصد في آخر يوم", "لم يُرصد") },
              { label: "جهازٌ معدَّل (root)", value: line(value.rooted, "نعم", "لا") },
              { label: "آخر بلاغ", value: reportedAt ? exactMoment(reportedAt) : null },
            ]}
          />
        )
      }
    </ProfileSection>
  );
}
