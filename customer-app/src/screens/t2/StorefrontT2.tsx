/** **لافتاتُ العروض بلغة TAXO 2.0** — كما رسمتها «R05» (والبلاطاتُ الأربعُ في `RiderHomeT2` كما رُسمت، §٦١-د).
 *
 * **والبيانُ والسلوكُ من بيتيهما لا من هنا**: الصفوفُ يكتبها المشرفُ في اللوحة (`GET /storefront`)، **ودورانُ اللافتات
 * وسحبُها ونقرُها وجلبُ صورها المؤجَّل من `PromoBanners`** — هذا الملفُّ يلبسها جلدَ الهوية وحدَه (`PromoSkin`).
 *
 * **ورقمُ «30%» الكبير من حقله `headline`** (§٦٢-ج/٢٦ — وكان «لا عمودَ له» في `TAXO2-DESIGN-CORRECTIONS.md` §٢٢ قبله): يكتبه المشرفُ
 * في «الرقم الكبير» من اللوحة، **ولا يُقتطَع من العنوان** — نصٌّ يُكبَّر من العنوان يقول ما لم يكتبه المشرف.
 */

import { BannerImage, OfferCard, type PromoSkin } from "@/components/home/PromoBanners";

/** **جلدُ اللافتة**: بطاقةُ الجمر بشريطها المائل، والعنوانُ والنصُّ، **وسهمٌ حين تُفتح** — وصورتُها إن كانت لها
 *  من حافّةٍ إلى حافّة فوق النصّ، كما في اللافتة القائمة. **وعرضُ الاشتراك** (للكبتن وحدَه) بوجهه القائم. */
export const PROMO_SKIN_T2: PromoSkin = {
  frame: "t2-promo",
  face: (slide, loadImage) => {
    if (slide.kind === "offer") return <OfferCard offer={slide.offer} />;
    const { banner } = slide;
    const opens = banner.link_kind !== "none" && banner.link !== null;
    return (
      <>
        {loadImage ? <BannerImage bannerId={banner.id} /> : null}
        <div className="t2-promo-row">
          <span className="t2-promo-stripe" aria-hidden="true" />
          {/* **«30%» الكبيرة** (§٦٢-ج/٢٦) — من حقلها في صفِّ اللافتة؛ **وبلا رقمٍ لا موضعَ يُحجز**. **ولا أيقونةَ اللافتة هنا**:
              اللوحةُ لا ترسمها في هذا الوجه */}
          {banner.headline ? (
            <span className="t2-promo-big" dir="ltr">
              {banner.headline}
            </span>
          ) : null}
          <div className="t2-promo-text">
            <div className="t2-promo-title">{banner.title}</div>
            {banner.body ? <div className="t2-promo-body">{banner.body}</div> : null}
          </div>
          {opens ? (
            <span className="t2-icon t2-promo-go" aria-hidden="true">
              arrow_back
            </span>
          ) : null}
        </div>
      </>
    );
  },
  dots: "t2-promo-dots",
  dot: (on) => (on ? "t2-promo-dot on" : "t2-promo-dot"),
};
