/** **استئذانٌ واحدٌ لكلِّ حذف** — يسمّي ما سيُحذف (البند ٤، §39٫٤).
 *
 * **شرطُ المالك بنصِّه**: «والحذفُ حيث يُسمح **يستأذن مرّةً بنصٍّ يسمّي ما
 * سيُحذف وعددَه**».
 *
 * ## ولمَ نصٌّ يسمّي لا «هل أنت متأكد؟»
 *
 * **سؤالٌ عامٌّ يُقرأ ولا يُفهم**: من ضغط «حذف» على الصفِّ الخطأ يقرأ «هل أنت
 * متأكد؟» **فيؤكّد** — لأن السؤالَ لا يقول عمّا يسأل. **واسمُ الصفِّ في
 * السؤال هو ما يوقف اليد**، وهو الفرقُ بين تأكيدٍ يحمي وتأكيدٍ يُمرَّر عليه.
 *
 * ## ولا يُحذف من رآه الناسُ أو استعمله
 *
 * **والحارسُ في الخلفية لا هنا**: `services/deletion.py` يسأل «أرآه أحدٌ أو
 * استعمله؟» ويردّ بالعربية ويقول العدد — **وإخفاءُ الزرِّ راحةٌ لا حماية**
 * (§21). فهذه الورقةُ تستأذن، **والرفضُ يأتي من الخادم بنصِّه** ويُعرض كما هو.
 *
 * ## والاستئذانُ مرّةٌ لا مرّتين
 *
 * **مرّتان تُعلّمان الضغطَ مرّتين**: من يؤكّد مرّتين في كلِّ حذفٍ يصير يضغط
 * الاثنتين بلا قراءة. **والمرّتان لِما يمسّ الجميع دفعةً واحدة** (البند ٨:
 * التحديثُ الإلزاميّ)، لا لصفٍّ واحد.
 */

import { useState } from "react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";

export function ConfirmDelete({
  /** **ما سيُحذف بالاسم** — لا «هذا العنصر». */
  what,
  /** سطرٌ يقول ما يترتّب عليه، أو ما يُفعل بدلاً منه. */
  note,
  /** **عددُ ما سيُحذف** حين يكون أكثرَ من واحد — يُعرض ولا يُخمَّن. */
  count,
  onConfirm,
  onClose,
}: {
  what: string;
  note?: ReactNode;
  count?: number;
  onConfirm: () => Promise<unknown>;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);

  return (
    <Modal title="تأكيدُ الحذف" onClose={onClose}>
      <p className="text-13 leading-note text-ink">
        سيُحذف: <b className="font-bold">{what}</b>
        {count !== undefined && count > 1 ? (
          <>
            {" "}
            — ومعه <b className="font-bold">{count}</b> صفّاً مرتبطاً به
          </>
        ) : null}
      </p>
      {note ? (
        <p className="mt-8 text-11.5 leading-note text-muted">{note}</p>
      ) : null}
      <p className="mt-8 text-11.5 leading-note text-muted">
        ولا يُحذف ما رآه الناسُ أو استعملوه — يُخفى بدل ذلك، والخادمُ يرفض
        ويقول السبب.
      </p>

      <div className="mt-16 flex gap-10">
        <Button
          size="md"
          variant="secondary"
          className="border-danger text-danger"
          loading={busy}
          onClick={() => {
            setBusy(true);
            void onConfirm().finally(() => setBusy(false));
          }}
        >
          احذف
        </Button>
        <Button size="md" variant="ghost" onClick={onClose}>
          تراجع
        </Button>
      </div>
    </Modal>
  );
}
