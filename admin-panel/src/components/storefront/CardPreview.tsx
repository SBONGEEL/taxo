/** المعاينة — **بالبطاقة نفسِها التي يرسمها التطبيق، لا بتقريبٍ لها**.
 *
 * **ولمَ معاينةٌ أصلاً**: المشرفُ يكتب عنواناً ويختار أيقونةً **ولا يرى ما
 * سيراه صاحبُ الهاتف** حتى يفتح التطبيق — فعنوانٌ يفيض على سطرين، أو أيقونةٌ
 * لا تناسب، **لا يُكتشفان إلا بعد الإشعال**، وقد رآهما الناسُ قبله.
 *
 * ## وثلاثةُ أشياءَ في هذا الملفّ مقصودةٌ ولا تُبسَّط
 *
 * **١) نسخةٌ لا استيراد.** الشبكةُ في التطبيقين تعيش داخل `react-router`
 * (تنادي `useNavigate`) وتقرأ أنواعَ التطبيق — **واستيرادُها هنا يجرّ الموجّه
 * وشجرتَه إلى اللوحة**. فهي منسوخةٌ بأصنافها حرفاً بحرف، **والسلّمُ واحدٌ في
 * الثلاثة** (`tailwind.config.js` نسخةٌ حرفيّةٌ من `DESIGN.md` §6) فالنسخُ
 * يعطي الشكلَ نفسَه لا شبيهاً به.
 *
 * **٢) والنسخةُ تُحرَس لا تُؤتمَن.** نسختان تفترقان أوّلَ تعديل — **فتصير
 * المعاينةُ تَعِد بما لا يقع**، وهو أسوأُ من لا معاينة. `tools/check-storefront-card.mjs`
 * يبصم بطاقتَي التطبيقين ويقابلهما بـ`CARD_FINGERPRINT` أدناه، **فمن غيّر
 * البطاقةَ هناك يقف هنا**.
 *
 * **٣) والصورةُ تُطلب ولا يُسأل عنها بحقل**: بايتاتٌ أو ٤٠٤ — وحقلٌ يقول «لها
 * صورة» بيتٌ ثانٍ للحقيقة يفترق عن الملفّ أوّلَ رفعٍ أو نزع.
 */

import { useEffect, useState } from "react";

import { bannerImageBlob } from "@/api/endpoints";
import type { PromoBannerRow, ServiceTileRow } from "@/api/types";
import { Glyph } from "@/components/storefront/IconPicker";

/** **بصمةُ بطاقتَي التطبيقين** — يقرؤها `check:storefront-card` ويقارن.
 *
 * **وحدُّها مكتوب**: هي تُثبت أن **أحداً لم يغيّر البطاقةَ هناك دون أن يقف
 * هنا** — **ولا تُثبت أن الشكلين متطابقان في العين**. التطابقُ البصريُّ يُقاس
 * بفتح الاثنين، والبصمةُ تضمن أن يُفتحا.
 *
 * **وتغيّرت في ٢٠٢٦-٠٩-١٩ ولم يتغيّر وجهُ البطاقة**: أُضيف السحبُ والدورانُ
 * إلى الصندوق، **ووجهُ الشريحة الواحدة هو هو حرفاً** — والمعاينةُ تعرض لافتةً
 * واحدةً ساكنة، **وهي بعينها ما يرسمه التطبيقُ لشريحةٍ واحدة**. فلم يُنقل
 * إليها شيء، **والحركةُ لا تُعايَن هنا بقصد**.
 */
export const CARD_FINGERPRINT = "96899bdef9f0e8cd";

