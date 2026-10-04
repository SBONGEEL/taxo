/** متجرُ المركبات — TAXO 2.0 «C11» (Claude Design «Captain»)، **في الداكن المرسوم وحدَه**.
 *
 * **وجهٌ ثانٍ لا شاشةٌ ثانية**: الصفحاتُ ومراقبُ القاع والرصيدُ والشراءُ من `useSkinStoreScreen` (`screens/SkinStore.tsx`) —
 * **والمالُ يمرّ بخطواته الثلاث نفسِها**: ورقةُ المنتج (`SkinDetailSheet`) ← ورقةُ التأكيد (`BuyConfirmSheet`: السعرُ
 * ورصيدُك الآن و«لا استرداد») ← `POST` الشراء بحرفه. **وزرُّ «شراء» في الشريط يفتح ورقةَ المنتج** كما كانت البطاقةُ تفتحها.
 *
 * **والاختيارُ كما رسمته اللوحة**: الضغطُ على بطاقةٍ يختارها ولا يدفع — فتُرسم في المعاينة أعلاه **على الخريطة الحقيقية**
 * (`SkinMapPreview`)، والمعاينةُ نفسُها تفتح ورقةَ المنتج لكلِّ مركبة (المملوكةِ والمقفولةِ أيضاً)، كما كانت البطاقة.
 *
 * **والمتجرُ مقسومٌ بندرته كما هو** (عقدُ المتجر: الترتيبُ من الخلفية لا يُعاد) — والشبكةُ واحدةٌ كما رسمتها اللوحة،
 * **والمرشِّحاتُ الندرةُ بأسمائها**: تُخفي ولا ترتّب، ووصفُ الندرة (رأسُ قسمها القائم) يظهر حين يُختار مرشِّحُها.
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته** (`design/drafts/captain-C09-C12.md`):
 * - **«شراء وتفعيل»**: الشراءُ لا يفعّل (`vehicle_skins.buy`) — والتفعيلُ بابُه «مركباتي»؛ فالزرُّ «شراء».
 * - **«خصم الذهبي 10%» والسعرُ المشطوب «3.000»**: لا خصمَ بالمستوى في المتجر ولا حقلَ له.
 * - **«بلاتيني» على المقفولة**: اسمُ المستوى لا يصل في جواب المتجر — فالشارةُ سببُ المنع بنصّه (`BLOCKED_LABEL`).
 * - **فئاتُ «كلاسيك · فاخرة · محدودة»**: لا فئاتَ بهذه الأسماء — المرشِّحاتُ **الندرةُ بأسمائها** و«مملوكة».
 * - **رسومُ السيارات الملوّنة**: المركباتُ صورٌ يرفعها المشرف — تُرسم كما رُفعت.
 */

import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import type { Rarity, VehicleSkin } from "@/api/types";
import { BuyConfirmSheet } from "@/components/skins/BuyConfirmSheet";
import { SkinArt } from "@/components/skins/SkinArt";
import { SkinDetailSheet } from "@/components/skins/SkinDetailSheet";
import { SkinMapPreview } from "@/components/skins/SkinMapPreview";
import { Spinner } from "@/components/ui/Feedback";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { BLOCKED_LABEL, RARITY_LABEL, RARITY_NOTE } from "@/lib/skins";
import { digits } from "@/lib/utils";
import { useSkinStoreScreen } from "@/screens/SkinStore";

import "@/taxo2";
import "./t2.css";

type Filter = "all" | "owned" | Rarity;

/** **أين تُرى وكيف تتحرّك** — من `visible_before_accept` و`map_rotates` لا من الندرة (شرطُ العقد في `lib/skins`). */
function seenLine(skin: VehicleSkin): string {
  const where = skin.visible_before_accept
    ? "تظهر للراكب"
    : "تظهر لراكبك بعد قبول الرحلة";
  return `${RARITY_LABEL[skin.rarity]} · ${where}${skin.map_rotates ? " وتتحرك مع اتجاهك" : ""}`;
}

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

/** يُشترى أم لا — **الشرطُ نفسُه الذي يُظهر زرَّ «شراء» في ورقة المنتج** (`SkinStore.tsx`). */
function buyable(skin: VehicleSkin): boolean {
  return !(skin.owned || skin.blocked_reason || !skin.price);
}

