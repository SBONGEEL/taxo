/** **المتجرُ بلغة TAXO 2.0** — بلاطاتُ الخدمات ولافتاتُ العروض كما رسمتها «R05».
 *
 * **والبيانُ والسلوكُ من بيتيهما لا من هنا**: الصفوفُ يكتبها المشرفُ في اللوحة (`GET /storefront`)، **وقاعدةُ
 * «أتُفتح البلاطة؟» من `tileOpenable`**، **ودورانُ اللافتات وسحبُها ونقرُها وجلبُ صورها المؤجَّل من `PromoBanners`**
 * — هذا الملفُّ يلبسها جلدَ الهوية وحدَه (`PromoSkin`). فلا يفترق الصندوقان في شيءٍ يُضغط.
 *
 * **وما رسمته اللوحةُ ولا يقوله صفٌّ لم يُبنَ** (`TAXO2-DESIGN-CORRECTIONS.md` §٢٢): رقمُ «30%» الكبير في اللافتة —
 * **لا عمودَ له**، ونصٌّ يُقتطَع من العنوان ليُكبَّر يقول ما لم يكتبه المشرف.
 */

import { useNavigate } from "react-router-dom";

import type { ServiceTile } from "@/api/types";
import { BannerImage, OfferCard, type PromoSkin } from "@/components/home/PromoBanners";
import { tileOpenable } from "@/components/home/ServiceTiles";
import { serviceIcon } from "@/taxo2";

/** **البلاطاتُ الصغيرةُ أربعاً في الصفّ** — بترتيب اللوحة وحالها: «قريباً» إطارٌ متقطّعٌ يُقرأ ولا يُنقر،
 *  و«جديد» شارةٌ من الخلفية بمدّتها. **والعنوانُ الفرعيُّ تحت العنوان** حين لا شارة — كما في البلاطة القائمة. */
export function ServiceTilesT2({ tiles }: { tiles: ServiceTile[] }) {
  const navigate = useNavigate();
  if (tiles.length === 0) return null;

  return (
    <div className="t2-tiles">
      {tiles.map((tile) => {
        const openable = tileOpenable(tile);
        const soon = tile.status === "soon";
        return (
          <div
            key={tile.id}
            // **لا `onClick` على «قريباً»** — كالبلاطة القائمة: اللمسةُ تمرّ بلا حدثٍ ولا خطأ
            onClick={openable ? () => navigate(tile.destination!) : undefined}
            className={`t2-tile${soon ? " soon" : ""}${openable ? " open" : ""}`}
          >
            <span className="t2-icon t2-tile-icon" aria-hidden="true">
              {serviceIcon(tile.icon)}
            </span>
            <span className="t2-tile-title">
              {tile.title}
              {!soon && !tile.is_new && tile.subtitle ? (
                <span className="t2-tile-sub">{tile.subtitle}</span>
              ) : null}
            </span>
            {soon ? (
              <span className="t2-tile-badge soon">قريباً</span>
            ) : tile.is_new ? (
              <span className="t2-tile-badge new">جديد</span>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

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
          {banner.icon ? (
            <span className="t2-icon t2-promo-icon" aria-hidden="true">
              {serviceIcon(banner.icon)}
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
