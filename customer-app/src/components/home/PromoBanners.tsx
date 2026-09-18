/** صندوقُ الإعلانات — **لافتاتُ اللوحة وعرضُ الاشتراك في صندوقٍ واحد**.
 *
 * **والخانةُ نفسُها صارت بيتَ اللافتة** (قرارُ المالك 2026-08-30): يملؤها
 * المشرفُ من اللوحة **بدل أن يُخبز نصُّها** — فعرضُ الخصم النسائيِّ المرسوم
 * **نموذجٌ لا نصٌّ مخبوز**، ونزل صفّاً في الجدول.
 *
 * **ومصدرانِ لصندوقٍ واحدٍ لا كيانان** (قرارُ المالك 2026-09-07): صفوفُ
 * `promo_banners` التي يكتبها المشرف، **وعرضُ الاشتراك الحيُّ محسوباً لهذا
 * الكبتن**. **ولمَ لا يُصنع للعرض صفُّ لافتةٍ آليّاً**: جدولٌ نصفُه بيدٍ
 * ونصفُه بآلةٍ يراه المشرفُ فيحرّره **فيُمحى في الدورة التالية** — وهو
 * «بيتان لحقيقةٍ واحدة» بعينه. **والعرضُ يصل الصندوقَ بلا تعديل شيفرة**:
 * ما يُطلق من اللوحة يُحسب في الخلفية ويظهر.
 *
 * **والنافذةُ قيست في الخلفية**: ما يصل هنا حيٌّ الآن. **ولا تُقاس في
 * التطبيق** — ساعةُ الجهاز يملكها صاحبُه، **ولافتةٌ انتهت تبقى ظاهرةً لمن
 * أخّر ساعتَه**.
 *
 * **وحين يفرغ الصندوقُ يختفي كلُّه** — لا فراغٌ ولا هيكلٌ أبديّ: **المكانُ
 * الفارغُ يُقرأ عطباً في التحميل**، والهيكلُ الذي لا ينتهي يُقرأ شبكةً
 * منقطعة، **ولا سطرَ يُكتب مكانَه** لأن «لا إعلانَ اليوم» ليست خبراً يستحقّ
 * مساحةً في أوّل شاشةٍ يفتحها المستخدم. والبلاطاتُ تصعد مكانَه.
 *
 * **ويُسحب ويدور وحدَه** (قرارُ المالك ٢٠٢٦-٠٩-١٩ — كانت النقاطُ وحدَها تقلبه):
 * سحبٌ أفقيٌّ يقلب الشريحة، والعموديُّ يُترك لتمرير الرئيسية، **ولمسةٌ تحرّكت
 * لا تفتح رابطاً**. ويدور كلَّ خمس ثوانٍ ويعود إلى الأولى، **ويقف تحت الإصبع**
 * وفي تبويبٍ مخفيّ، **ولا يدور لمن طلب تقليلَ الحركة**. **وشريحةٌ واحدةٌ بطاقةٌ
 * ساكنة** — لا نقاطَ ولا دورانَ ولا سحب.
 *
 * **والنقاطُ تحتها من التصميم**: تظهر حين تتعدّد اللافتاتُ لا حين تكون
 * واحدة — **ونقطةٌ واحدةٌ تحت لافتةٍ واحدةٍ تَعِد بثانيةٍ لا وجودَ لها**.
 */