export function SkinStoreT2Screen() {
  const s = useSkinStoreScreen();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Filter>("all");
  const [picked, setPicked] = useState<string | null>(null);

  // **مطفأً: رجوعٌ لا رسالةُ خطأ** — كالشاشة القائمة سواءً
  if (!s.enabled) return <Navigate to="/account" replace />;

  if (s.loading) {
    return (
      <div className="t2 t2-store t2-store-loading">
        <Spinner />
      </div>
    );
  }

  // **المفتوحةُ في ورقة المنتج** — تُقرأ مرّةً كما في الشاشة القائمة (`open`)
  const open = s.open;
  // **المختارةُ افتراضاً المفعَّلة** — فالمعاينةُ تقول «هكذا يراك الراكب» صدقاً قبل أيِّ لمسة
  const selected =
    s.skins.find((skin) => skin.id === picked) ??
    s.skins.find((skin) => skin.active) ??
    s.skins[0] ??
    null;
  const rarities = [...new Set(s.skins.map((skin) => skin.rarity))];
  const shown = s.skins.filter((skin) =>
    filter === "all"
      ? true
      : filter === "owned"
        ? skin.owned
        : skin.rarity === filter,
  );

  return (
    <div className="t2 t2-store">
      <div className="t2-store-scroll scr">
        <div className="t2-store-head">
          <button
            type="button"
            className="t2-store-back"
            aria-label="رجوع"
            onClick={() => s.goBack()}
          >
            <span className="t2-icon" aria-hidden="true">
              arrow_forward
            </span>
          </button>
          <h1 className="t2-store-title">متجر المركبات</h1>
          {/* **الرصيدُ في الرأس** — من يتصفّح الأسعارَ يحتاج أن يعرف ما معه */}
          {s.store ? (
            <span className="t2-store-wallet" aria-label="رصيد محفظتك">
              <span className="t2-icon" aria-hidden="true">
                account_balance_wallet
              </span>
              <span className="t2-store-wallet-num" dir="ltr">
                {digits(s.store.balance)}
              </span>
              <span className="t2-store-wallet-cur">
                {CURRENCY_LABEL[s.store.currency]}
              </span>
            </span>
          ) : null}
        </div>

        {selected ? (
          <>
            {/* **المعاينةُ تفتح ورقةَ المنتج** — صورتُها الكبيرة وتفاصيلُها، كما كانت البطاقة */}
            <button
              type="button"
              className="t2-store-preview t2-legacy"
              aria-label={`تفاصيل ${selected.name}`}
              onClick={() => s.setOpen(selected)}
            >
              <SkinMapPreview skin={selected} className="t2-store-map" />
              <span className="t2-store-shade" aria-hidden="true" />
              <span className="t2-store-fade" aria-hidden="true" />
              <span className="t2-store-seen">
                <span className="t2-icon fill" aria-hidden="true">
                  visibility
                </span>
                هكذا يراك الراكب
              </span>
              <span className="t2-store-info">
                <span className="t2-store-info-name">{selected.name}</span>
                <span className="t2-store-info-sub">{seenLine(selected)}</span>
              </span>
            </button>
          </>
        ) : null}

        {/* ── المرشِّحات: الكلُّ والندراتُ الحاضرةُ بأسمائها ومملوكة ── */}
        {s.skins.length > 0 ? (
          <div className="t2-store-chips" role="tablist" aria-label="المركبات">
            {(["all", ...rarities, "owned"] as Filter[]).map((key) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={filter === key}
                className={
                  filter === key ? "t2-store-chip on" : "t2-store-chip"
                }
                onClick={() => setFilter(key)}
              >
                {key === "all"
                  ? "الكل"
                  : key === "owned"
                    ? "مملوكة"
                    : RARITY_LABEL[key]}
              </button>
            ))}
          </div>
        ) : null}

        {s.failed ? (
          <p className="t2-note danger">
            <span className="t2-icon" aria-hidden="true">
              error
            </span>
            {s.failed}
          </p>
        ) : null}
        {s.done ? <p className="t2-store-done">{s.done}</p> : null}

        {s.skins.length === 0 && !s.failed ? (
          <div className="t2-empty t2-store-empty">
            <b>لا مركبات معروضةً الآن</b>
            <span>يُضاف إلى المتجر من وقتٍ لآخر — عُد لاحقاً.</span>
          </div>
        ) : null}

        {/* **وصفُ الندرة بنصّه** — كان رأسَ قسمها في الشاشة القائمة، واللوحةُ ترسم الشبكةَ واحدةً بمرشِّحات: فيظهر حين
            يُختار مرشِّحُها، والترتيبُ ترتيبُ الخلفية (مقسوماً بندرته) لا يُعاد */}
        {filter !== "all" && filter !== "owned" ? (
          <p className="t2-store-note">{RARITY_NOTE[filter]}</p>
        ) : null}

        <div className="t2-store-grid">
          {shown.map((skin) => {
            const on = selected?.id === skin.id;
            const locked = !skin.owned && skin.blocked_reason !== null;
            const stock = stockLine(skin);
            return (
              <button
                key={skin.id}
                type="button"
                aria-pressed={on}
                className={`t2-store-card${on ? " on" : ""}${locked ? " locked" : ""}`}
                onClick={() => setPicked(skin.id)}
              >
                <span className="t2-store-well">
                  <SkinArt skin={skin} className="t2-store-art" />
                </span>
                <span className="t2-store-card-text">
                  <span className="t2-store-card-name">{skin.name}</span>
                  <span className="t2-store-card-kind">
                    {RARITY_LABEL[skin.rarity]}
                  </span>
                </span>
                {skin.active ? (
                  <span className="t2-store-tag ok">مفعّلة</span>
                ) : skin.owned ? (
                  <span className="t2-store-tag">مملوكة</span>
                ) : skin.blocked_reason ? (
                  <span className="t2-store-tag warn">
                    <span className="t2-icon fill" aria-hidden="true">
                      lock
                    </span>
                    {BLOCKED_LABEL[skin.blocked_reason]}
                  </span>
                ) : skin.price && skin.currency ? (
                  <span className="t2-store-price">
                    <span className="t2-store-price-num" dir="ltr">
                      {digits(skin.price)}
                    </span>
                    <span className="t2-store-price-cur">
                      {CURRENCY_LABEL[skin.currency]}
                    </span>
                  </span>
                ) : (
                  <span className="t2-store-card-kind">غير معروضة للبيع</span>
                )}
                {stock ? <span className="t2-store-stock">{stock}</span> : null}
                {on ? (
                  <span className="t2-store-check" aria-hidden="true">
                    <span className="t2-icon">check</span>
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>

        {/* **حارسُ القاع** — بلوغُه يطلب الصفحةَ التالية، كما في الشاشة القائمة */}
        <div
          ref={s.sentinel}
          aria-hidden="true"
          className="t2-store-sentinel"
        />
        {s.paging ? (
          <div className="t2-store-paging">
            <Spinner />
          </div>
        ) : null}

        <p className="t2-store-fine">
          المركبةُ زينةٌ على الخريطة — لا تغيّر أجرتك ولا فئةَ سيارتك ولا
          أولويتَك في الطلبات.
        </p>
      </div>

      {/* ── الشريطُ السفليّ: سعرُ المختارة وزرُّها، أو سببُ المنع بنصّه — والمملوكةُ بابُها «مركباتي» ── */}
      {selected ? (
        <div className="t2-store-bar">
          <div className="t2-store-bar-main">
            {selected.price && selected.currency && !selected.owned ? (
              <div className="t2-store-bar-price">
                <span className="t2-store-bar-num" dir="ltr">
                  {digits(selected.price)}
                </span>
                <span className="t2-store-bar-cur">
                  {CURRENCY_LABEL[selected.currency]}
                </span>
              </div>
            ) : (
              <div className="t2-store-bar-name">{selected.name}</div>
            )}
            <div className="t2-store-bar-sub">
              {buyable(selected)
                ? "تُخصم من محفظتك · تملكها دائماً"
                : selected.owned
                  ? selected.active
                    ? "مفعّلة — والتبديلُ من «مركباتي»"
                    : "في كراجك — وتفعيلُها من «مركباتي»"
                  : selected.blocked_reason
                    ? BLOCKED_LABEL[selected.blocked_reason]
                    : "غير معروضة للبيع"}
            </div>
          </div>
          {buyable(selected) ? (
            // **يفتح ورقةَ المنتج لا التأكيد** — الخطواتُ الثلاثُ إلى المال كما هي (`SkinStore.tsx`)
            <button
              type="button"
              className="t2-store-buy"
              disabled={s.busy}
              onClick={() => s.setOpen(selected)}
            >
              <span className="t2-icon fill" aria-hidden="true">
                shopping_bag
              </span>
              شراء
            </button>
          ) : selected.owned ? (
            <button
              type="button"
              className="t2-store-garage"
              onClick={() => navigate("/account/garage")}
            >
              مركباتي
            </button>
          ) : null}
        </div>
      ) : null}

      {/* ── ورقتا المنتج والتأكيد بنفسهما وبشروطهما — بألوان الهوية عبر جسر الألوان القائمة (`.t2-legacy`) ── */}
      {open ? (
        <div className="t2-legacy t2-store-sheet">
          <SkinDetailSheet
            skin={open}
            busy={s.busy}
            onActivate={null}
            onBuy={
              open.owned || open.blocked_reason || !open.price
                ? null
                : () => s.setConfirming(open)
            }
            onClose={() => s.setOpen(null)}
          />
        </div>
      ) : null}

      {s.confirming && s.store ? (
        <div className="t2-legacy t2-store-sheet">
          <BuyConfirmSheet
            skin={s.confirming}
            balance={s.store.balance}
            currency={s.store.currency}
            busy={s.busy}
            error={s.buyError}
            onConfirm={() => void s.confirm()}
            onClose={() => {
              s.setConfirming(null);
              s.setBuyError(null);
            }}
          />
        </div>
      ) : null}
    </div>
  );
}
