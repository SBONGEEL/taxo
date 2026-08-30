/** لافتاتُ المحتوى — من ملفّ التصميم (خانةُ `showWomenPromo` / `showChallenge`).
 *
 * **والخانةُ نفسُها صارت بيتَ اللافتة** (قرارُ المالك 2026-08-30): يملؤها
 * المشرفُ من اللوحة **بدل أن يُخبز نصُّها** — فعرضُ الخصم النسائيِّ المرسوم
 * **نموذجٌ لا نصٌّ مخبوز**، ونزل صفّاً في الجدول.
 *
 * **والنافذةُ قيست في الخلفية**: ما يصل هنا حيٌّ الآن. **ولا تُقاس في
 * التطبيق** — ساعةُ الجهاز يملكها صاحبُه، **ولافتةٌ انتهت تبقى ظاهرةً لمن
 * أخّر ساعتَه**.
 *
 * **والنقاطُ تحتها من التصميم**: تظهر حين تتعدّد اللافتاتُ لا حين تكون
 * واحدة — **ونقطةٌ واحدةٌ تحت لافتةٍ واحدةٍ تَعِد بثانيةٍ لا وجودَ لها**.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import type { PromoBanner } from "@/api/types";
import * as icons from "lucide-react";

/** **أيقونةٌ زخرفيّةٌ كبيرةٌ في الطرف** — كما يرسمها التصميم (`heart` خلف
 *  عرضِ الخصم النسائيّ). **ولا صورةَ تُرفع**: لا بابَ يخدمها، **وعنوانٌ
 *  يُنشر لمسارٍ لا وجودَ له يرسم صورةً مكسورة** — وهي أسوأُ من لا صورة. */
function Glyph({ name, className }: { name: string; className: string }) {
  const key = name
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
  const table = icons as unknown as Record<
    string,
    ((props: { className?: string }) => JSX.Element) | undefined
  >;
  const Icon = table[key];
  return Icon ? <Icon className={className} /> : null;
}

export function PromoBanners({ banners }: { banners: PromoBanner[] }) {
  const navigate = useNavigate();
  const [at, setAt] = useState(0);
  if (banners.length === 0) return null;

  const banner = banners[Math.min(at, banners.length - 1)];
  const openable = banner.link_kind !== "none" && banner.link !== null;

  const open = () => {
    if (!openable) return;
    if (banner.link_kind === "internal") {
      navigate(banner.link!);
      return;
    }
    // **الخارجيُّ يفتح في لسانٍ جديد** — ولا يُخرج الكبتنَ من شاشته
    window.open(banner.link!, "_blank", "noopener,noreferrer");
  };

  return (
    <>
      <div
        onClick={openable ? open : undefined}
        className={`mb-8 overflow-hidden rounded-16 border border-line bg-surface-2 p-14 ${
          openable ? "pressable cursor-pointer" : ""
        }`}
      >
        <div className="flex items-start gap-10">
          {banner.icon ? (
            <Glyph name={banner.icon} className="size-44 shrink-0 text-line" />
          ) : null}
          <div className="min-w-0 flex-1">
            <div className="text-14 font-bold text-ink">{banner.title}</div>
            {banner.body ? (
              <div className="mt-3 text-11.5 leading-note text-muted">
                {banner.body}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      {banners.length > 1 ? (
        <div className="mb-12 flex justify-center gap-5">
          {banners.map((item, index) => (
            <button
              key={item.id}
              type="button"
              aria-label={`لافتة ${index + 1}`}
              onClick={() => setAt(index)}
              className={
                index === at
                  ? "block h-5 w-14 rounded-3 bg-muted"
                  : "block size-5 rounded-3 bg-line"
              }
            />
          ))}
        </div>
      ) : null}
    </>
  );
}
