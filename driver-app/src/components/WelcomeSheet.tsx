/** ورقةُ الترحيب — **عند أول فتحٍ بعد الاعتماد**، مرةً واحدةً لكل جهاز.
 *
 * **ونصوصُها ليست هنا** بل في `lib/welcome.ts` — بيتٌ واحدٌ يُعدَّل مرةً، وهي
 * قاعدةُ §17.2 مطبَّقةً على غير الأخطاء.
 *
 * **ولا تُغلق بالنقر على الظلّ** — بخلاف كلِّ ورقةٍ أخرى في هذا التطبيق. وهي
 * مخالفةٌ مقصودة: ورقةُ السحب تُغلق بالنقر لأن من فتحها **يعرف ما فيها** وقد
 * يكون فتحها خطأً؛ وهذه تُعرض **مرةً واحدةً في عمر الحساب على هذا الجهاز**،
 * فنقرةٌ عارضةٌ خارجها تحذفها إلى الأبد. وهي علّةُ إشعار الوضع النسائيّ نفسُها:
 * ما يُعرض مرةً يُغلق بيدٍ قاصدة.
 *
 * **ولا تحجب قراراً**: تظهر على الرئيسية وليس فوق عرضِ رحلةٍ ولا رحلةٍ جارية —
 * الاعتمادُ يقع قبل أيِّ طلب، فلا تزاحمُ أصلاً. والقاعدةُ مكتوبةٌ كي لا يُنقل
 * موضعُها لاحقاً بلا انتباه.
 */

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import {
  WELCOME_CTA,
  WELCOME_LEAD,
  WELCOME_POINTS,
  WELCOME_SEEN_KEY,
  WELCOME_TITLE,
} from "@/lib/welcome";

export function WelcomeSheet() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    // **القراءةُ في تأثيرٍ لا في التهيئة**: `localStorage` قد يكون ممنوعاً
    // (خصوصيةٌ مشدَّدة)، ورميُه أثناء الرسم يُفرِّغ الشاشة — والفشلُ هنا يعني
    // «لا تُعرض» لا «انكسر التطبيق»
    try {
      if (!localStorage.getItem(WELCOME_SEEN_KEY)) setOpen(true);
    } catch {
      /* لا تخزينَ متاح — لا ورقةَ، ولا عطب */
    }
  }, []);

  function dismiss() {
    setOpen(false);
    // **يُكتب عند الإغلاق لا عند العرض**: من فتح التطبيقَ فقُتل قبل أن يقرأ
    // يستحق أن يراها مرةً أخرى — ووسمُها عند العرض يحرمه إياها بلا أن يقرأها
    try {
      localStorage.setItem(WELCOME_SEEN_KEY, "1");
    } catch {
      /* تعذّر الحفظ — تُعرض مرةً أخرى، وهو أهونُ من ألّا تُعرض أبداً */
    }
  }

  if (!open) return null;

  return (
    <div className="absolute inset-0 z-50 animate-fadein-fast bg-dim">
      <div className="absolute inset-x-0 bottom-0 max-h-full overflow-y-auto animate-slideup rounded-t-24 border-t border-line bg-surface px-18 pb-24 pt-20">
        <h2 className="mb-4 text-16 font-bold text-ink">{WELCOME_TITLE}</h2>
        <p className="mb-16 text-12 text-muted">{WELCOME_LEAD}</p>

        <ul className="flex flex-col gap-14">
          {WELCOME_POINTS.map((point) => (
            <li key={point.title}>
              <div className="text-13 font-semibold text-ink">
                {point.title}
              </div>
              <p className="mt-2 text-11.5 leading-note text-muted">
                {point.body}
              </p>
            </li>
          ))}
        </ul>

        <Button className="mt-20 w-full text-14" onClick={dismiss}>
          {WELCOME_CTA}
        </Button>
      </div>
    </div>
  );
}
