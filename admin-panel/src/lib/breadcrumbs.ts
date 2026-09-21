/** فُتاتُ ما قبل العطب — **ما كان يفعله، لا ما انكسر** (٢٠٢٦-٠٩-٢١).
 *
 * أثرُ المكدَّس يقول **أين** انكسر، ولا يقول **ماذا كان يحاول**. وهذا الملفُّ
 * يمسك الخطواتِ القليلةَ السابقة — تنقّلاً بين الشاشات، ونداءاتِ الخلفية
 * بأفعالها وحالاتها — فيصير سؤالُ «كيف وصل إلى هنا» مقروءاً بدل أن يُخمَّن.
 *
 * ## وحدةٌ بلا مستوردات — **وهي قاعدةُ `request-id.ts` نفسُها**
 *
 * `crash-reports` يستورد `api/endpoints`، و`endpoints` يستورد `api/client`.
 * **فلو أمسك العميلُ الفُتاتَ عبر `crash-reports` لصارت الدورةُ ثلاثيّة** —
 * وهي بعينها العلّةُ التي أنشأت `request-id.ts` وحدةً مستقلّة. **وحدةٌ لا
 * تستورد أحداً لا تُدخِل أحداً في دورة**، ويقرأ منها الطرفان.
 *
 * ## وما لا يُجمع — وهو أهمُّ ما في الملفّ
 *
 * **لا أجسامَ طلبٍ ولا ردّ، ولا سلاسلَ استعلام، ولا رؤوس.** يُمسَك **الفعلُ
 * وقالبُ المسار والحالة** لا غير. وجسمُ الطلب هو موضعُ الرقم والمبلغ
 * والإحداثيّة، **وسلسلةُ الاستعلام تحمل المُعرِّفاتِ في العادة** — وكلاهما
 * يعيد من الباب الخلفيِّ ما نفاه `schemas/error_report.py` من الباب الأمامي.
 *
 * **والمسارُ يُقنَّع هنا قبل أن يُرسَل**، ويُقنَّع في الخادم ثانيةً
 * (`core/scrub.py::safe_route`). **وطبقتان ليستا تكراراً**: هذه تمنع المُعرِّفَ
 * أن يغادر الجهاز، وتلك تحرس عميلاً لم يُقنِّع.
 *
 * ## والطابعُ الزمنيُّ **بالثانية لا بالملّي** — وهذا مقيسٌ لا ذوق
 *
 * `toISOString()` يعطي `2026-09-21T04:18:58.314Z`، **ونمطُ المال في الخادم**
 * (`\d+\.\d{3}` — صيغةُ `NUMERIC(12,3)`) **يبتلع `58.314`** فيصل الطابعُ
 * `2026-09-21T04:18:«مبلغ»Z`. قِيس بالنمط نفسِه قبل الكتابة، **فحُذفت
 * الملّي**: دقّةُ الثانية تكفي فُتاتاً، **وطابعٌ ممسوخٌ لا يكفي شيئاً**.
 *
 * **وهي عائلةُ «حارسٌ صادقٌ يصيح على سليم»**: النمطُ صحيحٌ في موضعه، والعلّةُ
 * أن يُمرَّر عليه ما لا يشبه المال إلا شكلاً.
 */

/** خطوةٌ واحدةٌ قبل العطب. ومفاتيحُها **مُصرَّحةٌ في الخادم** أيضاً
 *  (`core/scrub.py::_CRUMB_KEYS`) — وما ليس فيها يُسقَط هناك. */
export type Crumb = {
  /** ISO **بالثانية** — انظر رأسَ الملفّ */
  at: string;
  kind: "route" | "api";
  route?: string;
  method?: string;
  path?: string;
  status?: number;
};

/** **عشرون** — والخادمُ يقصّ عند العدد نفسِه (`_MAX_CRUMBS`)، فلا يُرسَل ما
 *  يُرمى. وطابورٌ بلا سقفٍ في صفحةٍ تعمل ساعاتٍ يصير تسريبَ ذاكرة. */
const MAX_CRUMBS = 20;

/** مقاسُ المسار — والخادمُ يقصّ عند المقاس نفسِه (`_CRUMB_TEXT_LIMIT`). */
const MAX_PATH = 200;

