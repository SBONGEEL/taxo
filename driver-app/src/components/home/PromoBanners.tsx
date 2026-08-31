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

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { PromoBanner } from "@/api/types";
import * as icons from "lucide-react";

/** **أيقونةٌ زخرفيّةٌ كبيرةٌ في الطرف** — كما يرسمها التصميم (`heart` خلف
 *  عرضِ الخصم النسائيّ). */
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

/** **صورةُ اللافتة — بايتاتٌ أو لا شيء** (الترحيلة `0064`).
 *
 * **ولا حقلَ `has_image` في الخلفية**: الطلبُ نفسُه هو الجواب — وحقلٌ ثانٍ
 * يقول «لها صورة» بيتٌ ثانٍ للحقيقة يفترق عن الملفّ أوّلَ رفعٍ أو نزع. وهي
 * قاعدةُ `DriverAvatar` نفسُها.
 *
 * **وكان مكتوباً هنا «ولا صورةَ تُرفع: لا بابَ يخدمها»** — وكان صحيحاً في
 * حينه: العمودُ نُزع في 2026-08-30 لأنه بلا رافعٍ ولا خادم، **والحمولةُ تنشر
 * عنواناً لمسارٍ لا وجودَ له فيرسم التطبيقُ صورةً مكسورة**. وعاد في 08-31
 * **بالأربعة معاً**: العمودُ والرفعُ والبابُ وهذا العرض.
 *
 * **ولا `<img src>` مباشرة**: البابُ يسأل عن الجلسة والسوق، **و`<img>` لا
 * يحمل ترويسة** — فتُجلب بالمفتاح وتُعرض من `blob:`.
 */
function BannerImage({ bannerId }: { bannerId: string }) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    api
      .blob(`/storefront/banners/${bannerId}/image`)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      // **الفشلُ هو الحالُ العادية لا عطب**: أكثرُ اللافتات بلا صورة
      .catch(() => undefined);

    return () => {
      cancelled = true;
      // **ويُحرَّر العنوان** — وإلا حجزت كلُّ فتحةٍ نسخةً في الذاكرة
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [bannerId]);

  if (!src) return null;
  // **وصفٌ فارغٌ بقصد**: العنوانُ مكتوبٌ تحتها، ووصفٌ يكرّره يجعل قارئَ
  // الشاشة يقوله مرتين
  return <img src={src} alt="" className="block w-full object-cover" />;
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
        className={`mb-8 overflow-hidden rounded-16 border border-line bg-surface-2 ${
          openable ? "pressable cursor-pointer" : ""
        }`}
      >
        {/* **الصورةُ من حافةٍ إلى حافة** — والحشوةُ نزلت إلى الداخل لأجلها،
            فبطاقةٌ بلا صورةٍ تبقى كما كانت حرفاً */}
        <BannerImage bannerId={banner.id} />
        <div className="p-14">
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
