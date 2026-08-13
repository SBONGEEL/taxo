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
}: {
  children: ReactNode;
  className?: string;
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
        "pointer-events-auto rounded-t-sheet border-t border-line bg-surface",
        "px-5 pt-4 shadow-[0_-8px_32px_-12px_rgb(0_0_0/0.25)] pb-safe",
        className,
      )}
    >
      <div className="mx-auto mb-12 h-6 w-40 rounded-full bg-line" aria-hidden />
      {children}
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
          className="fixed inset-x-0 bottom-0 z-50 mx-auto flex max-h-[92dvh] max-w-lg
            flex-col rounded-t-sheet border-t border-line bg-surface outline-none"
        >
          <div className="mx-auto my-12 h-6 w-40 shrink-0 rounded-full bg-line" aria-hidden />
          {title ? (
            <Drawer.Title className="px-20 pb-8 text-18 font-semibold text-ink">
              {title}
            </Drawer.Title>
          ) : (
            <Drawer.Title className="sr-only">قائمة</Drawer.Title>
          )}
          <div className="min-h-0 flex-1 overflow-y-auto px-20 pb-safe">{children}</div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
