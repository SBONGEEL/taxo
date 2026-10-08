/** **صلاحياتُ المشرف الحاليّ من الحارس نفسِه** — `GET /admin/permissions` يردّ المجموعةَ الفعّالة (`permissions.for_user`)، لا نسخةً
 *  مكتوبةً هنا تفترق عنها.
 *
 * **ولمَ تُقرأ أصلاً**: بندٌ في العمود الجانبيّ **لا يظهر إلا لمن يملكها** (الملخّصاتُ المالية، SPEC §٦٥-د/٧) — والدورُ وحدَه لا
 * يقولها: `admin` على افتراضه **لا يملك** الحسّاسة. **وإخفاءُ البند راحةٌ لا حماية**: الخادمُ يردّ ٤٠٣ مهما رسمت الشاشة.
 *
 * **ونداءٌ واحدٌ لكلِّ جلسة**: العمودُ يُرسم مع كلِّ شاشة، فالجوابُ يُحفظ مفتاحُه معرّفُ المشرف — ومن خرج ودخل غيرُه قُرئ له ثانية.
 * **ولا يملك مشرفٌ تعديلَ صلاحياته** (`SelfElevation`)، فالمحفوظُ لا يبلى بيده؛ ومنحُ غيرِه له يظهر بعد إعادة الفتح.
 */

import { useEffect, useState } from "react";

import { listAdminPermissions } from "@/api/endpoints";
import { useSession } from "@/lib/session";

let cached: { userId: string; held: Promise<ReadonlySet<string>> } | null = null;

function heldBy(userId: string): Promise<ReadonlySet<string>> {
  if (cached === null || cached.userId !== userId) {
    const held = listAdminPermissions().then(
      (rows) => new Set(rows.find((row) => row.user_id === userId)?.permissions ?? []) as ReadonlySet<string>,
    );
    // **الفشلُ لا يُحفظ**: نداءٌ تعثّر مرّةً لا يُخفي البندَ الجلسةَ كلَّها
    held.catch(() => {
      if (cached?.held === held) cached = null;
    });
    cached = { userId, held };
  }
  return cached.held;
}

/** **أيملك المشرفُ الحاليُّ هذه الصلاحية؟** — `null` قبل الجواب، **و`false` إن تعذّر السؤال** (الخادمُ هو الحَكَم على أيِّ حال). */
export function useHolds(permission: string): boolean | null {
  const { user } = useSession();
  const [held, setHeld] = useState<boolean | null>(null);

  useEffect(() => {
    if (!user) return;
    let alive = true;
    heldBy(user.id)
      .then((set) => {
        if (alive) setHeld(set.has(permission));
      })
      .catch(() => {
        if (alive) setHeld(false);
      });
    return () => {
      alive = false;
    };
  }, [user, permission]);

  return held;
}
