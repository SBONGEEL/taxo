/** **علاماتُ الخريطة في تطبيق الكبتن** — سيارتُه هو، وزملاؤه حوله.
 *
 * **ولمَ هنا لا في `MapView`**: العلامةُ عنصرُ DOM تُبنى بيدٍ (mapbox يملك
 * العنصرَ الخارجيَّ ويكتب صنفَه عليه، فما نكتبه نحن قد يُهزَم) — وبناؤها
 * منطقٌ خالصٌ يقرؤه `check:readers`، لا رسمٌ في JSX.
 *
 * **وقاعدةُ الشكل الثالثَ عشر تحكم هذا الملف كلَّه**: ما يُرسم بلا اتجاهٍ
 * يُرسم **بالشكل نفسِه** المرسومِ به مع اتجاه — لا مثلثٌ لمن لا يبثّ اتجاهه
 * ولا دائرةٌ لمن لا مركبةَ له. شكلٌ ثانٍ **يُعدّ من الخارج** فيصير علامةً
 * على فئة، وهو بعينه ما أُصلح في «عطب الإعفاء».
 */

import { markerPx, skinAssetUrl } from "@/lib/skins";
import type { VehicleSkin } from "@/api/types";

/** ظلٌّ واحدٌ لكلِّ علامةٍ على الخريطة — فلا تختلف رسمةٌ عن أختها بارتفاعها. */
const SHADOW = "drop-shadow(0 1px 3px rgb(0 0 0 / 0.45))";

/** **السيارةُ العامّة** — منقولةٌ بحرفها من `customer-app/components/map`.
 *
 * والنسخُ مقصود: زميلُ الكبتن يجب أن يُرسم **بالرسمة التي يرى بها الراكبُ
 * كبتنَه بالضبط**، فالمجهَّلُ واحدٌ في التطبيقين. ونسختان تفترقان أوّلَ تعديل،
 * فمن عدّل هنا يعدّل هناك — وهي قاعدةُ `BottomNav` نفسُها في هذا المشروع.
 *
 * **وألوانُها رموزُ اللوحة** (`--tx`/`--inv`) لا قيمٌ ستّ عشريّة: لونٌ ثابتٌ
 * يذوب في إحدى السمتين مهما حُسن اختيارُه.
 */
export function carElement(px: number, muted = false): HTMLElement {
  const element = document.createElement("div");
  const fill = muted ? "var(--mut)" : "var(--tx)";
  element.innerHTML = `
    <svg width="${px}" height="${px}" viewBox="0 0 24 24" aria-hidden="true"
         style="filter: ${SHADOW}">
      <g fill="${fill}" stroke="var(--inv)" stroke-width="0.7">
        <rect x="4.2" y="1.6" width="2.1" height="4.4" rx="0.9"/>
        <rect x="17.7" y="1.6" width="2.1" height="4.4" rx="0.9"/>
        <rect x="4.2" y="18" width="2.1" height="4.4" rx="0.9"/>
        <rect x="17.7" y="18" width="2.1" height="4.4" rx="0.9"/>
        <path d="M12 1.2c-2.4 0-4.1 1.1-4.6 3.2l-.7 3.3c-.3 1.5-.4 3-.4 4.3
                 0 2.5.2 5 .6 7.4.2 1.4 2.1 2.4 5.1 2.4s4.9-1 5.1-2.4c.4-2.4
                 .6-4.9.6-7.4 0-1.3-.1-2.8-.4-4.3l-.7-3.3C16.1 2.3 14.4 1.2 12 1.2Z"/>
      </g>
      <path d="M8.6 6.6c.5-1.1 1.7-1.7 3.4-1.7s2.9.6 3.4 1.7l.5 1.6c-1.2-.5-2.5-.7-3.9-.7
               s-2.7.2-3.9.7Z" fill="var(--inv)" opacity="0.85"/>
    </svg>`;
  element.style.willChange = "transform";
  if (muted) element.style.opacity = "0.55";
  return element;
}

/** ما تُرسم به سيارةُ الكبتن على خريطته هو. */
export interface SelfMarker {
  /** المركبةُ النشطة — و`null` تعني «لا مركبةَ مفعَّلة»، فتُرسم العامّة. */
  skin: VehicleSkin | null;
  /** **لا اشتراكَ له**: تُرسم رماديةً باهتةً مكانَها، ومعها سطرُ الاشتراك. */
  subscribed: boolean;
}

/** **علامةُ الكبتن على خريطته هو — ولا تُنشر لأحد.**
 *
 * تُبنى من حاله عنده (`GET /vehicle-skins/garage` واشتراكِه) لا من نداءٍ
 * يعلن للشبكة أن فلاناً بلا اشتراك، **ولا تغيّر شرطَ الأهلية ولا ما يصل
 * الراكب**: تجهيلُ §10 يبقى كما هو، والراكبُ لا يرى من هذه شيئاً.
 *
 * **والرماديّةُ حالُ حسابٍ لا وشايةٌ بفئة**: يراها صاحبُها وحدَه على شاشته،
 * فلا يُعَدّ من الخارج شيء.
 */
export function selfMarkerElement({ skin, subscribed }: SelfMarker): HTMLElement {
  if (!subscribed || skin === null) {
    // **الشكلُ واحدٌ في الحالين واللونُ يفترق**: من لا اشتراكَ له ومن لا
    // مركبةَ مفعَّلةً له يريان السيارةَ نفسَها — وما يقول الفرقَ سطرُ
    // الاشتراك على الشاشة، لا شكلٌ ثانٍ يُخمَّن معناه
    return carElement(markerPx(100), !subscribed);
  }
  const px = markerPx(skin.map_scale_percent);
  const element = document.createElement("div");
  const image = document.createElement("img");
  image.src = skinAssetUrl(skin.map_image_url);
  image.alt = "";
  image.width = px;
  image.height = px;
  image.style.width = `${px}px`;
  image.style.height = `${px}px`;
  // **`contain` لا `cover`**: رسمةٌ غيرُ مربّعةٍ تُقصّ بـ`cover` فتُبتر مقدّمةُ
  // السيارة — والمقاسُ ثابتٌ في الكود، فالاحتواءُ هو ما يحترمه
  image.style.objectFit = "contain";
  image.style.display = "block";
  image.style.filter = SHADOW;
  element.appendChild(image);
  element.style.willChange = "transform";
  return element;
}

/** **الاتجاه** — و`null` يُرسم كالصفر تماماً: الشكلُ نفسُه والمقاسُ نفسُه.
 *
 * **و`rotate` لا `transform`**: mapbox يكتب `transform` على العنصر في كل
 * إطار، فالكتابةُ فيه سباقٌ يُمحى — وخاصيّةُ `rotate` مستقلّةٌ عنه.
 *
 * **ولا يدور ما صُرِّح ألّا يدور** (`map_rotates`): الرندرُ الواقعيُّ يُعرض
 * ثابتاً، **وذلك يُقرأ من العقد لا من الندرة** — استنتاجُه من الندرة يجعل
 * أوّلَ استثناءٍ يقرّره المشرفُ سيارةً تدور وهي مرسومةٌ بمنظورٍ ثابت.
 */
export function applyMarkerHeading(
  element: HTMLElement,
  heading: number | null | undefined,
  rotates: boolean,
): void {
  element.style.rotate = rotates ? `${heading ?? 0}deg` : "0deg";
}
