/** معاينةُ المركبة **على قطعةِ خريطةٍ حقيقيةٍ بالحجم النهائي** — قبل الحفظ.
 *
 * **ولمَ خريطةٌ حقيقيةٌ لا مربّعٌ مخطَّط**: السؤالُ الذي يجيب عنه هذا اللوحُ
 * هو «أتُقرأ هذه المركبةُ وسط ما على الخريطة؟» — وجوابُه يعتمد على **ما
 * تحتها**: أسفلتٌ رماديٌّ يبتلع سيارةً رمادية، وسمةٌ فاتحةٌ تبتلع فاتحة.
 * فمربّعٌ محايدٌ تحتها يجعل كلَّ رسمةٍ تبدو مقروءة، **وهو أسوأُ من ألّا
 * تُعاين أصلاً**: يعطي طمأنينةً لا يقابلها قياس.
 *
 * **وبالحجم النهائي لا مكبَّرةً**: العلامةُ ٣٠ بكسل CSS — ٧٫٧٪ من عرض هاتفٍ
 * ٣٩٠ — ورسمةٌ تُقرأ عند ٢٠٠ بكسل قد تصير بقعةً عند ٣٠. **والحجمُ يُقاس ولا
 * يُقدَّر**، وهو شرطُ المالك في كنس ألوان الخريطة.
 *
 * **ومعها علاماتٌ أخرى** — وهذا نصفُ الغرض: مركبةٌ تُقرأ وحدَها على شاشةٍ
 * فارغةٍ قد تذوب بين خمسٍ غيرِها. فتُرسم إلى جانبها مركباتُ الكتالوج التي
 * لها رسمة، **ونبضةُ موقعِ الراكب ودبّوسُ وجهته** — لأن خريطةَ الراكب تحمل
 * الثلاثةَ معاً دائماً، وعدُّ العلامات كذبَ مرتين في جلسةٍ واحدةٍ في هذا
 * المشروع لأنها لم تُميَّز بمحتواها.
 *
 * **والسحّابُ ٨٠–١٢٠٪ يُحفظ مع المركبة** (`map_scale_percent`): توليداتٌ
 * مختلفةٌ تملأ إطارَها بنسبٍ مختلفة، فالقصُّ الآليُّ يوحّد الإطارَ **ولا
 * يوحّد ما بداخله** — والباقي حكمُ عينٍ على خريطة، وهو ما يوجد هذا السحّابُ
 * له. وحدَّاه في القاعدة أيضاً (`CHECK`)، فلا يفتح هذا اللوحُ ما تمنعه.
 *
 * **وبلا توكن Mapbox** (عقدٌ غيرُ مفعَّل) يبقى السحّابُ والحجمُ المقيسُ
 * ويظهر مكانَ الخريطة سببٌ مكتوب — فالمعاينةُ تفقد نصفَها ولا تختفي.
 */

import mapboxgl from "mapbox-gl";
import { useEffect, useMemo, useRef } from "react";

import "mapbox-gl/dist/mapbox-gl.css";

// **تشكيلُ العربية قبل إنشاء الخريطة** — للوحدة أثرٌ جانبيٌّ (تسجيلُ الملحق)
// **يقع باستيراد الاسم كما يقع بالاستيراد المجرَّد**: الوحدةُ تُقيَّم مرّةً
// عند أوّل استيرادٍ أياً كانت صيغتُه، فيسبق كلَّ `new mapboxgl.Map` هنا.
import { MAP_LANGUAGE } from "@/lib/map-rtl";

import { useTheme } from "@/lib/theme";

const STYLE_LIGHT = "mapbox://styles/mapbox/streets-v12";
const STYLE_DARK = "mapbox://styles/mapbox/dark-v11";

/** **مقاسُ علامة الكبتن على خريطة الراكب** — ٣٠ بكسل CSS.
 *
 * والرقمُ ليس ذوقاً: هو ما يُرسم به في التطبيقين، فمعاينةٌ بغيره تعاين شيئاً
 * آخر. وتغييرُه هنا وحدَه يجعل هذا اللوحَ **يكذب بصدق** — يعرض بدقّةٍ حجماً
 * لا يقع.
 */
