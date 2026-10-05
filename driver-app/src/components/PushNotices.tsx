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

import { useSyncExternalStore } from "react";

import { play } from "@/lib/sound";
import { firstSighting } from "@/lib/notice";

import "@/taxo2";

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
  if (!current.length) return null;

  // **بلغة TAXO 2.0 في المظهرين** (§٦٢/١ و/٨) — `t2-notice`: كانت بطاقةً بيضاءَ بلغةٍ سابقةٍ فوق ليل الكبتن
  return (
    <div className="t2 t2-notices">
      {current.map((notice) => (
        <div key={notice.id} className="t2-notice" role="status">
          <span className="t2-notice-icon" aria-hidden="true">
            <span className="t2-icon">notifications</span>
          </span>
          <div className="t2-notice-main">
            <p className="t2-notice-title">{notice.title}</p>
            {notice.body ? <p className="t2-notice-body">{notice.body}</p> : null}
          </div>
          <button
            type="button"
            className="t2-notice-close"
            onClick={() => emit(notices.filter((item) => item.id !== notice.id))}
            aria-label="إغلاق"
          >
            <span className="t2-icon" aria-hidden="true">
              close
            </span>
          </button>
        </div>
      ))}
    </div>
  );
}
