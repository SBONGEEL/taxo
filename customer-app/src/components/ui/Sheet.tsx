/** الورقة السفلية — عمودُ واجهة الراكب الفقري (SPEC القسم 2: shadcn/Drawer).
 *
 * صنفان:
 * - `Sheet`: ورقةٌ ثابتة ملتصقة بأسفل الشاشة فوق الخريطة (الشاشة الرئيسية،
 *   التتبع). لا تُغلق ولا تُسحب — هي المحتوى نفسه.
 * - `DrawerSheet`: ورقةٌ منبثقة تُغلق بالسحب أو باللمس خارجها (اختيار الوجهة،
 *   شاشة الدفع). مبنيةٌ على `vaul` وهو ما يبني عليه shadcn/ui نفسه.
 */

import { motion } from "framer-motion";
import { Drawer } from "vaul";
import type { ReactNode } from "react";

import { DURATION, EASE } from "@/lib/motion";
import { cn } from "@/lib/utils";

export function Sheet({
  children,
  className,
  attached = false,
  footer,
}: {
  children: ReactNode;
  className?: string;
  /** ملتصقةٌ بحافة الشاشة تحت حجاب — لا عائمةٌ فوق الخريطة.
   *
   *  **والفصلُ من التصميم لا من الذوق**: `DESIGN.md` §1.3 يقول «الورقة السفلية
   *  المنبثقة (`24px 24px 0 0`)» — أي زوايا عليا فقط، لأنها تخرج من الحافة
   *  وتُغلق إليها. والعائمةُ فوق الخريطة عائلةٌ أخرى: تسكن حيث يسكن الشريطُ
   *  السفلي العائم، فتأخذ لغتَه — أربعُ زوايا وهامشٌ من الجوانب. */
  attached?: boolean;
  /** **قدمٌ ثابتةٌ لا تُمرَّر** — لِما لا يجوز أن يغيب عن العين مهما طال ما
   *  فوقه: مبلغُ الأجرة وزرُّ الالتزام (إذنُ المالك 2026-08-23).
   *
   *  **والتمريرُ وحدَه لا يفي بالشرط**: ورقةٌ مسقوفةٌ تُمرَّر تجعل كلَّ سطرٍ
   *  **قابلاً للبلوغ**، وهذا غيرُ **أن يُرى** — ومن يضغط «اطلب» وقد مرّر
   *  الرقمَ خارج نظره يلتزم بمبلغٍ لا يقرؤه. فالسقفُ يمنع القصّ، والقدمُ
   *  تمنع الغياب، **ولا يُغني أحدُهما عن الآخر**. */
  footer?: ReactNode;
}) {
  return (
    // **تنزلق وتختفي** (§8): الورقةُ تظهر من أسفل وتغادر إليه، فيُقرأ أنها
    // طبقةٌ فوق الشاشة لا محتوىً بدّل مكانَه فجأة
    <motion.div
      initial={{ y: 24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: 24, opacity: 0 }}
      transition={{ duration: DURATION.med, ease: EASE.standard }}
      className={cn(
        // **`rounded-t-22` لا `rounded-t-sheet`**: لا مفتاحَ `sheet` في سلّم
        // أنصاف الأقطار، فالصنفُ كان **لا يولّد شيئاً** — قِيس على الجهاز
        // `border-radius: 0px`، وعُدَّ في CSS المبنيّ: صفرُ قواعد. وهي أختُ
        // `.scr`: صنفٌ مكتوبٌ صحيحاً، حاضرٌ في الوسم، لا وجودَ له في المخرَج،
        // والبناءُ أخضر. و٢٢ ليست اختياراً: `DESIGN.md` §1.3 يقول «ورقة
        // الرحلة/التأكيد المدمجة (22px 22px 0 0)».
        "pointer-events-auto border-line bg-surface",
        // **عائمةٌ بأربع زوايا وهامشٍ جانبيّ ١٦** — نفسُ لغة الشريط السفلي
        // (`BottomNav`: `px-16` و`rounded-full` و`border-line` و`shadow-sheet`)،
        // فيُقرأ الاثنان عائلةً واحدةً تطفو فوق الخريطة. و**الفرجةُ فوق الشريط
        // ١٦** لتوازن الهامش الجانبي: الحاويةُ ترفعها `nav` (84) والبارُ يعلو
        // 76، فالفارقُ ثمانيةٌ — و`mb-8` يكملها إلى ستةَ عشر.
        attached
          ? "rounded-t-24 border-t"
          : "mx-16 mb-[calc(8px+var(--vv-bottom,0px))] rounded-22 border",
        // **سقفٌ يمنع القصَّ من الأعلى** (عطبٌ مقيسٌ 2026-08-23). كانت الورقةُ
        // بلا `max-height` وبلا تمرير، **ومثبَّتةً من الأسفل** داخل صندوقٍ
        // `overflow-hidden` — فكلُّ زيادةٍ تخرج من **الأعلى** ويقصّها الصندوق.
        // قِيس على S21: ورقةُ التأكيد ٩١٥ في شاشة ٨٠٠ ⇐ **٢٠٧ بكسلاً مقصوصة**
        // تحمل نقطةَ الانطلاق والوجهةَ ومحرّرَ المحطات، **ولا سبيلَ إلى
        // بلوغها بأيِّ حركة** — فهي غيرُ موجودةٍ لا مُزاحةً عن النظر.
        //
        // **والرقمُ محجوزٌ من الأعلى لا نسبةٌ من الإطار** — نفسُ علّة
        // `DrawerSheet` أدناه: `dvh` يتبع الإطارَ فيتقلّص مع لوحة المفاتيح
        // (قِيس ٨٢٠ ⇐ ٤٦٢)، ونسبةٌ منه تُبقي الرأسَ ينجو بالصدفة. و**٧٦** هي
        // ١٦ (علوُّ أزرار الرأس) + ٤٤ (قطرُها) + ١٦ (فرجة).
        // والعائمةُ تطرح فوقها **٩٢**: ٨٤ رفعةَ الحاوية (`bottom-nav`) و٨
        // هامشَها السفليّ (`mb-8`).
        // **و`--vvh` لا `dvh`** (قِيس بلوحة مفاتيحَ حقيقية 2026-08-23):
        // `dvh` و`vh` و`svh` تبقى ٨٠٠ بينما المرئيُّ ٤٥٨ — فالسقفُ المبنيُّ
        // عليها يمتدّ تحت لوحة المفاتيح. واحتياطُه `100dvh` لمتصفّحٍ بلا
        // `visualViewport`. و**`mb` يُرفع بالمحجوب** لأن السقفَ وحدَه لا
        // يكفي: الحافّةُ السفلى مثبَّتةٌ بأسفل إطار التخطيط.
        attached
          ? "max-h-[calc(var(--vvh,100dvh)-76px)] mb-[var(--vv-bottom,0px)]"
          : "max-h-[calc(var(--vvh,100dvh)-168px)]",
        // **والظلُّ من السلّم لا رقمٌ مسطور**: كان `rgba(0,0,0,.25)` — يختفي في
        // الوضع الليلي (أسودُ على أسود) فتُقرأ الورقةُ ملتصقةً بالخريطة، ويثقل
        // في النهاري. و`shadow-sheet` معرَّفٌ في §6 لهذا الموضع بالضبط.
        "flex flex-col pt-8 shadow-sheet",
        className,
      )}
    >
      {/* المقبض: أعرضُ وبلون `--mut` لا `--brd` — كان يذوب في حدِّ الورقة */}
      <div className="mx-auto mb-14 h-6 w-44 shrink-0 rounded-full bg-muted" aria-hidden />
      {/* **`scr` لا `overflow-y-auto` وحدَها**: شريطُ التمرير مخفيٌّ في المحمول
          (`DESIGN.md` §2.11)، وبدونه يُرسم شريطٌ رماديٌّ على حافة الورقة.
          و`min-h-0` شرطٌ لا زينة: ابنُ `flex` لا ينكمش دون محتواه بدونها،
          فيتجاوز السقفَ ويعود القصُّ كما كان. **والحشوُ الجانبيُّ انتقل إلى
          هنا** من الحاوية، فيمرّ المحتوى تحت الحافة لا بجانبها. */}
      <div className={cn("scr min-h-0 flex-1 px-16", footer ? null : "pb-safe")}>
        {children}
      </div>
      {/* **القدمُ خارج منطقة التمرير** — و`border-t` فاصلٌ لا زينة: بدونه
          ينزلق المحتوى تحت سطحٍ مصمتٍ بلا حدٍّ يقول أين انتهت المنطقةُ
          الممرَّرة، فيُقرأ عطباً في الرسم. */}
      {footer ? (
        <div className="shrink-0 border-t border-line px-16 pt-12 pb-safe">{footer}</div>
      ) : null}
    </motion.div>
  );
}

