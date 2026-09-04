/** سجلُّ الدفعات — **الصفُّ الذي كان ناقصاً، لا الزرّ** (قرارُ المالك 2026-08-19).
 *
 * `Rides.tsx` بلا زرِّ ردٍّ **بقرارٍ مكتوب**: الردُّ قرارٌ على **صفِّ دفعة**، ورحلةٌ
 * واحدةٌ قد تحمل صفّين (دفعٌ مختلط، ولا فهرسَ فريداً على `payments.ride_id`)، فزرٌّ
 * على الرحلة لا يعرف أيَّهما يردّ. وكان الأثرُ أن البابَ موجودٌ منذ المرحلة ٦-أ
 * ومختبَرٌ في ثلاثة ملفات — **ولا صفَّ في اللوحة يُضغط عليه**.
 *
 * **والردُّ يعود من حيث جاء المال**: المحفظةُ قيدٌ في دفتر الراكب، والبطاقةُ ردٌّ
 * عند المزوّد بلا قيدٍ له (مالُه لم يدخل رصيدَه أصلاً). والكاشُ وكليك خارج البابِ
 * كلِّه — قبضهما الكبتنُ بيده فلا نملك ردَّهما. فالزرُّ **يُعطَّل ويقول لماذا** بدل
 * أن يعمل ثم يرتدّ بـ٤٠٩: قاعدةُ اللوحة منذ شاشة الكباتن.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { listPayments, refundPayment } from "@/api/endpoints";
import type { Payment, PaymentMethod, PaymentStatus } from "@/api/types";
import { PaymentParties } from "@/components/profile/PaymentParties";
import { Shell } from "@/components/Shell";
import { Table, TableSearch } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field, Select } from "@/components/ui/Field";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Modal } from "@/components/ui/Modal";
import { money, moment } from "@/lib/format";
import { NO_RESULTS, useSearch } from "@/lib/search";
import { useCountry } from "@/lib/country";
import { useSession } from "@/lib/session";
import {
  PAYMENT_METHOD_LABEL,
  PAYMENT_STATUS_LABEL,
  PAYMENT_STATUS_TONE,
} from "@/lib/labels";
import { digits } from "@/lib/utils";

// **من `lib/labels.ts`** — وكانت هنا نسخةٌ ثالثةٌ لـ`METHOD_LABEL` تكتب
// «كوبون» بينما تكتبها الرحلاتُ والاشتراكاتُ «خصم كوبون»: **الشيءُ نفسُه
// باسمين في لوحةٍ واحدة**.
const METHOD_LABEL = PAYMENT_METHOD_LABEL;
const STATUS_LABEL = PAYMENT_STATUS_LABEL;
const STATUS_TONE = PAYMENT_STATUS_TONE;

/** ما تقبله الخلفيةُ للردّ — مرآةُ `payments.REFUNDABLE_METHODS` حرفياً. */
const REFUNDABLE: PaymentMethod[] = ["wallet", "card"];

/** **لماذا لا يمكن الردّ** — نصٌّ لكل سبب، لا زرٌّ معطَّلٌ صامت. */
function refusal(row: Payment): string | null {
  if (row.status === "refunded") return "رُدَّت هذه الدفعةُ من قبل";
  if (row.status !== "confirmed")
    return "لا يُردّ إلا ما تأكّد قبضُه — هذه لم تُؤكَّد بعد";
  if (!REFUNDABLE.includes(row.method))
    return "قبضه الكبتنُ بيده مباشرةً — لا تملك المنصّةُ ردَّه";
  return null;
}

