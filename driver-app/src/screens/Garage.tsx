/** **مركباتي** — كراجُ الكبتن (2026-08-22).
 *
 * **وضغطةٌ واحدةٌ تبدّل المفعَّلة**: الكراجُ ليس شاشةَ إعدادات، وخطوةُ تأكيدٍ
 * على تبديلٍ **لا يمسّ مالاً ويُرجَع عنه بضغطةٍ ثانية** احتكاكٌ بلا ثمن.
 * والتبديلُ متفائلٌ فتنعكس الخريطةُ في اللحظة نفسِها (`lib/garage.tsx`).
 *
 * **والمركبةُ للحساب لا للسيارة** (قرارُ المالك): من يملك سيارتين يملك
 * **مركبةً نشطةً واحدة**، تظهر مهما كانت السيارةُ التي يقودها اليوم — فلا
 * منتقيَ سيارةٍ هنا ولا ربطَ بلوحة.
 *
 * **ولا اشتراكَ: يُقال ولا يُخفى الكراج.** المركباتُ ملكُه اشترك أو لم يشترك،
 * والذي يقف هو **ظهورُها على الخريطة** — فتُقال العلّةُ ومعها بابُها.
 *
 * **خلف مفتاح السوق** (`vehicle_skins_enabled`، يُقرأ من `useGarage`): مطفأً يعود المسارُ إلى «حسابي» ولا صفَّ إليه —
 * **وبُنيت بلغة TAXO 2.0 جاهزةً ليومِ يُشعَل** (§٦٢/١٣). «C31» (`design/t2-new/captain/C31*.dc.html`): بطاقاتُ متجر المركبات
 * «C11» بعينها (`t2-store-card` من `t2.css`)، والمتجرُ بابٌ بارزٌ على الجمر الخافت، وتنبيهُ الاشتراك صفُّ «C12» الأحمر بزرّه.
 * **والمنطقُ حرفاً**: القراءةُ عند الفتح، والتفعيلُ من ورقة المنتج نفسِها (`SkinDetailSheet`، بجسر الألوان كما في المتجر).
 */