export function DrawerSheet({
  open,
  onOpenChange,
  title,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  children: ReactNode;
}) {
  return (
    <Drawer.Root open={open} onOpenChange={onOpenChange} direction="bottom">
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <Drawer.Content
          dir="rtl"
          /* **سقفُها مساحةٌ محجوزةٌ من الأعلى لا نسبةٌ من الإطار** (البند ٩،
             قِيس على الجهاز 2026-08-14): كانت `max-h-[92dvh]`، و`dvh` يتبع
             الإطارَ فيتقلّص مع لوحة المفاتيح — قِيس: الإطارُ ٨٢٠ ⇐ ٤٦٢،
             فصارت الورقةُ ٤٢٥ وبدأت عند y=37، **وأزرارُ الرأس في 16..60**.
             فقُطعت الأيقوناتُ نصفَين، و`elementFromPoint` في منتصف الجرس يعيد
             **الورقةَ** لا الجرس — أي زرٌّ مقصوصٌ وميّتٌ معاً. وبالنسبة كان
             الرأسُ ينجو بستّة بكسلاتٍ عند الإطار الكامل: نجاةُ صدفةٍ لا قاعدة.
             و٧٦ = ١٦ (علوُّ الأزرار) + ٤٤ (قطرُها) + ١٦ (فرجة). */
          className="fixed inset-x-0 bottom-0 z-50 mx-auto flex max-h-[calc(100dvh-76px)]
            max-w-lg flex-col rounded-t-24 border-t border-line bg-surface outline-none"
        >
          <div className="mx-auto my-12 h-6 w-44 shrink-0 rounded-full bg-muted" aria-hidden />
          {title ? (
            <Drawer.Title className="px-20 pb-8 text-18 font-semibold text-ink">
              {title}
            </Drawer.Title>
          ) : (
            <Drawer.Title className="sr-only">قائمة</Drawer.Title>
          )}
          {/* `scr` لا `overflow-y-auto` وحدَها: شريطُ التمرير مخفيٌّ في المحمول
              (`DESIGN.md` §2.11) — وبدونه يُرسم شريطٌ رماديٌّ على حافة الورقة،
              وهو ما يُقرأ «غيرَ منتظم» (البند ٩). و`Stage.tsx` يفعلها أصلاً. */}
          <div className="scr min-h-0 flex-1 px-20 pb-safe">{children}</div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