import {
  type PointerEvent as ReactPointerEvent,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { useReducedMotion } from "framer-motion";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { PromoBanner, StorefrontOffer } from "@/api/types";
import { currencyLabel, digits } from "@/lib/utils";
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

/** بطاقةُ عرض الاشتراك — **السعرُ المشطوب بجانب المخفَّض** كما في شاشة
 *  الاشتراك حرفاً، فيعرف الكبتنُ ما يراه من أوّل نظرة.
 *
 *  **ولا طرحَ هنا**: الرقمان يصلان محسوبين من الخلفية (§14). **و«مجاناً»
 *  كلمةٌ لا رقمُ صفر** — «0.000 د.أ» تُقرأ عطباً في السعر لا هديّة.
 *
 *  **والعنوانُ اسمُ العرض كما كتبه المشرف**، لا جملةً مؤلَّفةً في الشيفرة:
 *  ما يُطلق من اللوحة يظهر بنصّه. */
function OfferCard({ offer }: { offer: StorefrontOffer }) {
  return (
    <div className="p-14">
      <div className="flex items-start gap-10">
        <Glyph name="percent" className="size-44 shrink-0 text-line" />
        <div className="min-w-0 flex-1">
          <div className="text-14 font-bold text-ink">{offer.name}</div>
          <div className="mt-3 flex flex-wrap items-baseline gap-6 text-11.5 leading-note text-muted">
            <span>اشتراك «{offer.plan_name}»</span>
            <span className="whitespace-nowrap font-bold text-ink">
              <span className="me-6 font-medium text-muted line-through">
                {digits(offer.price)}
              </span>
              {offer.free ? (
                "مجاناً"
              ) : (
                <>
                  {digits(offer.price_after)}{" "}
                  <span className="text-11 font-medium text-muted">
                    {currencyLabel(offer.currency)}
                  </span>
                </>
              )}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

/** **ثوانٍ بين شريحةٍ وأخرى** — تكفي لقراءة العنوان، ولا تطول حتى يُظنّ
 *  الصندوقُ ساكناً. */
const ADVANCE_MS = 5000;

/** **ما دون هذا نقرةٌ لا سحب** — إصبعٌ يرتجف على الزجاج يتحرّك بكسلاتٍ ولا
 *  يقصد شيئاً، **ونقرةٌ تُقرأ سحباً تبتلع الرابط**. */
const SLOP_PX = 8;

/** **سحبٌ يتجاوز هذا الجزءَ من العرض يقلب الشريحة** — وما دونه يرتدّ. */
const PAGE_RATIO = 0.18;

type Slide = { key: string } & (
  | { kind: "offer"; offer: StorefrontOffer }
  | { kind: "banner"; banner: PromoBanner }
);

/** **وجهُ الشريحة وحدَه** — الحركةُ والنقرُ في الصندوق لا هنا.
 *
 *  **و`loadImage` يؤجّل الصورة**: الشريحةُ الحاليّةُ والتي تليها تُجلبان،
 *  **والباقي حين يقترب دوره** — ثلاثُ لافتاتٍ بصورها قرابةُ خمسة ميغابايت،
 *  **وراكبٌ فتح التطبيقَ ليطلب رحلةً لا يدفعها كلَّها في أوّل ثانية**. */
function SlideFace({ slide, loadImage }: { slide: Slide; loadImage: boolean }) {
  if (slide.kind === "offer") return <OfferCard offer={slide.offer} />;
  return (
    <>
      {/* **الصورةُ من حافةٍ إلى حافة** — والحشوةُ نزلت إلى الداخل لأجلها،
          فبطاقةٌ بلا صورةٍ تبقى كما كانت حرفاً */}
      {loadImage ? <BannerImage bannerId={slide.banner.id} /> : null}
      <div className="p-14">
        <div className="flex items-start gap-10">
          {slide.banner.icon ? (
            <Glyph name={slide.banner.icon} className="size-44 shrink-0 text-line" />
          ) : null}
          <div className="min-w-0 flex-1">
            <div className="text-14 font-bold text-ink">{slide.banner.title}</div>
            {slide.banner.body ? (
              <div className="mt-3 text-11.5 leading-note text-muted">
                {slide.banner.body}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </>
  );
}

/** **أتُنقر هذه الشريحة؟** — والعرضُ ينقر دائماً إلى شاشة الاشتراك. */
function isOpenable(slide: Slide): boolean {
  return (
    slide.kind === "offer" ||
    (slide.banner.link_kind !== "none" && slide.banner.link !== null)
  );
}

export function PromoBanners({
  banners,
  offer = null,
}: {
  banners: PromoBanner[];
  offer?: StorefrontOffer | null;
}) {
  const navigate = useNavigate();
  // **`prefers-reduced-motion` من مصدرِ Framer نفسِه** (§8) — ومن طلبه لا
  // تدور له الشرائحُ وحدَها، ولا تنزلق: تُقلب فوراً
  const reduceMotion = useReducedMotion() ?? false;

  const [at, setAt] = useState(0);
  // **أبعدُ شريحةٍ جُلبت صورتُها** — لا تنقص، فما جُلب لا يُعاد
  const [reach, setReach] = useState(1);
  // **إزاحةُ الإصبع بالبكسل** — و`null` تعني «لا سحب»، وبها يقف المؤقّت
  const [dragPx, setDragPx] = useState<number | null>(null);
  const [hidden, setHidden] = useState(() => document.hidden);
  // **اتجاهُ الصفحة يُقرأ لا يُفترض**: في RTL تقع الشريحةُ التاليةُ يساراً،
  // **فالإشارةُ تنقلب** — ومكوّنٌ يفترض LTR يسحب الراكبَ إلى الخلف
  const [dirSign, setDirSign] = useState(1);

  const viewport = useRef<HTMLDivElement>(null);
  const gesture = useRef<{
    id: number;
    x: number;
    y: number;
    axis: "x" | "y" | null;
  } | null>(null);
  // **سحبٌ جرى في هذه اللمسة** — فالنقرةُ التي تليها لا تفتح شيئاً
  const moved = useRef(false);

  // **العرضُ أوّلاً**: نافذتُه أقصرُ من نافذة اللافتة وأثرُه مالٌ في جيب
  // الكبتن — **ولافتةٌ تعلوه تدفعه إلى نقطةٍ لا تُنقر**
  const slides: Slide[] = [
    ...(offer ? [{ key: "offer", kind: "offer" as const, offer }] : []),
    ...banners.map((banner) => ({
      key: banner.id,
      kind: "banner" as const,
      banner,
    })),
  ];
  const count = slides.length;
  const current = Math.min(at, Math.max(count - 1, 0));
  // **شريحةٌ واحدةٌ ليست دوّاراً**: لا نقاط، ولا دوران، ولا سحب
  const carousel = count > 1;
  const dragging = dragPx !== null;

  useLayoutEffect(() => {
    if (viewport.current) {
      setDirSign(getComputedStyle(viewport.current).direction === "rtl" ? 1 : -1);
    }
  }, [carousel]);

  useEffect(() => {
    setReach((far) => Math.max(far, current + 1));
  }, [current]);

  // **تبويبٌ مخفيٌّ لا يدور** — وإلا عاد صاحبُه إلى شريحةٍ لم يختَرها
  useEffect(() => {
    const sync = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", sync);
    return () => document.removeEventListener("visibilitychange", sync);
  }, []);

  // **الدورانُ مؤقّتٌ واحدٌ يُعاد مع كلِّ قلب** — فشريحةٌ اختارها صاحبُها
  // بنقطةٍ أو سحبٍ تنال مهلتَها كاملة، **والسحبُ يوقفه حتى يُرفع الإصبع**
  useEffect(() => {
    if (!carousel || reduceMotion || dragging || hidden) return;
    const timer = window.setTimeout(
      () => setAt((index) => (index + 1) % count),
      ADVANCE_MS,
    );
    return () => window.clearTimeout(timer);
  }, [carousel, reduceMotion, dragging, hidden, current, count]);

  // **الصندوقُ كلُّه يختفي حين يفرغ** — لا إطارٌ فارغٌ ولا هيكلٌ ينتظر
  if (count === 0) return null;

  const open = (slide: Slide) => {
    if (!isOpenable(slide)) return;
    if (slide.kind === "offer") {
      // **مقصدُ العرضِ شاشةُ الاشتراك** — حيث الخصمُ نفسُه محسوبٌ على كلِّ
      // خطة، فلا يقع الكبتنُ على رقمٍ يخالف ما رآه
      navigate("/subscription");
      return;
    }
    if (slide.banner.link_kind === "internal") {
      navigate(slide.banner.link!);
      return;
    }
    // **الخارجيُّ يفتح في لسانٍ جديد** — ولا يُخرج الكبتنَ من شاشته
    window.open(slide.banner.link!, "_blank", "noopener,noreferrer");
  };

  const frame = "mb-8 overflow-hidden rounded-16 border border-line bg-surface-2";

  if (!carousel) {
    const only = slides[0];
    const openable = isOpenable(only);
    return (
      <div
        onClick={openable ? () => open(only) : undefined}
        className={`${frame} ${openable ? "pressable cursor-pointer" : ""}`}
      >
        <SlideFace slide={only} loadImage />
      </div>
    );
  }

  // ── السحب ──────────────────────────────────────────────────────────────
  //
  // **`touch-action: pan-y` يترك العموديَّ للمتصفح**: التمريرُ في الرئيسية
  // لا يمرّ بهذا الكود أصلاً. **والمحورُ يُحسم بعد `SLOP_PX`**: إن غلب
  // العموديُّ تُترك اللمسةُ كلُّها للتمرير، وإن غلب الأفقيُّ أُمسك المؤشّر.

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    gesture.current = {
      id: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      axis: null,
    };
    moved.current = false;
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const touch = gesture.current;
    if (!touch || touch.id !== event.pointerId) return;
    let dx = event.clientX - touch.x;
    const dy = event.clientY - touch.y;
    if (touch.axis === null) {
      if (Math.max(Math.abs(dx), Math.abs(dy)) < SLOP_PX) return;
      // **لمسةٌ تحرّكت ليست نقرةً في أيِّ محور** (قِيس ٢٠٢٦-٠٩-١٩): سحبٌ
      // عموديٌّ بالفأرة ينتهي بـ`click` فيفتح الرابط — واللمسُ يُلغيه
      // المتصفحُ عند التمرير، **والفأرةُ لا**
      moved.current = true;
      if (Math.abs(dx) <= Math.abs(dy)) {
        touch.axis = "y";
        gesture.current = null;
        return;
      }
      touch.axis = "x";
      try {
        event.currentTarget.setPointerCapture(event.pointerId);
      } catch {
        // **مؤشّرٌ لم يعد نشطاً** — السحبُ يكمل بلا إمساك، ولا يسقط
      }
    }
    // **الطرفان يقاومان ولا يُقلبان** — سحبٌ خلف الأولى أو بعد الأخيرة
    // يتحرّك ثلثَ الإصبع ويرتدّ، فيُفهم أن لا شيءَ هناك
    const forward = dx * dirSign > 0;
    if ((forward && current === count - 1) || (!forward && current === 0)) {
      dx /= 3;
    }
    setDragPx(dx);
  };

  const endGesture = (event: ReactPointerEvent<HTMLDivElement>) => {
    const touch = gesture.current;
    gesture.current = null;
    if (!touch || touch.id !== event.pointerId || touch.axis !== "x") {
      setDragPx(null);
      return;
    }
    const dx = event.clientX - touch.x;
    const width = viewport.current?.clientWidth ?? 1;
    if (event.type === "pointerup" && Math.abs(dx) > width * PAGE_RATIO) {
      const step = dx * dirSign > 0 ? 1 : -1;
      setAt(Math.min(count - 1, Math.max(0, current + step)));
    }
    setDragPx(null);
  };

  const transition =
    dragging || reduceMotion
      ? "none"
      : "transform 450ms cubic-bezier(0.22, 0.61, 0.36, 1)";

  return (
    <>
      <div
        ref={viewport}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endGesture}
        onPointerCancel={endGesture}
        // **نقرةٌ تلي سحباً لا تفتح شيئاً** — تُمسك قبل أن تبلغ الشريحة
        onClickCapture={(event) => {
          if (!moved.current) return;
          moved.current = false;
          event.stopPropagation();
          event.preventDefault();
        }}
        // **والصورةُ لا تُسحب كملفّ** بالفأرة على سطح المكتب
        onDragStart={(event) => event.preventDefault()}
        className={`${frame} touch-pan-y select-none`}
      >
        <div
          className="flex items-start"
          style={{
            transform: `translateX(calc(${dirSign * current * 100}% + ${dragPx ?? 0}px))`,
            transition,
          }}
        >
          {slides.map((slide, index) => {
            const openable = isOpenable(slide);
            return (
              <div
                key={slide.key}
                aria-hidden={index !== current}
                onClick={openable ? () => open(slide) : undefined}
                className={`w-full shrink-0 ${openable ? "pressable cursor-pointer" : ""}`}
              >
                <SlideFace slide={slide} loadImage={index <= reach} />
              </div>
            );
          })}
        </div>
      </div>

      <div className="mb-12 flex justify-center gap-5">
        {slides.map((item, index) => (
          <button
            key={item.key}
            type="button"
            aria-label={`لافتة ${index + 1}`}
            onClick={() => setAt(index)}
            className={
              index === current
                ? "block h-5 w-14 rounded-3 bg-muted"
                : "block size-5 rounded-3 bg-line"
            }
          />
        ))}
      </div>
    </>
  );
}
