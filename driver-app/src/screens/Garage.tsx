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
 */

import { useCallback, useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { Store } from "lucide-react";

import { ApiError } from "@/api/client";
import type { VehicleSkin } from "@/api/types";
import { SkinCard } from "@/components/skins/SkinCard";
import { SkinDetailSheet } from "@/components/skins/SkinDetailSheet";
import { EmptyNote, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";
import { useGarage } from "@/lib/garage";
import { RARITY_LABEL } from "@/lib/skins";

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
      <div className="flex h-full items-center justify-center bg-bg">
        <Spinner />
      </div>
    );
  }

  const skins = garage?.skins ?? [];

  return (
    <div className="relative h-full bg-bg">
      <div className="scr h-full px-16 pb-nav pt-safe">
        <div className="mb-16 flex items-center gap-10">
          <button
            type="button"
            onClick={() => goBack()}
            aria-label="رجوع"
            className="pressable text-18 text-muted"
          >
            →
          </button>
          <h1 className="text-20 font-bold text-ink">مركباتي</h1>
        </div>

        {/* **زرُّ المتجر بارزٌ في الأعلى**: الكراجُ يمتلئ من المتجر، ومن فتح
            كراجَه بمركبةٍ واحدةٍ يبحث عن البقية */}
        <button
          type="button"
          onClick={() => navigate("/account/garage/store")}
          className="pressable mb-16 flex w-full items-center gap-12 rounded-16 bg-brand px-15 py-14 text-start"
        >
          <Store size={18} className="text-brand-ink" />
          <span className="min-w-0 flex-1">
            <span className="block text-14 font-bold text-brand-ink">
              متجر المركبات
            </span>
            <span className="block text-11 text-brand-ink opacity-80">
              مركباتٌ مميزةٌ ونادرةٌ وأسطورية
            </span>
          </span>
        </button>

        {/* **العلّةُ ومعها بابُها**: «لن تظهر» بلا زرٍّ يقود إلى الاشتراك
            رسالةٌ بلا مخرج — وهي بعينها ما يمنعه عقدُ الأخطاء (§17) */}
        {garage && !garage.has_subscription ? (
          <button
            type="button"
            onClick={() => navigate("/subscription")}
            className="pressable mb-14 flex w-full items-center gap-10 rounded-14 border border-danger bg-surface px-13 py-11 text-start"
          >
            <span className="block h-36 w-6 shrink-0 rounded-4 bg-danger" />
            <span className="min-w-0 flex-1">
              <span className="block text-12.5 font-bold text-ink">
                مركبتك لا تظهر على الخريطة
              </span>
              <span className="block text-11 leading-snug text-muted">
                بلا اشتراكٍ ساري لا تصلك طلبات ولا يراك أحد. اشترك لتستقبل
                الطلبات.
              </span>
            </span>
            <span className="shrink-0 rounded-9 bg-brand px-12 py-7 text-11.5 font-bold text-brand-ink">
              اشترك
            </span>
          </button>
        ) : null}

        <ErrorNote message={error} />

        {skins.length === 0 ? (
          <EmptyNote
            title="لا مركبة في كراجك بعد"
            hint="أول اشتراكٍ يهديك واحدة، والمتجر فيه غيرها."
          />
        ) : (
          <>
            <div className="mb-10 mt-4 text-12 text-muted">
              المفعَّلةُ وحدَها تظهر على الخريطة — اضغط أيَّ مركبةٍ لتفعيلها.
            </div>
            <div className="grid grid-cols-2 gap-10">
              {skins.map((skin) => (
                <SkinCard
                  key={skin.id}
                  skin={skin}
                  onOpen={() => setOpen(skin)}
                />
              ))}
            </div>
            <p className="mt-14 text-11 leading-note text-muted">
              مركبتك واحدةٌ لحسابك كلِّه — تظهر مهما كانت السيارة التي تقودها
              اليوم. وأنواعُها: {Object.values(RARITY_LABEL).join(" · ")}.
            </p>
          </>
        )}
      </div>

      {open ? (
        <SkinDetailSheet
          skin={open}
          busy={busy}
          onBuy={null}
          onActivate={() => void choose(open)}
          onClose={() => setOpen(null)}
        />
      ) : null}
    </div>
  );
}
