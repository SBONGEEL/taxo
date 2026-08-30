/** شبكةُ بلاطات الخدمات — من ملفّ التصميم (`home Captain` / `home Rider`).
 *
 * **والصفوفُ من اللوحة لا من الشيفرة** (قرارُ المالك 2026-08-30): إضافةُ
 * سادسةٍ **بلا نشر**، وإخفاءُ ما تأجّل، وإشعالُ ما جهز.
 *
 * **و«قريباً» تُقرأ ولا تُنقر**: تظهر بعلامتها، **ولا تفتح باباً ولا تصيح
 * بخطأٍ حين تُلمس** — وخطأٌ على لمسةٍ متوقَّعةٍ يُقرأ عطباً. فلا `onClick`
 * عليها أصلاً، **ولا زرَّ معطَّلاً يبتلع اللمسة**.
 *
 * **و«جديد» شارةٌ لا حال**: `is_new` محسوبةٌ في الخلفية بمدّتها، **فتختفي
 * بانقضائها بلا نشر** — وساعةُ الجهاز يملكها صاحبُه.
 */

import * as icons from "lucide-react";
import { useNavigate } from "react-router-dom";

import type { ServiceTile } from "@/api/types";

/** **أيقونةٌ باسمها من اللوحة** — و`layout-grid` بديلٌ حين لا تُعرف.
 *
 * **ولا تسقط الشبكةُ على اسمٍ مكتوبٍ خطأً**: بلاطةٌ بلا أيقونةٍ أهونُ من
 * شاشةٍ بيضاء.
 */
function Glyph({ name, className }: { name: string; className: string }) {
  const key = name
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
  const table = icons as unknown as Record<
    string,
    ((props: { className?: string }) => JSX.Element) | undefined
  >;
  const Icon = table[key] ?? icons.LayoutGrid;
  return <Icon className={className} />;
}

export function ServiceTiles({ tiles }: { tiles: ServiceTile[] }) {
  const navigate = useNavigate();
  if (tiles.length === 0) return null;

  return (
    <div className="mb-12 grid grid-cols-3 gap-8">
      {tiles.map((tile) => {
        const openable = tile.status === "active" && tile.destination !== null;
        return (
          <div
            key={tile.id}
            // **لا `onClick` على «قريباً»** — فاللمسةُ تمرّ بلا حدثٍ ولا خطأ
            onClick={openable ? () => navigate(tile.destination!) : undefined}
            className={`flex flex-col items-center gap-6 rounded-12 border border-line bg-surface px-5 pb-9 pt-11 ${
              openable ? "pressable cursor-pointer" : ""
            }`}
          >
            <Glyph name={tile.icon} className="size-21 text-ink" />
            <span className="text-11.5 font-medium text-ink">{tile.title}</span>
            {tile.status === "soon" ? (
              <span className="rounded-6 border border-line bg-surface-2 px-6 py-2 text-9.5 font-semibold text-warn">
                قريباً
              </span>
            ) : tile.is_new ? (
              <span className="rounded-6 border border-brand-brd bg-brand-soft px-6 py-2 text-9.5 font-semibold text-brand">
                جديد
              </span>
            ) : tile.subtitle ? (
              <span className="text-9.5 text-muted">{tile.subtitle}</span>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
