/** البلاغُ داخل التطبيق والتطبيقُ أمامَ صاحبه — **بصوته** (§٦١-ل/٣).
 *
 * **يصل من طريقين** (`presentNotice`): إشعارٌ والتطبيقُ في المقدّمة — والنظامُ
 * لا يرسم شيئاً حينها (`lib/push.ts`) — **وبلاغُ المقبس** لما لا يرسمه التطبيقُ
 * من حدثٍ له: بقشيشٌ، اشتراكٌ يقارب الانتهاء، نتيجةُ وثيقة (`notifications.
 * RENDERED_IN_APP` في الخلفية). **وكانا يصلان صامتين بلا أثر**: الخلفيةُ تحجب
 * الإشعارَ عن مقبسٍ حيّ، والمقبسُ لا يحمل لهما حدثاً يُرسم.
 *
 * **ومظهرُه مظهرُ بلاغ الراكب** (`customer-app/src/components/Toasts.tsx`) —
 * فبلاغٌ واحدٌ بوجهين في التطبيقين يُقرأ نظاماً، **وبوجهين مختلفين يُقرأ تطبيقين
 * لا يعرف أحدُهما الآخر**.
 */

import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { useSyncExternalStore } from "react";

import { play } from "@/lib/sound";
import { firstSighting } from "@/lib/notice";

interface Notice {
  id: number;
  title: string;
  body?: string;
}

let notices: Notice[] = [];
let nextId = 0;
const listeners = new Set<() => void>();

function emit(next: Notice[]): void {
  notices = next;
  for (const listener of listeners) listener();
}

/** يعرض بلاغاً ستَّ ثوانٍ — **كبلاغ الراكب** (`lib/ride.tsx` → `notify`). */
function showPushNotice(title: string, body?: string): void {
  const id = ++nextId;
  emit([...notices, { id, title, body }]);
  window.setTimeout(() => emit(notices.filter((notice) => notice.id !== id)), 6_000);
}

/** **البابُ الواحدُ للبلاغ** — من الإشعار ومن المقبس معاً.
 *
 * **والغائبُ لا يُرسم له شيء**: الإشعارُ نفسُه يصله من النظام بصوت قناته،
 * فرسمُه في الخلفية بلاغان وصوتان لحدثٍ واحد. **والطلبُ الوارد لا بلاغَ له**:
 * بطاقتُه وحلقتُه من المقبس أو من `OfferAlert`، وبلاغٌ فوقها يغطّي ما جاءت تعرضه.
 *
 * **والبقشيشُ بصوت المال** (قِيس 2026-08-30) — `credited` كانت مبنيّةً بلا سلكٍ
 * إليه؛ **وما عداه «الإشعار»** تحت مفتاح «ما عدا الطلب».
 */
export function presentNotice(notice: {
  title?: string;
  body?: string;
  data?: Record<string, string>;
}): void {
  const { title, body, data } = notice;
  if (!title || document.hidden || data?.type === "ride_offer") return;
  if (!firstSighting(title, body)) return;
  showPushNotice(title, body);
  play(data?.type === "tip_received" ? "credited" : "notify");
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function PushNotices() {
  const current = useSyncExternalStore(subscribe, () => notices);

  return (
    <div className="pointer-events-none fixed inset-x-0 top-0 z-[60] mx-auto flex max-w-lg flex-col gap-8 px-16 pt-safe">
      <AnimatePresence initial={false}>
        {current.map((notice) => (
          <motion.div
            key={notice.id}
            initial={{ opacity: 0, y: -16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            className="pointer-events-auto flex items-start gap-8 rounded-12 border border-line bg-surface px-16 py-12 shadow-lg"
            role="status"
          >
            <div className="min-w-0 flex-1">
              <p className="font-medium text-ink">{notice.title}</p>
              {notice.body ? <p className="mt-2 text-14 text-muted">{notice.body}</p> : null}
            </div>
            <button
              type="button"
              onClick={() => emit(notices.filter((item) => item.id !== notice.id))}
              className="pressable rounded-8 p-4 text-muted transition hover:bg-surface-2"
              aria-label="إغلاق"
            >
              <X className="size-16" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
