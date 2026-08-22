/** **ورقةُ الاحتفال بهديّة أول اشتراك** (2026-08-22).
 *
 * **ولا تُضاف صامتة**: مركبةٌ تظهر في كراجٍ لم يفتحه صاحبُه قطُّ هديّةٌ لم
 * تُعطَ. والورقةُ هي **الإعطاء** — والزرُّ فيها يقود إلى الأثر لا إلى شكرٍ
 * منّا: «فعّلها الآن» تجعلها على خريطته في اللحظة نفسِها.
 *
 * **وتُعرض مرةً ثم تُختم في الخلفية** (`POST /vehicle-skins/{id}/seen`) لا في
 * `localStorage`: هذه **واقعةُ حسابٍ** لا تفضيلَ جهاز — ومن غيّر هاتفه لا
 * يُحتفى به مرةً ثانيةً بهديّةٍ عمرُها شهر.
 *
 * **ولا تُغلق بالنقر على الظلّ** — كورقة الترحيب بحرفها: ما يُعرض مرةً واحدةً
 * في عمر الحساب يُغلق بيدٍ قاصدة، ونقرةٌ عارضةٌ خارجَها تحذفه إلى الأبد.
 *
 * **ولا تُعرض فوق قرار**: محلُّها الرئيسيةُ بعد الاعتماد، ولا تُركَّب مع
 * عرضِ رحلةٍ ولا رحلةٍ جارية (`DriverHome` يرسمها في فرع «معتمد» وحدَه).
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { SkinArt } from "@/components/skins/SkinArt";
import { Button } from "@/components/ui/Button";
import { useGarage } from "@/lib/garage";
import { RARITY_CHIP, RARITY_LABEL, visibilityNote } from "@/lib/skins";
import { cn } from "@/lib/utils";

export function CelebrationSheet() {
  const { garage, activate, celebrated } = useGarage();
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const skin = garage?.celebrate ?? null;
  if (!skin) return null;

  async function close(andActivate: boolean) {
    if (!skin) return;
    setBusy(true);
    // **الختمُ أولاً**: لو فشل التفعيلُ بقيت الورقةُ مغلقةً ولم تُعرض ثانيةً،
    // ولو خُتم بعده لعادت الورقةُ في كلِّ فتحةٍ حتى ينجح التفعيل
    await celebrated(skin.id);
    if (andActivate) {
      // **وفشلُ التفعيل لا يُبكي على هديّة**: المركبةُ في كراجه على كلِّ حال،
      // والكراجُ بابُ التفعيل
      await activate(skin.id).catch(() => undefined);
    }
    setBusy(false);
  }

  return (
    <div className="absolute inset-0 z-50 animate-fadein-fast bg-dim">
      <div className="absolute inset-x-0 bottom-0 animate-slideup rounded-t-24 border-t border-line bg-surface px-18 pb-24 pt-20">
        <p className="mb-2 text-11.5 font-semibold text-muted">
          هديّة أول اشتراك
        </p>
        <h2 className="mb-12 text-20 font-bold text-ink">
          مبروك! سيارتك الجديدة وصلت
        </h2>

        <SkinArt skin={skin} className="mb-12 h-150 w-full" />

        <div className="mb-8 flex items-center gap-8">
          <span
            className={cn(
              "rounded-full border px-10 py-4 text-10.5 font-bold",
              RARITY_CHIP[skin.rarity],
            )}
          >
            {RARITY_LABEL[skin.rarity]}
          </span>
          <span className="min-w-0 flex-1 truncate text-15 font-bold text-ink">
            {skin.name}
          </span>
        </div>

        <p className="mb-16 text-11.5 leading-note text-muted">
          {visibilityNote(skin)} وتجدها دائماً في «مركباتي».
        </p>

        <div className="flex flex-col gap-9">
          <Button size="md" loading={busy} onClick={() => void close(true)}>
            فعّلها الآن
          </Button>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              void close(false);
              navigate("/account/garage");
            }}
            className="pressable w-full py-8 text-center text-12.5 font-semibold text-muted"
          >
            افتح مركباتي
          </button>
        </div>
      </div>
    </div>
  );
}
