/** «إنهاء كل الجلسات» — **من شاشة «حسابي» القديمة إلى بيتٍ مستقلّ** (§٦٢/٣): الشاشةُ القديمةُ نُزعت، والفعلُ باقٍ كما هو حرفاً
 *  في R15 (`screens/t2/AccountT2.tsx`). وورقتُه بلغة التطبيق القائمة حتى يُعاد رسمُ «حسابي» كلِّه (§٦٢/٧). */
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { DrawerSheet } from "@/components/ui/Sheet";
import { useSession } from "@/lib/session";

/** **إنهاءُ كلِّ الجلسات** (SPEC §60-ب/١، قرارُ المالك ٢٠٢٦-١٠-٠٤) — لهاتفٍ أو
 *  حاسوبٍ ضاع. **ويُسأل قبل أن يقع**: يُخرج صاحبَ الحساب من هذا الجهاز أيضاً،
 *  وفعلٌ يُخرج من كلِّ مكانٍ لا يقع بلمسةٍ عابرة. */
export function SignOutEverywhereRow({
  className = "pressable w-full p-10 text-center text-12 text-muted",
}: {
  /** شكلُ الزرّ وحدَه — **والورقةُ وفعلُها واحدٌ للشاشتين** (القائمة وR15). */
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
      <DrawerSheet open={open} onOpenChange={(next) => !busy && setOpen(next)} title="إنهاء كل الجلسات">
        <p className="text-13.5 leading-relaxed text-muted">
          تخرج من حسابك على كلِّ جهازٍ دخلتَ منه — وهذا منها — ولا تصل إشعاراتُ
          حسابك إلى أيٍّ منها. استعمله إن ضاع هاتفٌ أو حاسوب.
        </p>
        <ErrorNote message={error} />
        <div className="mt-16 space-y-8 pb-16">
          <Button variant="danger" size="lg" loading={busy} onClick={() => void confirm()}>
            إنهاء كل الجلسات
          </Button>
          <Button variant="ghost" size="lg" disabled={busy} onClick={() => setOpen(false)}>
            إلغاء
          </Button>
        </div>
      </DrawerSheet>
    </>
  );
}
