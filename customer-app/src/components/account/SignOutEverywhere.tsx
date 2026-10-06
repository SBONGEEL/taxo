/** «إنهاء كل الجلسات» — زرُّه آخرَ «حسابي» (R15، `screens/t2/AccountT2.tsx`)، **وورقتُه بلغة TAXO 2.0** «R23b»
 *  (`design/t2-new/rider/R23b-sign-out-everywhere.dc.html`): ورقةُ R06–R09 بعنوانها، وزرُّ الخطر بالأحمر، و«إلغاء» بحافّةٍ هادئة. */
import { useState } from "react";

import { DrawerT2 } from "@/screens/t2/DrawerT2";
import { NoteT2 } from "@/screens/t2/KitT2";
import { useSession } from "@/lib/session";

/** **إنهاءُ كلِّ الجلسات** (SPEC §60-ب/١، قرارُ المالك ٢٠٢٦-١٠-٠٤) — لهاتفٍ أو
 *  حاسوبٍ ضاع. **ويُسأل قبل أن يقع**: يُخرج صاحبَ الحساب من هذا الجهاز أيضاً،
 *  وفعلٌ يُخرج من كلِّ مكانٍ لا يقع بلمسةٍ عابرة. */
export function SignOutEverywhereRow({
  className = "t2-endall",
}: {
  /** شكلُ الزرّ وحدَه — **والورقةُ وفعلُها واحدٌ** أينما رُسم الزرّ. */
  className?: string;
} = {}) {
  const { signOutEverywhere } = useSession();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await signOutEverywhere();
    } catch (caught) {
      // نصُّ الخلفية كما هو (§17) — ولا عربيةَ ثانيةٌ هنا
      setError(caught instanceof Error ? caught.message : "تعذّر إنهاء الجلسات — أعد المحاولة");
      setBusy(false);
    }
  }

  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className={className}>
        إنهاء كل الجلسات
      </button>
      <DrawerT2 open={open} onOpenChange={(next) => !busy && setOpen(next)} title="إنهاء كل الجلسات">
        <p className="t2-drawer-text">
          تخرج من حسابك على كلِّ جهازٍ دخلتَ منه — وهذا منها — ولا تصل إشعاراتُ
          حسابك إلى أيٍّ منها. استعمله إن ضاع هاتفٌ أو حاسوب.
        </p>
        {error ? <NoteT2 tone="danger">{error}</NoteT2> : null}
        <div className="t2-drawer-actions">
          <button
            type="button"
            className="t2-button t2-destroy"
            disabled={busy}
            aria-busy={busy}
            onClick={() => void confirm()}
          >
            إنهاء كل الجلسات
          </button>
          <button type="button" className="t2-button t2-quiet" disabled={busy} onClick={() => setOpen(false)}>
            إلغاء
          </button>
        </div>
      </DrawerT2>
    </>
  );
}
