/** **وضعُ الضيف — تشغيلٌ وإطفاءٌ لكلِّ تطبيق** (أمرُ المالك ٢٠٢٦-١٠-١٥، SPEC §٧٦-ن/٤).
 *
 * زرُّ «تجربة كضيف» في شاشة الترحيب يُرسم حيث المفتاحُ مشتعل — **والضيفُ في صندوق عرضٍ لا يبلغ أحداً ولا مالاً**: كبتنٌ محاكى، ورصيدٌ
 * للعرض، ولا رحلةَ حقيقيّة. والخادمُ لا يعرف منه إلا أنه بدأ وما كتبه في «أرسل ملاحظة»، **ويمحوه بعد ثلاثين يوماً**.
 *
 * **وموضعُه شاشةُ الإصدارات**: هي التي تُدار فيها التطبيقاتُ لكلِّ تطبيق.
 */

import { useCallback, useEffect, useState } from "react";

import { getGuestMode, setGuestMode } from "@/api/endpoints";
import type { GuestMode } from "@/api/types";
import { Switch } from "@/components/ui/Field";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useSession } from "@/lib/session";

const ROWS: Array<{ key: keyof GuestMode; label: string }> = [
  { key: "rider", label: "تطبيق الراكب" },
  { key: "driver", label: "تطبيق الكبتن" },
];

export function GuestModeCard() {
  const { isAdmin } = useSession();
  const [mode, setMode] = useState<GuestMode | null>(null);
  const [busy, setBusy] = useState<keyof GuestMode | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => setMode(await getGuestMode()), []);
  useEffect(() => {
    void load().catch(() => setError("تعذّرت قراءة وضع الضيف"));
  }, [load]);

  return (
    <section className="mb-18 rounded-16 border border-line bg-surface p-18" data-guest-mode>
      <h2 className="mb-4 text-16 font-bold text-ink">وضعُ الضيف — «تجربة كضيف»</h2>
      <p className="mb-12 text-11 leading-note text-muted">
        يجرّب به المختبِرون ومراجعو المتجر كلَّ شيءٍ بلا رقم: كبتنٌ محاكى، ورصيدٌ للعرض، ولا رحلةَ ولا مالَ حقيقيّ ولا اتّصالَ بأحد.
        ملاحظاتُهم تصل «الملاحظات» موسومةً «ضيف»، وتُمحى بياناتُهم بعد ثلاثين يوماً.
      </p>
      <ErrorNote message={error} />
      {mode === null ? (
        <Spinner />
      ) : (
        <div className="flex flex-col gap-8">
          {ROWS.map((row) => (
            <div
              key={row.key}
              className="flex items-center gap-10 rounded-13 border border-line bg-surface-2 px-13 py-10"
            >
              <span className="flex-1 text-12.5 text-ink">{row.label}</span>
              <span className="text-11.5 text-muted">{mode[row.key] ? "مشتعل" : "مطفأ"}</span>
              <Switch
                checked={mode[row.key]}
                label={`وضع الضيف — ${row.label}`}
                disabled={!isAdmin || busy !== null}
                onChange={(next) => {
                  setBusy(row.key);
                  setError(null);
                  setGuestMode({ [row.key]: next })
                    .then(setMode)
                    .catch(() => setError("تعذّر الحفظ"))
                    .finally(() => setBusy(null));
                }}
              />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
