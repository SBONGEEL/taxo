/** **ما يملكه صاحبُ الجلسة من الصلاحيات** — للرسم لا للحراسة (SPEC §٦٥-د/٧ · §٦٦-ب/١٠، §39٫٥).
 *
 * **مصدرُه ما تقرؤه مصفوفةُ الصلاحيات نفسُها** (`GET /admin/permissions` — `for_user` في الخلفية، **أي المجموعةُ الفعّالة لا
 * الصفوف**): صفُّ صاحب الجلسة منها. **فلا بابَ ثانٍ ولا قاعدةٌ تُعاد هنا** — و«المشرفُ الكامل بلا صفوف» يُقرأ كما يُقرأ هناك:
 * الكلُّ **إلا الحسّاسة** (`permissions.SENSITIVE` — قراءةُ المحادثات والاستماعُ إلى التسجيلات والملخّصاتُ المالية، لا تُعطى إلا بالاسم).
 *
 * **والإخفاءُ راحةٌ لا حماية** (§21): بندُ الملخّصات في العمود، وتبويبُ المحادثة وصفحةُ البلاغات وزرُّ الاستماع تُرسم لمن يملكها،
 * **والخادمُ يردّ غيرَه** — والشاشةُ تقول الردَّ بنصِّه إن وقع (مصفوفةٌ تغيّرت بعد القراءة).
 *
 * **ومرّةً لكلِّ جلسة** — الإطارُ يُرسم مع كلِّ شاشة، ونداءٌ مع كلِّ رسمٍ يملأ السجلّ؛ **ويُعاد بعد كلِّ تعديلٍ في المصفوفة**
 * (`refreshMyPermissions`) فلا يبقى زرٌّ لمن نزع صلاحيتَه للتوّ. **وصار بيتاً واحداً لبابين** (الملخّصاتُ والمحادثة، دُمجا ٢٠٢٦-١٠-٠٨)
 * كانا قد كتب كلٌّ منهما نسختَه — **ونسختان لسؤالٍ واحدٍ تفترقان**.
 */

import { useEffect, useState } from "react";

import { listAdminPermissions } from "@/api/endpoints";
import { useSession } from "@/lib/session";

/** **قراءةُ محادثات الرحلات وبلاغاتها** — مرآةُ `AdminPermission.TRIP_CHATS_READ`. */
export const TRIP_CHATS_READ = "trip_chats.read";
/** **الاستماعُ إلى تسجيلات المكالمات** — مرآةُ `AdminPermission.CALL_RECORDINGS_LISTEN`. */
export const CALL_RECORDINGS_LISTEN = "call_recordings.listen";

let cached: { userId: string; answer: Promise<ReadonlySet<string>> } | null = null;
const listeners = new Set<() => void>();

function load(userId: string): Promise<ReadonlySet<string>> {
  if (cached?.userId !== userId) {
    cached = {
      userId,
      answer: listAdminPermissions()
        .then((rows) => new Set(rows.find((row) => row.user_id === userId)?.permissions ?? []))
        // **تعذّرُ القراءة لا يَعِد بشيء** — بلا جوابٍ لا تُرسم أبوابُ الحسّاس، والخادمُ يحكم على ما سواها
        .catch(() => new Set<string>()),
    };
  }
  return cached.answer;
}

/** يُنادى بعد تعديل المصفوفة — فيُقرأ ما يملكه صاحبُ الجلسة من جديد. */
export function refreshMyPermissions(): void {
  cached = null;
  for (const listener of listeners) listener();
}

/** صلاحياتُ صاحب الجلسة — **`null` حتى تصل**: لا يُرسم ما ينتظرها، ولا يُرسم ثمّ يختفي. */
export function useMyPermissions(): ReadonlySet<string> | null {
  const { user } = useSession();
  const [held, setHeld] = useState<ReadonlySet<string> | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const bump = () => setVersion((value) => value + 1);
    listeners.add(bump);
    return () => {
      listeners.delete(bump);
    };
  }, []);

  useEffect(() => {
    if (!user) {
      setHeld(null);
      return;
    }
    let live = true;
    void load(user.id).then((answer) => {
      if (live) setHeld(answer);
    });
    return () => {
      live = false;
    };
  }, [user, version]);

  return held;
}

/** **أيملك صاحبُ الجلسة هذه الصلاحية؟** — `null` قبل الجواب، **و`false` إن تعذّر السؤال** (الخادمُ هو الحَكَم على أيِّ حال). */
export function useHolds(permission: string): boolean | null {
  const held = useMyPermissions();
  return held === null ? null : held.has(permission);
}