export const MARKER_BASE_PX = 30;

/** مواضعُ العلامات المرافقة — عمّان، وثابتةٌ فلا تقفز بين إعادتَي رسم. */
const CENTER: [number, number] = [35.9106, 31.9539];
const NEIGHBOURS: [number, number][] = [
  [35.9078, 31.9562],
  [35.9139, 31.9521],
  [35.9121, 31.9573],
  [35.9065, 31.9514],
];

interface Props {
  /** رسمةُ الخريطة — `blob:` أو `data:`. و`null` قبل اختيار ملفّ. */
  mapImage: string | null;
  /** نسبةُ العرض ٨٠–١٢٠ — تُحفظ مع المركبة. */
  scalePercent: number;
  onScaleChange: (next: number) => void;
  /** رسوماتُ مركباتٍ أخرى في الكتالوج — **لتُقرأ هذه بينها**. */
  neighbours?: string[];
  token: string | null;
  rotates: boolean;
}

function shell(): HTMLElement {
  const node = document.createElement("div");
  node.appendChild(document.createElement("span"));
  return node;
}

export function SkinMapPreview({
  mapImage,
  scalePercent,
  onScaleChange,
  neighbours = [],
  token,
  rotates,
}: Props) {
  const holder = useRef<HTMLDivElement | null>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const subject = useRef<mapboxgl.Marker | null>(null);
  const extras = useRef<mapboxgl.Marker[]>([]);
  const { dark } = useTheme();

  const size = Math.round((MARKER_BASE_PX * scalePercent) / 100);

  /** **الحجمُ يُقاس ولا يُقدَّر** — والقياسُ يُعرض للمشرف لا يُخبَّأ.
   *
   * **والمليمترُ مشتقٌّ من قياسٍ وقع في هذا المشروع**، لا من كثافةٍ مفترضة:
   * ثلاثون بكسل CSS قُيست ≈ 5.7 مم على الجهاز. فالنسبةُ خطّيّةٌ منها، ولا
   * يُخترع رقمُ نقاطٍ في البوصة لا أحدَ قاسه.
   */
  const measured = useMemo(() => {
    const share = ((size / 390) * 100).toFixed(1);
    const millimetres = ((size / 30) * 5.7).toFixed(1);
    return { share, device: size * 3, millimetres };
  }, [size]);

  useEffect(() => {
    if (!token || !holder.current || map.current) return;
    mapboxgl.accessToken = token;
    map.current = new mapboxgl.Map({
      container: holder.current,
      style: dark ? STYLE_DARK : STYLE_LIGHT,
      language: MAP_LANGUAGE,
      center: CENTER,
      zoom: 15.4,
      attributionControl: false,
    });
    return () => {
      map.current?.remove();
      map.current = null;
    };
    // السمةُ تُبدَّل في أثرٍ منفصل — إعادةُ البناء عليها تُفقد الموضع
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    map.current?.setStyle(dark ? STYLE_DARK : STYLE_LIGHT);
  }, [dark]);

  // **العلامةُ تُحدَّث ولا تُعاد** — قاعدةُ `LiveCanvas` نفسُها: إعادةُ بنائها
  // مع كلِّ حركةِ سحّابٍ تُومض الخريطةَ تحت يد المشرف
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;

    if (!subject.current) {
      subject.current = new mapboxgl.Marker({ element: shell() })
        .setLngLat(CENTER)
        .addTo(instance);
    }
    const face = subject.current.getElement()
      .firstElementChild as HTMLElement;
    face.style.display = "block";
    face.style.width = `${size}px`;
    face.style.height = `${size}px`;
    // **الدورانُ يُعاين أيضاً**: علامةٌ تدور حول نقطةٍ خارجَ السيارة تقفز،
    // ولا يُرى ذلك في رسمةٍ ساكنة
    face.style.transform = rotates ? "rotate(124.9deg)" : "none";
    face.innerHTML = "";
    if (mapImage) {
      const image = document.createElement("img");
      image.src = mapImage;
      image.width = size;
      image.height = size;
      image.alt = "";
      image.style.display = "block";
      face.appendChild(image);
    } else {
      face.style.borderRadius = "99px";
      face.style.border = "2px dashed currentColor";
      face.style.opacity = "0.5";
    }
  }, [mapImage, size, rotates, token]);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    for (const marker of extras.current) marker.remove();
    extras.current = [];
    NEIGHBOURS.forEach((position, index) => {
      const node = shell();
      const face = node.firstElementChild as HTMLElement;
      face.style.display = "block";
      face.style.width = `${MARKER_BASE_PX}px`;
      face.style.height = `${MARKER_BASE_PX}px`;
      const art = neighbours[index];
      if (art) {
        const image = document.createElement("img");
        image.src = art;
        image.width = MARKER_BASE_PX;
        image.height = MARKER_BASE_PX;
        image.alt = "";
        image.style.display = "block";
        image.style.transform = `rotate(${index * 67}deg)`;
        face.appendChild(image);
      } else {
        // **نبضةٌ ودبّوسٌ لا سيارتان**: خريطةُ الراكب تحمل موقعَه ووجهتَه
        // دائماً، فمعاينةٌ بلا هما تعاين خريطةً لا وجودَ لها
        face.style.borderRadius = index % 2 ? "3px" : "99px";
        face.style.width = index % 2 ? "12px" : "16px";
        face.style.height = index % 2 ? "12px" : "16px";
        // **قيمةٌ ست عشريةٌ هنا تنجو من كلِّ كنس**: `check:scale` يقرأ أصنافَ
        // Tailwind، وهذه أنماطُ DOM. **وهي CSS فعلاً** — بخلاف `paint` في
        // mapbox — فتقرأ اللوحةَ بمتغيّرها وتتبعها بلا نسخة
        face.style.background = index % 2 ? "var(--dng)" : "var(--ok)";
        // والهالةُ ثابتةٌ بقصد: حدُّها يفصل العلامةَ عن الأسفلت في السمتين،
        // ولونٌ يتبع السمةَ يذوب في إحداهما — وهي قاعدةُ خطِّ المسار مقلوبة
        face.style.boxShadow = "0 0 0 4px rgba(255,255,255,.35)";
      }
      extras.current.push(
        new mapboxgl.Marker({ element: node }).setLngLat(position).addTo(instance),
      );
    });
  }, [neighbours, token]);

  return (
    <div>
      <div className="overflow-hidden rounded-14 border border-line">
        {token ? (
          <div ref={holder} className="h-170 w-full" />
        ) : (
          <div className="flex h-170 items-center justify-center bg-stripe px-20 text-center text-11.5 leading-note text-muted">
            عقدُ Mapbox غيرُ مفعَّل، فلا خريطةَ تحت المركبة — والسحّابُ يعمل،
            لكنّ الحكمَ على «أتُقرأ بين العلامات؟» يحتاج ما تحتها.
          </div>
        )}
      </div>

      <div className="mt-12 flex items-center gap-12">
        <span className="w-82 shrink-0 text-11.5 text-muted">نسبة العرض</span>
        <input
          type="range"
          min={80}
          max={120}
          step={1}
          value={scalePercent}
          aria-label="نسبة عرض المركبة على الخريطة"
          onChange={(event) => onScaleChange(Number(event.target.value))}
          className="h-4 flex-1 accent-ink"
        />
        <span className="w-52 shrink-0 text-end text-12.5 font-bold text-ink">
          {scalePercent}%
        </span>
      </div>

      {/* **يُقاس ولا يُقدَّر** (شرطُ المالك): والمقيسُ يُعرض، فمن يحرّك
          السحّابَ يعرف ماذا حرّك — لا «أكبرُ قليلاً» */}
      <p className="mt-8 text-11 leading-note text-muted">
        {size} بكسل CSS · {measured.device} بكسلَ جهازٍ عند 3x ·{" "}
        {measured.share}% من عرض شاشةٍ 390 · ≈{measured.millimetres} مم
        (مشتقٌّ من قياس 30 بكسل ≈ 5.7 مم).
        <br />
        ولا يُقرأ الحجمُ من المستطيل المحيط: مربّعٌ بزاوية 124.9° محيطُه
        يتجاوز ضلعَه بنحو 39% — وذلك حجمُ الالتفاف لا حجمُ الأيقونة.
      </p>
    </div>
  );
}
