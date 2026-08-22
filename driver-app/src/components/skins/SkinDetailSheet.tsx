/** **بطاقةُ المنتج** — ما يُقرأ قبل أن تُفتح ورقةُ الدفع.
 *
 * أربعةُ أشياءٍ لا يُشترى بدونها:
 *
 * 1. **المعاينةُ الكبيرة** — الرسمةُ كما رُسمت.
 * 2. **المعاينةُ على خريطةٍ مصغّرة** — **بمقاسها الحقيقيّ** كما سيراها
 *    الراكب. والفرقُ بين الاثنتين هو الفرقُ بين ما اشتراه وما سيُرى.
 * 3. **أين تُرى** — نصّاً صريحاً من `visible_before_accept`: من يدفع في
 *    «أسطورية» يجب أن يعرف أنها **لا تظهر على الخريطة الحرّة** قبل القبول،
 *    لا أن يكتشف ذلك بعد الدفع.
 * 4. **الكميّةُ وعدّادُ الاقتناء** — «متبقٍّ ٣ من ٥٠» يقرّر شراءً الآن.
 *
 * **ولا زرَّ دفعٍ هنا**: هذه تُفتح للقراءة، والدفعُ ورقةٌ بعدها (بندُ ٥ من
 * `MONEY-STEPS-CHECKLIST`).
 */

import type { VehicleSkin } from "@/api/types";
import { SkinArt } from "@/components/skins/SkinArt";
import { SkinMapPreview } from "@/components/skins/SkinMapPreview";
import { Button } from "@/components/ui/Button";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import {
  BLOCKED_LABEL,
  RARITY_CHIP,
  RARITY_LABEL,
  visibilityNote,
} from "@/lib/skins";
import { digits, cn, DISPLAY_LOCALE } from "@/lib/utils";

export function SkinDetailSheet({
  skin,
  busy,
  onBuy,
  onActivate,
  onClose,
}: {
  skin: VehicleSkin;
  busy: boolean;
  /** `null` في الكراج — لا شراءَ من هناك. */
  onBuy: (() => void) | null;
  /** `null` لِما لا يملكه — لا تفعيلَ لِما ليس له. */
  onActivate: (() => void) | null;
  onClose: () => void;
}) {
  return (
    <div
      className="absolute inset-0 z-50 animate-fadein-fast bg-dim"
      onClick={onClose}
    >
      <div
        className="scr absolute inset-x-0 bottom-0 max-h-full animate-slideup rounded-t-24 border-t border-line bg-surface px-18 pb-24 pt-20"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-12 flex items-center gap-8">
          <span
            className={cn(
              "rounded-full border px-10 py-4 text-10.5 font-bold",
              RARITY_CHIP[skin.rarity],
            )}
          >
            {RARITY_LABEL[skin.rarity]}
          </span>
          <h2 className="min-w-0 flex-1 truncate text-17 font-bold text-ink">
            {skin.name}
          </h2>
        </div>

        <SkinArt skin={skin} className="mb-12 h-150 w-full" />

        <div className="mb-6 text-11.5 font-semibold text-muted">
          كما يراها الراكب على الخريطة
        </div>
        <SkinMapPreview skin={skin} className="mb-12 h-150 w-full" />

        {/* **أين تُرى** — الجملةُ التي يشتري الكبتنُ على أساسها */}
        <p className="mb-12 rounded-14 border border-line bg-surface-2 px-14 py-11 text-11.5 leading-note text-ink">
          {visibilityNote(skin)}
          {skin.map_rotates
            ? " وتدور مع اتجاه سيرك."
            : " وتُعرض ثابتةً بلا دوران."}
        </p>

        <dl className="mb-14 flex flex-col gap-7">
          {skin.remaining !== null ? (
            <Line
              term="المتبقّي"
              value={
                skin.remaining > 0
                  ? digits(String(skin.remaining))
                  : "نفدت الكمية"
              }
            />
          ) : null}
          {/* **«عددُ من اقتنوها»** لا «اقتنوها»: الثانيةُ فعلٌ يُقرأ مع
              رقمه «اقتنوها 0» — جملةٌ لا معنى لها. قِيس في المتصفح */}
          <Line
            term="عددُ من اقتنوها"
            value={digits(String(skin.owners_count))}
          />
          {skin.level_required !== null ? (
            <Line
              term="المستوى المطلوب"
              value={digits(String(skin.level_required))}
            />
          ) : null}
          {skin.valid_until ? (
            <Line
              term="حتى"
              value={digits(
                new Date(skin.valid_until).toLocaleDateString(DISPLAY_LOCALE, {
                  day: "numeric",
                  month: "long",
                }),
              )}
            />
          ) : null}
        </dl>

        {onActivate ? (
          <Button size="md" loading={busy} onClick={onActivate}>
            {skin.active ? "مفعَّلة الآن" : "فعّلها"}
          </Button>
        ) : onBuy && skin.price && skin.currency ? (
          <Button size="md" disabled={busy} onClick={onBuy}>
            شراء بـ {digits(skin.price)} {CURRENCY_LABEL[skin.currency]}
          </Button>
        ) : (
          <p className="rounded-16 border border-line bg-surface-2 p-14 text-center text-12.5 font-semibold text-muted">
            {skin.blocked_reason
              ? BLOCKED_LABEL[skin.blocked_reason]
              : "غير معروضة للبيع"}
          </p>
        )}

        <button
          type="button"
          onClick={onClose}
          className="pressable mt-9 w-full py-8 text-center text-12.5 font-semibold text-muted"
        >
          إغلاق
        </button>
      </div>
    </div>
  );
}

function Line({ term, value }: { term: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between">
      <dt className="text-12 text-muted">{term}</dt>
      <dd className="text-12.5 font-semibold text-ink">{value}</dd>
    </div>
  );
}
