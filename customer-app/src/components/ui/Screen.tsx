/** هيكل الشاشات غير الخريطية: عنوانٌ ورجوعٌ ومحتوى يتمرّر.
 *
 * السهم `ChevronRight` لا `ChevronLeft`: في واجهةٍ عربية «رجوع» يشير يميناً.
 *
 * **و`nav` يرسم الشريطَ السفلي** (الحزمة أ) ويُنهي المحتوى فوقه بـ`pb-nav`.
 * **وهو مستقلٌّ عن `back` عمداً**، لأن القياس فرض ذلك: صفحاتُ النموذج الداخلية
 * (`pgPlaces`، `pgSettings`، `pgNotifs`، `pgCards`، `pgRideDetail`) كلُّها
 * `inset:0 0 66px` — أي **سهمُ رجوعٍ والشريطُ معاً**. وهو الصواب: شريطٌ يختفي
 * عند أوّل صفٍّ يُضغط يجعل الانتقالَ من «الإعدادات» إلى «المحفظة» رجعتين بدل
 * ضغطة، وهو ما يوجد الشريطُ ليمنعه.
 *
 * وجذرُ التبويب هو `nav` مع `back={false}`: لا «خلفَ» له — من ضغط «رحلاتي» من
 * «المحفظة» لم يدخل شيئاً ليخرج منه، وسهمٌ هناك يعيده إلى تبويبٍ آخر فيُقرأ
 * عطلاً. وكلاهما `prop` لا استنتاجٌ من المسار: الشاشةُ تعرف دورَها، وقائمةُ
 * مساراتٍ في مكوّنٍ مشترك تُنسى أوّلَ مرةٍ يُضاف مسار.
 */

import { ChevronRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { ReactNode } from "react";

import { BottomNav } from "@/components/BottomNav";
import { cn } from "@/lib/utils";

export function Screen({
  title,
  back = true,
  action,
  nav = false,
  children,
  className,
}: {
  title: string;
  back?: boolean | string;
  action?: ReactNode;
  /** يرسم الشريطَ السفلي — مستقلٌّ عن `back` (انظر أعلاه). */
  nav?: boolean;
  children: ReactNode;
  className?: string;
}) {
  const navigate = useNavigate();
  const showBack = back;

  return (
    <div className="relative flex h-full flex-col bg-bg">
      <header className="sticky top-0 z-10 flex items-center gap-8 border-b border-line bg-surface px-12 pb-12 pt-safe backdrop-blur">
        {showBack ? (
          <button
            type="button"
            onClick={() =>
              typeof showBack === "string" ? navigate(showBack) : navigate(-1)
            }
            className="rounded-full p-8 text-ink transition hover:bg-surface-2"
            aria-label="رجوع"
          >
            <ChevronRight className="size-20" />
          </button>
        ) : (
          <span className="w-8" />
        )}
        <h1 className="flex-1 truncate text-18 font-semibold text-ink">{title}</h1>
        {action}
      </header>

      <main
        className={cn(
          "flex-1 overflow-y-auto px-16 py-16",
          nav ? "pb-nav" : "pb-safe",
          className,
        )}
      >
        {children}
      </main>

      {nav ? <BottomNav /> : null}
    </div>
  );
}