/** ## ولمَ لا معاينةَ لشريحة عرض الاشتراك (2026-09-07)
 *
 * صارت بطاقةُ التطبيق **شريحتين في صندوقٍ واحد**: صفُّ لافتةٍ يكتبه المشرف،
 * **وعرضُ اشتراكٍ يُحسب لكلِّ كبتنٍ على حدة**. والأولى تُعاين هنا، والثانية
 * **لا تُعاين ولا تُبنى لها معاينةٌ بقصد**:
 *
 * **المعاينةُ تحتاج الرقمَ لتكون معاينة** — «25.000 مشطوباً بجانب 20.000» —
 * **واللوحةُ لا تملك حسابَه**: السعرُ بعد الخصم يُحسب في الخلفية وحدَها (§14)،
 * **وحسابُه هنا في المتصفح** يخالف القاعدةَ ويوقفه `check:money-math`.
 * **ومعاينةٌ برقمٍ محسوبٍ في اللوحة تفترق عمّا يراه الكبتنُ أوّلَ سقفِ خصمٍ
 * أو تقريب** — وهي «معاينةٌ تَعِد بشكلٍ لا يقع» التي بُني لها هذا الحارسُ
 * نفسُه.
 *
 * **فالشكلُ الذي يُضمن هنا شكلُ اللافتة**، والعرضُ يُقاس بفتح تطبيق الكبتن.
 * **والبصمةُ تشمل الشريحتين معاً** — فمن غيّر بطاقةَ العرض يقف هنا أيضاً
 * ويقرأ هذا السطر.
 */

// ═══════════════════════════════════ بلاطاتُ الخدمات — نسخةُ `ServiceTiles.tsx`

export function TilesPreview({ tiles }: { tiles: ServiceTileRow[] }) {
  if (tiles.length === 0) return null;
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="mb-12 grid grid-cols-3 gap-8">
      {tiles.map((tile) => (
        <div
          key={tile.id}
          className="flex flex-col items-center gap-6 rounded-12 border border-line bg-surface px-5 pb-9 pt-11"
        >
          <Glyph name={tile.icon} className="size-21 text-ink" />
          <span className="text-11.5 font-medium text-ink">{tile.title}</span>
          {tile.status === "soon" ? (
            <span className="rounded-6 border border-line bg-surface-2 px-6 py-2 text-9.5 font-semibold text-warn">
              قريباً
            </span>
          ) : tile.new_until !== null && today <= tile.new_until ? (
            <span className="rounded-6 border border-brand-brd bg-brand-soft px-6 py-2 text-9.5 font-semibold text-brand">
              جديد
            </span>
          ) : tile.subtitle ? (
            <span className="text-9.5 text-muted">{tile.subtitle}</span>
          ) : null}
        </div>
      ))}
    </div>
  );
}

// ═════════════════════════════════ لافتاتُ المحتوى — نسخةُ `PromoBanners.tsx`

export function BannerPreview({ banner }: { banner: PromoBannerRow }) {
  const [image, setImage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    bannerImageBlob(banner.id)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setImage(url);
      })
      // **٤٠٤ هي الحالُ العادية** — لافتةٌ بلا صورةٍ ترسمها الأيقونة
      .catch(() => undefined);
    return () => {
      cancelled = true;
      // **ومن يفتحها يغلقها** — وإلا بقيت في ذاكرة التبويب
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [banner.id]);

  return (
    <div className="mb-8 overflow-hidden rounded-16 border border-line bg-surface-2">
      {image ? (
        <img src={image} alt="" className="block w-full object-cover" />
      ) : null}
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
  );
}

/** إطارٌ بعرض الهاتف — **فالبطاقةُ تُقاس في عرضها لا في عرض الشاشة**.
 *
 * **وعنوانٌ يسع في اللوحة يفيض في الهاتف**: العرضُ جزءٌ من الشكل، ومعاينةٌ
 * بعرض المكتب تُطمئن على ما سيُقطع.
 */
export function PhoneFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="w-device rounded-20 border border-line bg-surface p-16">
      <p className="mb-10 text-11 text-muted">
        كما تظهر في الهاتف — بعرض الجهاز نفسِه
      </p>
      {children}
    </div>
  );
}
