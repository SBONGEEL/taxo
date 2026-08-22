/** بطاقةُ مركبةٍ في الشبكة — **واحدةٌ للكراج والمتجر**.
 *
 * وبطاقتان لشيءٍ واحدٍ تفترقان أوّلَ تعديل، فيقرأ الكبتنُ ندرةً بلونٍ هنا
 * وبلونٍ آخرَ هناك — وهو الشكلُ الثامن في ثوب واجهة.
 *
 * **والمفعَّلةُ معلَّمةٌ بعلامتين لا بواحدة**: إطارٌ **وكلمة**. الإطارُ وحدَه
 * يُقرأ «مختارةٌ الآن للعرض» لا «المفعَّلة»، والفرقُ يقع تحت الإصبع مباشرةً.
 */

import { Check } from "lucide-react";

import type { VehicleSkin } from "@/api/types";
import { SkinArt } from "@/components/skins/SkinArt";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { BLOCKED_LABEL, RARITY_CHIP, RARITY_LABEL } from "@/lib/skins";
import { digits, cn } from "@/lib/utils";

export function SkinCard({
  skin,
  onOpen,
}: {
  skin: VehicleSkin;
  onOpen: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        "pressable flex flex-col gap-8 rounded-16 border bg-surface p-10 text-start",
        skin.active ? "border-ink" : "border-line",
      )}
    >
      <SkinArt skin={skin} className="h-82 w-full" />

      <span className="flex items-center gap-6">
        <span
          className={cn(
            "rounded-full border px-8 py-3 text-9.5 font-bold",
            RARITY_CHIP[skin.rarity],
          )}
        >
          {RARITY_LABEL[skin.rarity]}
        </span>
        {skin.active ? (
          <span className="flex items-center gap-3 text-9.5 font-bold text-ok">
            <Check size={11} /> مفعَّلة
          </span>
        ) : null}
      </span>

      <span className="block truncate text-12.5 font-bold text-ink">
        {skin.name}
      </span>

      {/* **السعرُ أو سببُ المنع — لا كلاهما**: العقدُ يعطي سبباً واحداً
          بأسبقيةٍ مكتوبة، وسطران يقولان لكبتنٍ واحدٍ خبرين عن حالةٍ واحدة */}
      {skin.owned ? (
        <span className="block text-11 text-muted">في كراجك</span>
      ) : skin.blocked_reason ? (
        <span className="block text-11 font-semibold text-muted">
          {BLOCKED_LABEL[skin.blocked_reason]}
        </span>
      ) : skin.price && skin.currency ? (
        <span className="block text-13 font-bold text-ink">
          {digits(skin.price)}{" "}
          <span className="text-10 font-medium text-muted">
            {CURRENCY_LABEL[skin.currency]}
          </span>
        </span>
      ) : (
        <span className="block text-11 text-muted">غير معروضة للبيع</span>
      )}

      {/* **الكميّةُ المتبقيةُ حين تكون محدودة** — و`null` بلا حدٍّ فلا سطر:
          «متبقٍّ: بلا حدّ» جملةٌ لا تخبر بشيءٍ وتُعلّم قارئَها ألّا يقرأ */}
      {skin.remaining !== null ? (
        <span className="block text-10 text-muted">
          {skin.remaining > 0
            ? `متبقٍّ ${digits(String(skin.remaining))}`
            : "نفدت الكمية"}
          {" · "}
          {digits(String(skin.owners_count))} اقتنوها
        </span>
      ) : skin.owners_count > 0 ? (
        <span className="block text-10 text-muted">
          {digits(String(skin.owners_count))} اقتنوها
        </span>
      ) : null}
    </button>
  );
}
