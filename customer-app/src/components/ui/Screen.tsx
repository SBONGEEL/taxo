/** هيكل الشاشات غير الخريطية: عنوانٌ ورجوعٌ ومحتوى يتمرّر.
 *
 * السهم `ChevronRight` لا `ChevronLeft`: في واجهةٍ عربية «رجوع» يشير يميناً.
 *
 * **و`nav` يحجز مكانَ الشريط السفلي** (`pb-nav`) ولا يرسمه: الشريطُ صار واحداً
 * فوق الملاح كلِّه (`App.tsx::NavBar`)، لأن شريطاً يُفكَّك ويُركَّب مع كلِّ شاشة
 * لا تنزلق حبّتُه — `layoutId` لا يقيس بين عنصرين لم يجتمعا في لحظة.
 * **وهو مستقلٌّ عن `back` عمداً**، لأن القياس فرض ذلك: صفحاتُ النموذج الداخلية
 * (`pgPlaces`، `pgSettings`، `pgNotifs`، `pgCards`، `pgRideDetail`) كلُّها
 * `inset:0 0 66px` — أي **سهمُ رجوعٍ والشريطُ معاً**. وهو الصواب: شريطٌ يختفي
 * عند أوّل صفٍّ يُضغط يجعل الانتقالَ من «الإعدادات» إلى «المحفظة» رجعتين بدل
 * ضغطة، وهو ما يوجد الشريطُ ليمنعه.
 *
 * **و`back` وجهةٌ احتياطيةٌ لا وجهةٌ ثابتة** (12-ي+، بعد عطبِ الجرس): الشاشةُ
 * التي لها بابان — كالإشعارات: من رأس الخريطة ومن «حسابي» — كانت تُرجع الجميعَ
 * إلى الأب المكتوب، فيهبط من دخل من الخريطة في «حسابي» وهو لم يزره. القرارُ في
 * `lib/back.ts`: من حيث جئت، والمكتوبُ لمن لا تاريخَ له.
 *
 * وجذرُ التبويب هو `nav` مع `back={false}`: لا «خلفَ» له — من ضغط «رحلاتي» من
 * «المحفظة» لم يدخل شيئاً ليخرج منه، وسهمٌ هناك يعيده إلى تبويبٍ آخر فيُقرأ
 * عطلاً. وكلاهما `prop` لا استنتاجٌ من المسار: الشاشةُ تعرف دورَها، وقائمةُ
 * مساراتٍ في مكوّنٍ مشترك تُنسى أوّلَ مرةٍ يُضاف مسار.
 */

import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";

import { useGoBack } from "@/lib/back";
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
  // **المسارُ المكتوب مخرجٌ احتياطيٌّ لا وجهة** (`lib/back.ts`): الرجوعُ يعيدك
  // من حيث جئت، ولا يُستعمل هذا المسارُ إلا حين لا تاريخَ داخل التطبيق
  const goBack = useGoBack(typeof back === "string" ? back : "/");
  const showBack = back;

  return (
    <div className="relative flex h-full flex-col bg-bg">
      <header className="sticky top-0 z-10 flex items-center gap-8 border-b border-line bg-surface px-12 pb-12 pt-safe backdrop-blur">
        {showBack ? (
          <button
            type="button"
            onClick={goBack}
            className="pressable rounded-full p-8 text-ink transition hover:bg-surface-2"
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

    </div>
  );
}