/** **لا يُسجَّل بابُ التبليغ نفسُه** — وإلا صار كلُّ تقريرٍ يولّد فُتاتاً
 *  يظهر في التقرير الذي يليه، فيُقرأ سلوكُ المستخدم وفيه أثرُ المراقِب. */
const SELF_PATH = "/telemetry/errors";

const buffer: Crumb[] = [];

/** يُقنِّع كلَّ ما يشبه مُعرِّفاً في مسار — **بيتٌ واحدٌ يقرأ منه الاثنان**.
 *
 * والنمطُ هو نمطُ `core/scrub.py::_PATH_SEGMENT` حرفاً بحرف: ثماني خاناتٍ
 * ستّ عشريّةٍ فأكثر (UUID أو ما يشبهه)، أو عددٌ صرف.
 */
export function maskPath(pathname: string): string {
  return pathname
    .split("/")
    .map((part) => (/^[0-9a-fA-F-]{8,}$|^\d+$/.test(part) ? ":id" : part))
    .join("/")
    .slice(0, MAX_PATH);
}

/** الآنَ بالثانية — **بلا ملّي**، انظر رأسَ الملفّ. */
function stamp(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function push(crumb: Crumb): void {
  buffer.push(crumb);
  // **يُقصّ من رأسه**: الأحدثُ هو ما يُشخَّص به، والأقدمُ يسقط أوّلاً
  if (buffer.length > MAX_CRUMBS) buffer.splice(0, buffer.length - MAX_CRUMBS);
}

/** تنقّلٌ إلى شاشة — **ولا يُسجَّل ما لم يتغيّر**.
 *
 * موجّهاتُ React تكتب التاريخَ مرّاتٍ للشاشة الواحدة (استبدالٌ بعد تحميل،
 * ومَزامنةُ معاملات)، **فعشرون فُتاتاً تمتلئ بشاشةٍ واحدةٍ مكرَّرة** ولا
 * يبقى فيها ما سبقها — وهو بالضبط ما بُنيت لتحمله.
 */
export function noteRoute(route: string): void {
  const last = [...buffer].reverse().find((crumb) => crumb.kind === "route");
  if (last?.route === route) return;
  push({ at: stamp(), kind: "route", route: route.slice(0, MAX_PATH) });
}

/** نداءُ خلفيةٍ — **الفعلُ والقالبُ والحالة، لا غير**. */
export function noteApi(method: string, path: string, status: number): void {
  if (path.startsWith(SELF_PATH)) return;
  push({
    at: stamp(),
    kind: "api",
    method: method.toUpperCase().slice(0, 10),
    path: maskPath(path),
    status,
  });
}

/** ما جُمع حتى الآن — نسخةٌ، **فلا يُعدَّل الطابورُ من خارجه**. */
export function recentCrumbs(): Crumb[] {
  return buffer.slice();
}

let watching = false;

/** يُركَّب مرّةً عند الإقلاع — **ويُمسك التنقّلَ من طرفيه**.
 *
 * `pushState`/`replaceState` لِما يفعله الموجِّه، و`popstate` لزرِّ الرجوع في
 * المتصفّح — **وزرُّ الرجوع وحدَه لا يمرّ بالأوّلين**، فمن يكتفي بهما يعمى عن
 * أكثرِ ما يفعله الناسُ حين تتعطّل شاشة.
 *
 * **والتغليفُ يُعيد ما يُعيده الأصلُ ولا يبتلع رميةً**: مُراقِبٌ يكسر التنقّلَ
 * أسوأُ بكثيرٍ من مُراقِبٍ لا يرى.
 */
export function watchRoutes(): void {
  if (watching) return;
  watching = true;

  const note = (): void => {
    try {
      noteRoute(maskPath(window.location.pathname));
    } catch {
      /* لا شيءَ يسقط بسبب فُتات */
    }
  };

  note();

  for (const name of ["pushState", "replaceState"] as const) {
    const original = history[name];
    history[name] = function patched(
      this: History,
      ...args: Parameters<History["pushState"]>
    ): void {
      const result = original.apply(this, args);
      note();
      return result;
    };
  }

  window.addEventListener("popstate", note);
}
