/** **الورقةُ المنبثقةُ بلغة TAXO 2.0** — «إلى أين؟» للبحث (R29d) و«إنهاء كل الجلسات» (R23b).
 *
 * **السلوكُ سلوكُ `DrawerSheet` القائم بعينه** (`components/ui/Sheet`، `vaul`): تُغلق بالسحب وباللمس خارجها وبزرّ الرجوع،
 * وعنوانُها يُعلَن لقارئ الشاشة، **وسقفُها مساحةٌ محجوزةٌ من الأعلى لا نسبةٌ من الإطار** (البند ٩، قِيس على الجهاز ٢٠٢٦-٠٨-١٤)
 * — **والوجهُ وجهُ أوراق R06–R09**: حجرٌ بزاويتين ٣٠ ومقبضٍ وظلٍّ، والعنوانُ كـ«إلى أين؟» في ورقة الخريطة (`WhereToSheetT2`).
 */
import type { ReactNode } from "react";
import { Drawer } from "vaul";

import "@/taxo2";
import "./kit.css";

export function DrawerT2({
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
        <Drawer.Overlay className="t2 t2-drawer-scrim" />
        <Drawer.Content dir="rtl" className="t2 t2-drawer">
          <div className="t2-drawer-grab" aria-hidden="true" />
          {title ? (
            <Drawer.Title className="t2-drawer-title">{title}</Drawer.Title>
          ) : (
            <Drawer.Title className="sr-only">قائمة</Drawer.Title>
          )}
          {/* **منطقةُ التمرير تحت العنوان** — وما زاد عن السقف يُمرَّر لا يُقصّ (`check:sheet` يقيسها في الورقة القائمة) */}
          <div className="t2-drawer-body">{children}</div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
