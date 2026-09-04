/** إشعارٌ جماعيٌّ إلى من اختيرَ — **الفرع ٣ من §39٫١٢، ثانيه** (§50).
 *
 * ## وصلٌ لا بناء
 *
 * **نصُّ §٤٧٫١١**: «**وبابُ الرسالة الفرديّة قائمٌ** (§46) فالجماعيُّ وصلٌ لا
 * بناء». فهذا المكوّنُ ينادي `POST /admin/users/{id}/notify` **نفسَه** الذي
 * يستعمله درجُ الملفّ — **وصفرُ بابٍ جديدٍ في الخلفية**، وصفرُ نصٍّ عربيٍّ
 * ثانٍ لرسالةٍ لها نصٌّ واحد.
 *
 * ## والنداءاتُ متسلسلةٌ لا متوازية
 *
 * **قاعدةٌ مكتوبةٌ في §٤٧٫١١ لاعتماد الوثائق، وتسري هنا بحرفها**:
 * `Promise.all` يرسل خمسين طلباً تتسابق، **وكلُّ واحدٍ منها يكتب صفَّ تدقيقٍ
 * وصفَّ صندوقِ واردٍ ويوقظ جهازاً**. والتسلسلُ يجعل الإخفاقَ في الأثناء
 * **معلوماً بعدده** لا مجهولاً.
 *
 * ## والجملةُ تقول العددَين — **ولا تقول «تمّ»**
 *
 * «أُرسلت إلى N — وأخفقت M». **ورسالةٌ تقول «تمّ» بعد إخفاق ثلاثةٍ من عشرة
 * تكذب على من يقرؤها**، وهي عينُ درس «لا نجاحَ يُعلَن قبل التحقق ممّا كُتب».
 *
 * ## و**لا يُرسَل إلى موظّف** — والخلفيةُ هي الحارس
 *
 * `notify_one_user` يردّ من كان `admin` أو `support` بنصٍّ صريح: «القناةُ
 * لصاحب التطبيق». **والواجهةُ لا تعيد بناءَ ذلك الشرط** — تعرضه حين يقع،
 * **فلا يفترق حارسان لشيءٍ واحد**.
 */

import { useState } from "react";

import { ApiError } from "@/api/client";
import { notifyUser } from "@/api/endpoints";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { digits } from "@/lib/utils";

/** أدنى ما يقبله `UserMessageIn` في الخلفية — **مرآةٌ لا رقمٌ مخترع**. */
const MIN_TITLE = 2;
const MIN_BODY = 2;
const MAX_TITLE = 80;
const MAX_BODY = 600;

export function BulkNotify({
  userIds,
  onDone,
  onClear,
}: {
  /** **`users.id` لا `drivers.id`** — والبابُ بابُ حساب. */
  userIds: string[];
  /** يُنادى بالجملة التي تقول ماذا وقع، **بعددَيها**. */
  onDone: (message: string) => void;
  onClear: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const ready =
    title.trim().length >= MIN_TITLE && body.trim().length >= MIN_BODY;

  async function send() {
    setBusy(true);
    setError(null);
    setSent(0);
    let ok = 0;
    let firstFailure: string | null = null;
    // **متسلسلٌ بقصد** — والعدُّ يتقدّم أمام العين فلا يبدو الحوارُ معلَّقاً
    for (const id of userIds) {
      try {
        await notifyUser(id, { title: title.trim(), body: body.trim() });
        ok += 1;
        setSent(ok);
      } catch (caught) {
        if (firstFailure === null) {
          firstFailure =
            caught instanceof ApiError ? caught.message : "تعذّر الإرسال";
        }
      }
    }
    setBusy(false);
    const failed = userIds.length - ok;
    if (ok === 0) {
      setError(firstFailure ?? "لم تصل رسالةٌ واحدة.");
      return;
    }
    setOpen(false);
    setTitle("");
    setBody("");
    onClear();
    onDone(
      failed === 0
        ? `أُرسلت إلى ${digits(ok)} صندوقَ وارد.`
        : // **العددان معاً** — و«تمّ» وحدَها تكذب على من أخفق عنده ثلاثة
          `أُرسلت إلى ${digits(ok)} — وأخفقت ${digits(failed)}: ${firstFailure ?? ""}`,
    );
  }

  return (
    <>
      <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
        أرسِل إشعاراً
      </Button>

      {open ? (
        <Modal
          title={`رسالةٌ إلى ${digits(userIds.length)} حساباً`}
          onClose={() => (busy ? undefined : setOpen(false))}
        >
          <Field
            label="العنوان"
            name="bulk_title"
            value={title}
            maxLength={MAX_TITLE}
            onChange={(event) => setTitle(event.target.value)}
          />
          <div className="mt-8">
            <label className="mb-6 block text-11.5 text-muted">النص</label>
            <textarea
              name="bulk_body"
              rows={4}
              value={body}
              maxLength={MAX_BODY}
              onChange={(event) => setBody(event.target.value)}
              className="w-full rounded-12 border border-line bg-surface px-12 py-10 text-12 leading-note text-ink"
            />
          </div>
          <p className="mt-8 text-10.5 leading-note text-muted">
            تصل صندوقَ الوارد في تطبيق كلِّ واحدٍ منهم، وتُدفع إلى جهازه إن كان
            مغلقاً — ونصُّها يُحفظ في سجل التدقيق كما كُتب، لكلِّ حساب.
          </p>
          {/* **ولا يُرسَل إلى موظّف** — تُقال قبل الضغط لا بعد الارتداد */}
          <p className="mt-6 text-10.5 leading-note text-muted">
            وحسابُ الموظّف يُردّ من الخلفية: القناةُ لصاحب التطبيق.
          </p>

          {error ? (
            <p className="mt-10 rounded-12 border border-line bg-surface-2 px-12 py-10 text-11.5 leading-note text-danger">
              {error}
            </p>
          ) : null}

          <div className="mt-16 flex items-center gap-10">
            <Button size="sm" disabled={!ready || busy} loading={busy} onClick={() => void send()}>
              أرسِل
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={busy}
              onClick={() => setOpen(false)}
            >
              إلغاء
            </Button>
            {busy ? (
              // **التقدّمُ يُرى** — إرسالٌ متسلسلٌ إلى خمسين بلا عدّادٍ يبدو معلَّقاً
              <span className="text-11.5 text-muted">
                {digits(sent)} من {digits(userIds.length)}…
              </span>
            ) : null}
          </div>
        </Modal>
      ) : null}
    </>
  );
}
