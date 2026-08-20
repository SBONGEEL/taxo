/** منحُ عرضٍ لجمهور `manual` — **بابٌ بلا زرّ منذ البند ٥٤** (قرارُ المالك 2026-08-19).
 *
 * الجمهورُ مبنيٌّ ومختبَرٌ في الخلفية، و`applies_to` تقرأ صفَّ المنح — فبلا زرٍّ
 * كان **عرضٌ لا يصله أحد**: يُنشأ بجمهورٍ يدويٍّ ثم لا يُمنح لأحدٍ أبداً.
 *
 * **والمنتقي بحثٌ لا قائمة** (أمرُ المالك): سوقٌ فيه ألفُ كبتنٍ قائمتُه غيرُ
 * قابلةٍ للقراءة، والبحثُ بالاسم أو الرقم هو ما يفعله المشرفُ فعلاً — يعرف من
 * يقصد قبل أن يفتح الشاشة.
 *
 * **والمنحُ لا يمنح خصماً بذاته**: هو ما يجعل العرضَ **منطبقاً** على هذا الكبتن،
 * والخصمُ يُحسب في `subscriptions._create` وحدَها — فالحدُّ لكل كبتن، وسقفُ
 * الميزانية، وقفلُ صفِّ العرض، كلُّها تعمل عند الشراء كما تعمل لأيِّ جمهورٍ آخر.
 * **ولذلك لا يُرفض المنحُ لنفاد الميزانية**: قد تتحرر قبل أن يشتري، ورفضُه اليومَ
 * يمنع منحاً صحيحاً لغد.
 */

import { useState } from "react";

import { ApiError } from "@/api/client";
import {
  grantSubscriptionOffer,
  listDrivers,
  listOfferGrants,
} from "@/api/endpoints";
import type { AdminDriverRow, CountryCode, OfferGrant } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { EmptyNote, Spinner } from "@/components/ui/Feedback";
import { Modal } from "@/components/ui/Modal";
import { digits } from "@/lib/utils";

export function OfferGrants({
  offerId,
  offerName,
  country,
  onClose,
  onError,
  onGranted,
}: {
  offerId: string;
  offerName: string;
  country: CountryCode;
  onClose: () => void;
  onError: (message: string) => void;
  onGranted: (message: string) => void;
}) {
  const [rows, setRows] = useState<OfferGrant[] | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<AdminDriverRow[] | null>(null);
  const [picked, setPicked] = useState<AdminDriverRow | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  if (!loaded) {
    setLoaded(true);
    listOfferGrants(offerId)
      .then(setRows)
      .catch((caught: Error) => onError(caught.message));
  }

  return (
    <Modal title={`منحُ «${offerName}»`} onClose={onClose}>
      <div className="grid gap-14">
        <section>
          <h4 className="mb-6 text-12.5 font-bold text-ink">
            ابحث عن الكبتن
          </h4>
          <div className="flex items-end gap-10">
            <Field
              className="flex-1"
              label="بالاسم أو الرقم"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setFound(null);
                setPicked(null);
                listDrivers({ q: query.trim(), country_code: country, limit: 10 })
                  .then(setFound)
                  .catch((caught) =>
                    onError(
                      caught instanceof ApiError
                        ? caught.message
                        : "تعذّر البحث",
                    ),
                  );
              }}
            >
              ابحث
            </Button>
          </div>

          {found?.length === 0 ? (
            <EmptyNote
              title="لا نتائج"
              hint="لا كبتنَ بهذا الاسم أو الرقم في هذا السوق."
            />
          ) : null}
          {found && found.length > 0 ? (
            <ul className="mt-10 grid gap-6">
              {found.map((row) => (
                <li key={row.driver_id}>
                  <button
                    type="button"
                    onClick={() => setPicked(row)}
                    className={
                      "flex w-full items-center justify-between rounded-12 border px-12 py-8 text-start " +
                      (picked?.driver_id === row.driver_id
                        ? "border-ink bg-surface-2"
                        : "border-line")
                    }
                  >
                    <span className="text-12.5 text-ink">{row.name}</span>
                    <span className="text-11.5 text-muted" dir="ltr">
                      {digits(row.phone)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </section>

        {picked ? (
          <section className="grid gap-10">
            <Field
              label="سببُ المنح (يدخل سجلّ التدقيق)"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
            <Button
              size="sm"
              loading={busy}
              disabled={note.trim().length < 3}
              onClick={() => {
                setBusy(true);
                grantSubscriptionOffer(offerId, {
                  driver_id: picked.driver_id,
                  note: note.trim(),
                })
                  .then(() => {
                    setNote("");
                    setPicked(null);
                    onGranted(`مُنح العرضُ لـ${picked.name}`);
                    return listOfferGrants(offerId).then(setRows);
                  })
                  .catch((caught) =>
                    onError(
                      caught instanceof ApiError
                        ? caught.message
                        : "تعذّر المنح",
                    ),
                  )
                  .finally(() => setBusy(false));
              }}
            >
              امنح
            </Button>
            <p className="text-11 leading-note text-muted">
              المنحُ يجعل العرضَ منطبقاً عليه، ولا يمنحه خصماً بذاته: الخصمُ
              يُحسب عند الشراء، فالحدُّ لكلِّ كبتن وسقفُ الميزانية والقفلُ تعمل
              هناك كما لأيِّ جمهورٍ آخر.
            </p>
          </section>
        ) : null}

        <section>
          <h4 className="mb-6 text-12.5 font-bold text-ink">المنوحون</h4>
          {rows === null ? (
            <Spinner className="mx-auto" />
          ) : rows.length === 0 ? (
            <EmptyNote
              title="لم يُمنح لأحدٍ بعد"
              hint="عرضٌ بجمهورٍ يدويٍّ لا يصل أحداً حتى يُمنح."
            />
          ) : (
            <ul className="grid gap-6">
              {rows.map((row) => (
                <li
                  key={row.id}
                  className="rounded-12 border border-line px-12 py-8"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-12.5 text-ink">
                      {row.driver_name ?? row.driver_id.slice(0, 8)}
                    </span>
                  </div>
                  {row.note ? (
                    <p className="mt-4 text-11 leading-note text-muted">
                      {row.note}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </Modal>
  );
}
