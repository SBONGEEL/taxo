/** «السفراء والمميّزون» — SPEC §١١١-د/٤ (أمرُ المالك ٢٠٢٦-١١-٢١ الخامس، البند ٣).
 *
 * **كلُّ دائمٍ ساري وكلُّ «عدد أيام» لم ينقضِ** في سوق المبدّل، ببحثٍ بالاسم والهاتف — والمنحُ نفسُه من «تسجيل اشتراكٍ مقبوض».
 *
 * **والنزعُ للمالك وحدَه، بسببٍ إلزاميٍّ وتأكيد**: يُلغى الصفُّ الدائمُ وحدَه بمسار الإلغاء القائم (لا حذفَ ولا تعديلَ تاريخ)،
 * **وما دفعه الكبتنُ قبله يبقى يغطّيه**. وما يعود إلى محفظته يُقرأ **قبل** الضغط من الخلفية (`revoke_refund`) لا من حسابٍ هنا.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { listGiftSubscriptions, revokeAmbassador } from "@/api/endpoints";
import type { GiftRow } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Table, TableSearch } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Modal } from "@/components/ui/Modal";
import { useCountry } from "@/lib/country";
import { day, money } from "@/lib/format";
import { NO_RESULTS, useSearch } from "@/lib/search";
import { useSession } from "@/lib/session";
import { digits } from "@/lib/utils";

const COLUMNS = "1.4fr 1fr 1fr 0.9fr 0.9fr 0.8fr";

function kindLabel(row: GiftRow): string {
  if (row.is_permanent) return "دائم · سفير TAXO";
  return `${digits(String(row.custom_days ?? 0))} يوماً`;
}

export function AmbassadorsScreen() {
  const { country } = useCountry();
  const { user } = useSession();
  const isOwner = Boolean(user?.roles?.includes("owner"));
  const search = useSearch();
  const [rows, setRows] = useState<GiftRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<GiftRow | null>(null);

  const load = useCallback(async () => {
    setRows(null);
    setRows(await listGiftSubscriptions({ country_code: country, q: search.term }));
  }, [country, search.term]);

  useEffect(() => {
    load().catch((caught) =>
      setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة القائمة"),
    );
  }, [load]);

  return (
    <Shell
      title="السفراء والمميّزون"
      subtitle="الاشتراكُ الدائم و«عدد أيام» — المنحُ من «تسجيل اشتراكٍ مقبوض»، والنزعُ للمالك وحدَه بسبب"
    >
      <ErrorNote message={error} />
      <SuccessNote message={done} />

      <Table
        toolbar={
          <TableSearch value={search.text} onChange={search.setText} placeholder="اسمُ الكبتن أو رقمُه…" />
        }
        searching={search.searching}
        noResults={NO_RESULTS}
        columns={COLUMNS}
        headers={["الكبتن", "النوع", "البداية", "الانتهاء", "المبلغ", ""]}
        rows={rows}
        keyOf={(row) => row.subscription_id}
        empty={{
          title: "لا سفراءَ ولا أيّامَ ممنوحةٌ في هذه الدولة",
          hint: "يُمنحان من «الاشتراكات والباقات» ← «تسجيل اشتراكٍ مقبوض».",
        }}
        render={(row) => (
          <>
            <span className="min-w-0">
              <span className="block truncate font-semibold text-ink">{row.name}</span>
              <span dir="ltr" className="block text-10.5 text-muted">{row.phone ?? ""}</span>
            </span>
            <span>
              <Badge tone={row.is_permanent ? "ink" : "ok"}>{kindLabel(row)}</Badge>
            </span>
            <span className="text-muted">{day(row.starts_at)}</span>
            <span className="text-muted">{row.is_permanent ? "لا ينتهي" : day(row.expires_at)}</span>
            <span className="font-semibold text-ink">{money(row.amount_paid, row.currency)}</span>
            <span className="flex justify-end">
              {isOwner && row.is_permanent ? (
                <button
                  type="button"
                  onClick={() => setRevoking(row)}
                  className="text-11.5 font-semibold text-danger"
                >
                  نزع
                </button>
              ) : null}
            </span>
          </>
        )}
      />

      {revoking ? (
        <RevokeModal
          row={revoking}
          onClose={() => setRevoking(null)}
          onDone={(message) => {
            setDone(message);
            setRevoking(null);
            void load();
          }}
          onError={(caught) => setError(caught instanceof ApiError ? caught.message : "تعذّر النزع")}
        />
      ) : null}
    </Shell>
  );
}

/** ورقةُ تأكيد النزع — **سببٌ إلزاميّ، وما يعود إلى محفظته معروضٌ قبل الضغط**. */
function RevokeModal({
  row,
  onClose,
  onDone,
  onError,
}: {
  row: GiftRow;
  onClose: () => void;
  onDone: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <Modal title={`نزعُ «سفير TAXO» عن ${row.name}`} onClose={onClose}>
      <p className="mb-14 text-12.5 leading-note text-muted">
        يُلغى الاشتراكُ الدائمُ وحدَه بمسار الإلغاء — <b className="text-ink">ولا يُحذف صفٌّ</b>. ما دفعه الكبتنُ قبله يبقى يغطّيه،
        وإن لم يبقَ له اشتراكٌ خرج من الاستقبال. ويصله إشعار.
      </p>
      <div className="rounded-14 border border-line bg-surface-2 px-14 py-12">
        <div className="flex items-baseline justify-between gap-10">
          <span className="text-12.5 text-muted">ما يعود إلى محفظته</span>
          <span className="text-18 font-bold text-ink">{money(row.revoke_refund, row.currency)}</span>
        </div>
      </div>
      <div className="mt-14">
        <Field
          label="سبب النزع"
          name="reason"
          placeholder="يدخل سجلَّ التدقيق باسمك"
          value={reason}
          maxLength={300}
          onChange={(event) => setReason(event.target.value)}
        />
      </div>
      <div className="mt-14 flex gap-10">
        <Button
          size="md"
          variant="secondary"
          className="border-danger text-danger"
          disabled={busy || reason.trim().length < 3}
          onClick={() => {
            setBusy(true);
            revokeAmbassador(row.driver_id, reason.trim())
              .then((result) =>
                onDone(`نُزع «سفير TAXO» عن ${row.name} — رُدّ ${money(result.refund, row.currency)}`),
              )
              .catch((caught) => {
                onError(caught);
                setBusy(false);
              });
          }}
        >
          انزع
        </Button>
        <Button size="md" variant="ghost" onClick={onClose}>
          تراجع
        </Button>
      </div>
    </Modal>
  );
}
