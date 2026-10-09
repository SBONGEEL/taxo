/** البابُ العامُّ وشارةُ المتجر — **يقرؤهما بيتان: الرئيسيةُ وصفحةُ التحميل**.
 *
 * **ونسخةٌ واحدةٌ لا اثنتان**: صفحتان تقرآن البابَ نفسَه بطريقين تفترقان أوّلَ
 * تعديل — إحداهما تبتلع الفشلَ والأخرى تُظهره، **فتقول الصفحتان شيئين عن
 * الإعداد الواحد**.
 */

const DOOR = "/api/site";
const BAKED = "/site.json";

/** إعداداتُ الصفحة من الباب — **والفشلُ صامت، وما لا يصل لا يُرسم**. */
export async function readDoor() {
  // **الحيُّ أوّلاً، والمخبوزُ احتياطٌ إن لم يُجب** — لا العكس: نداءٌ واحدٌ
  // ينتظره الإقلاع، **فما يُرسم هو ما يقوله البابُ الآن** لا نسخةُ البناء.
  // وثمنُه معلَن: لا شيءَ يُرسم من الباب قبل أن يجيب، **وما خُبز في HTML
  // يبقى ظاهراً حتى ذلك الحين**.
  try {
    const res = await fetch(DOOR, { cache: "no-store" });
    if (res.ok) return await res.json();
  } catch { /* الفشلُ صامت */ }
  try {
    const res = await fetch(BAKED, { cache: "no-store" });
    if (res.ok) return await res.json();
  } catch { /* والمخبوزُ قد يغيب في التطوير */ }
  return null;
}

/** **رابطُ متجرٍ يبدأ بـ`https://play.google.com/`** — والمخطَّطُ يفحصه عند الكتابة (§٥٢٫٥)، **وهذا يفحصه عند الرسم**:
 * زرٌّ يقول «Google Play» ويفتح غيرَه يكذب على من ضغطه، **ولو وصل الرابطُ من بابٍ لم يمرّ بالمخطَّط**. */
export function isStoreUrl(url) {
  return typeof url === "string" && /^https:\/\/play\.google\.com\//.test(url);
}

/** شارةُ Google Play الرسمية — **من ملفّ Google كما هو**.
 *
 * **ولا زرَّ مرسومٌ يحاكيها** (شرطُ المالك): الشارةُ ملفٌّ رسميٌّ بمساحته
 * الآمنة، **ورسمُ بديلٍ يشبهها مخالفةُ علامةٍ تجارية**.
 *
 * **والارتفاعُ من نسبة الملفّ لا مكتوبٌ بيد** (٦٤٦×٢٥٠): كان `180×53` فيُحجز
 * للشارة مكانٌ أقصرُ من رسمها ثمّ تقفز الصفحةُ حين تُحمَّل. والعرضُ وسيطٌ: ١٨٠
 * في صفحة التحميل، و٢٠٠ مكانَ الزرّ في وضع `play` على الرئيسية (W08).
 */
export function playBadge(href, label, width = 180) {
  const a = document.createElement("a");
  a.href = href;
  a.rel = "noopener";
  a.className = "play-badge";
  a.setAttribute("aria-label", label);
  a.style.cssText = "display:inline-block;margin-top:auto;min-height:44px";
  const img = document.createElement("img");
  img.src = "/assets/google-play-badge.png";
  img.alt = label;
  img.width = width;
  img.height = Math.round((width * 250) / 646);
  img.loading = "lazy";
  img.style.cssText = `display:block;width:${width}px;height:auto`;
  a.appendChild(img);
  return a;
}

/** سطرُ العلامة التجارية — **يذكر الشعارَ حين تُرسم الشارةُ لا قبلها**.
 *
 * الشارةُ الرسميةُ تحمل شعارَ Google Play، **والرابطُ النصّيُّ والشارةُ
 * المعطَّلةُ لا تحملانه** — وسطرٌ يقول «والشعار» تحتهما يُسند علامةً لم
 * تُعرض. فالمخبوزُ في الصفحتين يذكر الاسمَ وحدَه، **وهذا يضيف الشعارَ
 * حين تظهر شارةٌ واحدةٌ على الأقلّ**.
 */
export function trademark(line, withLogo) {
  if (!line) return;
  if (withLogo) {
    const ltr = (text) => {
      const span = document.createElement("span");
      span.dir = "ltr";
      span.style.unicodeBidi = "isolate";
      span.textContent = text;
      return span;
    };
    line.replaceChildren(
      ltr("Google Play"),
      " وشعارُ ",
      ltr("Google Play"),
      " علامتان تجاريتان لشركة ",
      ltr("Google LLC"),
      ".",
    );
  }
  line.hidden = false;
}