import { useCallback, useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import type { VehicleSkin } from "@/api/types";
import { SkinArt } from "@/components/skins/SkinArt";
import { SkinDetailSheet } from "@/components/skins/SkinDetailSheet";
import { useGoBack } from "@/lib/back";
import { useGarage } from "@/lib/garage";
import { RARITY_LABEL } from "@/lib/skins";
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "@/screens/t2/t2.css";
import "@/screens/t2/account.css";

/** **سطرُ البطاقة القائمة بنصّه**: المتبقّي حين تكون الكميّةُ محدودة، ومن اقتناها — و`null` بلا حدٍّ فلا سطر. */
function stockLine(skin: VehicleSkin): string | null {
  if (skin.remaining !== null) {
    return `${skin.remaining > 0 ? `متبقٍّ ${digits(String(skin.remaining))}` : "نفدت الكمية"} · ${digits(
      String(skin.owners_count),
    )} اقتنوها`;
  }
  return skin.owners_count > 0
    ? `${digits(String(skin.owners_count))} اقتنوها`
    : null;
}

export function GarageScreen() {
  const goBack = useGoBack();
  const navigate = useNavigate();
  const { enabled, garage, loading, refresh, activate } = useGarage();
  const [open, setOpen] = useState<VehicleSkin | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // **تُقرأ عند كلِّ فتحٍ للشاشة**: يشتري من المتجر ثم يعود، ومركبةٌ اشتراها
  // قبل ثانيةٍ لا تظهر في كراجٍ قُرئ عند الإقلاع
  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const choose = useCallback(
    async (skin: VehicleSkin) => {
      setBusy(true);
      setError(null);
      try {
        await activate(skin.id);
        setOpen(null);
      } catch (caught) {
        setError(
          caught instanceof ApiError ? caught.message : "تعذّر تفعيل المركبة",
        );
      } finally {
        setBusy(false);
      }
    },
    [activate],
  );

  // **مطفأً: رجوعٌ لا رسالةُ خطأ.** الصفُّ محجوبٌ في «حسابي» أصلاً، وهذا
  // لمن وصل برابطٍ مباشر (إشعارٌ قديم، أو مسارٌ محفوظ) — وشاشةُ خطأٍ عن
  // ميزةٍ لم تُفتح في سوقه تُقرأ عطباً
  if (!enabled) return <Navigate to="/account" replace />;

  if (loading && !garage) {
    return (
      <div className="t2 t2-ax">
        <div className="t2-ax-center">
          <span className="t2-ax-spin" role="status" aria-label="جارٍ التحميل" />
        </div>
      </div>
    );
  }

  const skins = garage?.skins ?? [];

  return (
    <div className="t2 t2-ax">
      <div className="t2-ax-scroll">
        <div className="t2-head">
          <button type="button" className="t2-back" aria-label="رجوع" onClick={() => goBack()}>
            <Icon name="arrow_forward" />
          </button>
          <h1 className="t2-title">مركباتي</h1>
        </div>

        {/* **زرُّ المتجر بارزٌ في الأعلى**: الكراجُ يمتلئ من المتجر، ومن فتح
            كراجَه بمركبةٍ واحدةٍ يبحث عن البقية */}
        <button
          type="button"
          onClick={() => navigate("/account/garage/store")}
          className="t2-gar-store"
        >
          <span className="t2-ax-tile" aria-hidden="true">
            <Icon name="storefront" />
          </span>
          <span className="t2-gar-store-main">
            <span className="t2-gar-store-title">متجر المركبات</span>
            <span className="t2-gar-store-sub">مركباتٌ مميزةٌ ونادرةٌ وأسطورية</span>
          </span>
          <Icon name="chevron_left" className="t2-ax-chev" />
        </button>

        {/* **العلّةُ ومعها بابُها**: «لن تظهر» بلا زرٍّ يقود إلى الاشتراك
            رسالةٌ بلا مخرج — وهي بعينها ما يمنعه عقدُ الأخطاء (§17) */}
        {garage && !garage.has_subscription ? (
          <button
            type="button"
            onClick={() => navigate("/subscription")}
            className="t2-gar-nosub"
          >
            <span className="t2-ax-tile danger" aria-hidden="true">
              <Icon name="visibility_off" />
            </span>
            <span className="t2-gar-nosub-main">
              <span className="t2-gar-nosub-title">مركبتك لا تظهر على الخريطة</span>
              <span className="t2-gar-nosub-text">
                بلا اشتراكٍ ساري لا تصلك طلبات ولا يراك أحد. اشترك لتستقبل
                الطلبات.
              </span>
            </span>
            <span className="t2-gar-nosub-go">اشترك</span>
          </button>
        ) : null}

        {error ? (
          <p className="t2-note danger" role="alert">
            <Icon name="error" />
            {error}
          </p>
        ) : null}

        {skins.length === 0 ? (
          <div className="t2-empty t2-ax-empty">
            <b>لا مركبة في كراجك بعد</b>
            <span>أول اشتراكٍ يهديك واحدة، والمتجر فيه غيرها.</span>
          </div>
        ) : (
          <>
            <p className="t2-gar-lede">
              المفعَّلةُ وحدَها تظهر على الخريطة — اضغط أيَّ مركبةٍ لتفعيلها.
            </p>
            <div className="t2-gar-grid">
              {skins.map((skin) => {
                const stock = stockLine(skin);
                return (
                  // **بطاقةُ «C11» بعينها** — الضغطُ يفتح ورقةَ المنتج وفيها «فعّلها»، كما كانت البطاقةُ القائمة
                  <button
                    key={skin.id}
                    type="button"
                    className={skin.active ? "t2-store-card on" : "t2-store-card"}
                    onClick={() => setOpen(skin)}
                  >
                    <span className="t2-store-well">
                      <SkinArt skin={skin} className="t2-store-art" />
                    </span>
                    <span className="t2-store-card-text">
                      <span className="t2-store-card-name">{skin.name}</span>
                      <span className="t2-store-card-kind">{RARITY_LABEL[skin.rarity]}</span>
                    </span>
                    {/* **المفعَّلةُ معلَّمةٌ بعلامتين لا بواحدة**: الإطارُ **والكلمة** — الإطارُ وحدَه يُقرأ «مختارة» */}
                    {skin.active ? (
                      <span className="t2-store-tag ok">مفعّلة</span>
                    ) : (
                      <span className="t2-store-tag">في كراجك</span>
                    )}
                    {stock ? <span className="t2-store-stock">{stock}</span> : null}
                    {skin.active ? (
                      <span className="t2-store-check" aria-hidden="true">
                        <Icon name="check" />
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>
            <p className="t2-gar-fine">
              مركبتك واحدةٌ لحسابك كلِّه — تظهر مهما كانت السيارة التي تقودها
              اليوم. وأنواعُها: {Object.values(RARITY_LABEL).join(" · ")}.
            </p>
          </>
        )}
      </div>

      {/* **ورقةُ المنتج نفسُها** — بألوان الهوية عبر جسر الألوان القائمة (`.t2-legacy`)، كما في المتجر */}
      {open ? (
        <div className="t2-legacy t2-store-sheet">
          <SkinDetailSheet
            skin={open}
            busy={busy}
            onBuy={null}
            onActivate={() => void choose(open)}
            onClose={() => setOpen(null)}
          />
        </div>
      ) : null}
    </div>
  );
}
