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
 * **والنقاطُ تحتها من التصميم**: تظهر حين تتعدّد اللافتاتُ لا حين تكون
 * واحدة — **ونقطةٌ واحدةٌ تحت لافتةٍ واحدةٍ تَعِد بثانيةٍ لا وجودَ لها**.
 */

import { useEffect, useState } from "react";
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

export function PromoBanners({
  banners,
  offer = null,
}: {
  banners: PromoBanner[];
  offer?: StorefrontOffer | null;
}) {
  const navigate = useNavigate();
  const [at, setAt] = useState(0);

  // **العرضُ أوّلاً**: نافذتُه أقصرُ من نافذة اللافتة وأثرُه مالٌ في جيب
  // الكبتن — **ولافتةٌ تعلوه تدفعه إلى نقطةٍ لا تُنقر**
  const slides: ({ key: string } & (
    | { kind: "offer"; offer: StorefrontOffer }
    | { kind: "banner"; banner: PromoBanner }
  ))[] = [
    ...(offer ? [{ key: "offer", kind: "offer" as const, offer }] : []),
    ...banners.map((banner) => ({
      key: banner.id,
      kind: "banner" as const,
      banner,
    })),
  ];
  // **الصندوقُ كلُّه يختفي حين يفرغ** — لا إطارٌ فارغٌ ولا هيكلٌ ينتظر
  if (slides.length === 0) return null;

  const slide = slides[Math.min(at, slides.length - 1)];
  const openable =
    slide.kind === "offer" ||
    (slide.banner.link_kind !== "none" && slide.banner.link !== null);

  const open = () => {
    if (!openable) return;
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

  return (
    <>
      <div
        onClick={openable ? open : undefined}
        className={`mb-8 overflow-hidden rounded-16 border border-line bg-surface-2 ${
          openable ? "pressable cursor-pointer" : ""
        }`}
      >
        {slide.kind === "offer" ? (
          <OfferCard offer={slide.offer} />
        ) : (
          <>
            {/* **الصورةُ من حافةٍ إلى حافة** — والحشوةُ نزلت إلى الداخل لأجلها،
                فبطاقةٌ بلا صورةٍ تبقى كما كانت حرفاً */}
            <BannerImage bannerId={slide.banner.id} />
            <div className="p-14">
              <div className="flex items-start gap-10">
                {slide.banner.icon ? (
                  <Glyph
                    name={slide.banner.icon}
                    className="size-44 shrink-0 text-line"
                  />
                ) : null}
                <div className="min-w-0 flex-1">
                  <div className="text-14 font-bold text-ink">
                    {slide.banner.title}
                  </div>
                  {slide.banner.body ? (
                    <div className="mt-3 text-11.5 leading-note text-muted">
                      {slide.banner.body}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {slides.length > 1 ? (
        <div className="mb-12 flex justify-center gap-5">
          {slides.map((item, index) => (
            <button
              key={item.key}
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
