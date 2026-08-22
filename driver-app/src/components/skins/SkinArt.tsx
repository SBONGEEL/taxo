/** رسمةُ المركبة الكبيرة — في البطاقة وفي ورقة المنتج وفي ورقة الاحتفال.
 *
 * **وتعثّرُ التحميل يُرسم ولا يُترك**: أيقونةُ صورةٍ مكسورةٍ في متجرٍ يُدفع
 * فيه مالٌ تُقرأ **عطباً في التطبيق** لا نقصاً في ملفّ. فيبقى الإطارُ بمقاسه
 * ويظهر اسمُ المركبة — لا قفزةَ في الشبكة ولا فراغٌ يُفسَّر.
 */

import { useEffect, useState } from "react";

import type { VehicleSkin } from "@/api/types";
import { skinAssetUrl } from "@/lib/skins";
import { cn } from "@/lib/utils";

export function SkinArt({
  skin,
  className,
}: {
  skin: VehicleSkin;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  // **يُصفَّر مع تبدّل المركبة**: بغيره تبقى بطاقةٌ ثانيةٌ تُعرض في المكان
  // نفسِه محتفظةً بفشلِ سابقتها
  useEffect(() => setFailed(false), [skin.id]);

  return (
    <div
      className={cn(
        "flex items-center justify-center overflow-hidden rounded-14 bg-surface-2",
        className,
      )}
    >
      {failed ? (
        <span className="px-10 text-center text-11 text-muted">{skin.name}</span>
      ) : (
        <img
          src={skinAssetUrl(skin.store_image_url)}
          alt={skin.name}
          onError={() => setFailed(true)}
          className="size-full object-contain"
        />
      )}
    </div>
  );
}