export function PaymentsScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();
  const [status, setStatus] = useState<PaymentStatus | "">("");
  const [rows, setRows] = useState<Payment[] | null>(null);
  const [open, setOpen] = useState<Payment | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const search = useSearch();

  const load = useCallback(async () => {
    setRows(null);
    // **من الخادم لا في المتصفح**: القائمةُ مرقَّمة، وبحثٌ محلّيٌّ يقرأ
    // الصفحةَ المعروضةَ وحدَها فيبدو معطوباً لمن يعرف أن الصفَّ موجود
    setRows(await listPayments(status || undefined, country, search.term));
  }, [status, country, search.term]);

  useEffect(() => {
    void load().catch((caught: Error) => setError(caught.message));
  }, [load]);

  return (
    <Shell
      title="الدفعات"
      subtitle="كلُّ صفٍّ دفعةٌ واحدة — ورحلةٌ واحدةٌ قد تحمل صفّين"
      actions={
        <Select
          value={status}
          onChange={(event) =>
            setStatus(event.target.value as PaymentStatus | "")
          }
        >
          <option value="">كلُّ الحالات</option>
          {(Object.keys(STATUS_LABEL) as PaymentStatus[]).map((key) => (
            <option key={key} value={key}>
              {STATUS_LABEL[key]}
            </option>
          ))}
        </Select>
      }
    >
      {error ? <ErrorNote message={error} /> : null}
      {done ? <SuccessNote message={done} /> : null}

      <Table
        toolbar={
          <TableSearch
            value={search.text}
            onChange={search.setText}
            placeholder="اسمُ الراكب أو الكبتن، أو رقمُ أحدهما…"
          />
        }
        searching={search.searching}
        noResults={NO_RESULTS}
        columns="1.1fr 1.2fr .8fr .9fr 1fr 1.1fr auto"
        headers={["الرحلة", "الطرفان", "القناة", "المبلغ", "الحال", "التاريخ", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{
          title: "لا دفعات",
          hint: "لم تُسجَّل دفعةٌ بهذه الحال في هذا السوق.",
        }}
        render={(row) => {
          const why = refusal(row);
          return (
            <>
              <span className="truncate text-12 text-muted" dir="ltr">
                {row.ride_id.slice(0, 8)}
              </span>
              {/* **الطرفان بزرِّ ملفٍّ لكلٍّ** — §39٫١٢٫٤: «ومن أيِّ صفٍّ يخصّ
                  مستخدماً زرٌّ يفتح ملفَّه مباشرة». **وكان صفُّ الدفعة لا
                  يحمل إنساناً البتّة** فبقي غيرَ موصولٍ بعلّةٍ مكتوبة (§٤٧٫١٧)،
                  **والعلّةُ زالت بحقلٍ في العقد** لا بزرٍّ يبحث بالاسم */}
              <PaymentParties payment={row} />
              <span className="text-12.5 text-ink">
                {METHOD_LABEL[row.method] ?? row.method}
              </span>
              <span className="text-12.5 font-semibold text-ink" dir="ltr">
                {money(row.amount, row.currency)}
              </span>
              <Badge tone={STATUS_TONE[row.status] ?? "muted"}>
                {STATUS_LABEL[row.status] ?? row.status}
              </Badge>
              <span className="text-11.5 text-muted">
                {digits(moment(row.created_at))}
              </span>
              {isAdmin ? (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={why !== null}
                  title={why ?? undefined}
                  onClick={() => {
                    setOpen(row);
                    setReason("");
                    setError(null);
                  }}
                >
                  ردّ
                </Button>
              ) : (
                <span />
              )}
            </>
          );
        }}
      />

      {/* **السببُ إلزاميٌّ في الخلفية**، والشاشةُ تقوله قبل الضغط لا بعد الارتداد */}
      {open ? (
        <Modal title="ردُّ دفعة" onClose={() => setOpen(null)}>
          <div className="grid gap-12">
            <p className="text-12 leading-note text-muted">
              يُردّ{" "}
              <b className="text-ink" dir="ltr">
                {money(open.amount, open.currency)}
              </b>{" "}
              {open.method === "card"
                ? "إلى البطاقة نفسِها عبر المزوّد — ولا قيدَ في دفتر الراكب، فمالُه لم يدخل رصيدَه."
                : "إلى محفظة الراكب قيداً جديداً."}{" "}
              ويُكتب على الكبتن قيدٌ مضادٌّ بصافي ما قُيّد له. والدفترُ لا يُعدَّل:
              الردُّ قيدٌ لا محو.
            </p>
            <Field
              label="سبب الردّ (يُحفظ في سجلّ التدقيق)"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
            <Button
              loading={busy}
              disabled={reason.trim().length < 3}
              onClick={() => {
                setBusy(true);
                refundPayment(open.id, reason.trim())
                  .then(() => {
                    setOpen(null);
                    setDone("رُدَّت الدفعة");
                    return load();
                  })
                  .catch((caught) =>
                    setError(
                      caught instanceof ApiError ? caught.message : "تعذّر الردّ",
                    ),
                  )
                  .finally(() => setBusy(false));
              }}
            >
              تأكيد الردّ
            </Button>
          </div>
        </Modal>
      ) : null}
    </Shell>
  );
}
