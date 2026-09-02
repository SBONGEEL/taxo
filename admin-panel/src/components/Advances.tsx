/** سلفُ الكباتن (البند ١٥) — القائمةُ ومتبقّيها، والشطبُ بقرارٍ مسجَّل.
 *
 * **وموضعُها تحت قائمة الكباتن** كطلبات إلغاء التفعيل: السلفةُ حالٌ من أحوال
 * الكبتن تُقرأ حيث تُقرأ حالتُه، لا في شاشةِ مالٍ منفصلةٍ يُبحث عنها.
 *
 * **ولا زرَّ «سدّد عنه»**: السدادُ يقع في محفظته هو — إمّا اقتطاعاً من رحلةٍ
 * أو بضغطةٍ منه. وزرٌّ هنا يعني كتابةَ مالٍ من بابٍ ثانٍ، وهو ما لا يفعله
 * هذا الجدول ولا أيُّ شاشةٍ في اللوحة.
 *
 * **والشطبُ ليس سداداً**: يعترف بأن المال لن يعود — ولا قيدَ يُكتب في الدفتر،
 * لأن قيداً يقول «سدَّد» يجعل الكشفَ يكذب على صاحبه بعد شهر.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { listAdvances, writeOffAdvance } from "@/api/endpoints";
import type { AdvanceRow } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Table, TableSearch } from "@/components/Table";
import { ADVANCE_STATUS_LABEL, ADVANCE_STATUS_TONE } from "@/lib/labels";
import { NO_RESULTS, useSearch } from "@/lib/search";
import { day, money } from "@/lib/format";

// **من `lib/labels.ts`** — يقرؤهما الملفُّ الشخصيُّ أيضاً (§37)
const TONE = ADVANCE_STATUS_TONE;
const LABEL = ADVANCE_STATUS_LABEL;

export function Advances({ onError }: { onError: (message: string) => void }) {
  const [rows, setRows] = useState<AdvanceRow[]>([]);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const search = useSearch();

  const load = useCallback(() => {
    listAdvances(undefined, search.term)
      .then(setRows)
      .catch((caught) =>
        onError(caught instanceof ApiError ? caught.message : "تعذّر التحميل"),
      );
  }, [search.term, onError]);

  useEffect(load, [load]);

  async function drop(row: AdvanceRow) {
    const reason = reasons[row.id]?.trim();
    if (!reason) {
      onError("سبب الشطب مطلوب — خسارةٌ بلا سببٍ مكتوبٍ لا يملكها أحد");
      return;
    }
    setBusy(row.id);
    try {
      await writeOffAdvance(row.id, reason);
      load();
    } catch (caught) {
      onError(caught instanceof ApiError ? caught.message : "تعذّر الشطب");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="card mt-16 p-16">
      <h2 className="mb-4 text-15 font-bold text-ink">سلف الكباتن</h2>
      <p className="mb-12 text-12 text-muted">
        تُقتطع تلقائياً من أرباح الرحلات. وبانقضاء المهلة يخرج صاحبُها من
        التوزيع حتى يسدّد. والشطبُ اعترافٌ بالخسارة — لا يُكتب له قيدٌ في
        الدفتر، ويرفع الإيقاف.
      </p>

      <Table
        toolbar={
          <TableSearch
            value={search.text}
            onChange={search.setText}
            placeholder="اسمُ الكبتن أو رقمُه…"
          />
        }
        searching={search.searching}
        noResults={NO_RESULTS}
        height="compact"
        columns="1fr 0.9fr 0.9fr 0.8fr 0.9fr 1.6fr"
        headers={["الكبتن", "المبلغ", "المتبقّي", "الحالة", "المهلة", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{ title: "لا سلف", hint: "لم تُصرف سلفةٌ بعد." }}
        render={(row) => (
          <>
            <span className="font-mono text-11.5">{row.driver_id.slice(0, 8)}</span>
            <span className="text-12 text-ink">
              {money(row.amount, row.currency)}
            </span>
            <span className="text-12 text-ink">
              {money(row.remaining, row.currency)}
            </span>
            {/* **الشارةُ في `span` لا عاريةً في الشبكة**: خليةُ `grid`
                تمطّ ابنَها على عرض العمود، فتخرج حبّةٌ بعرض الجدول — وهو
                ما تفعله `Rides.tsx` بالضبط ولنفس السبب */}
            <span className="flex items-center gap-6">
              <Badge tone={TONE[row.status]}>{LABEL[row.status]}</Badge>
            </span>
            <span
              className={row.overdue ? "text-12 text-danger" : "text-12 text-muted"}
            >
              {day(row.due_at)}
            </span>
            {row.status === "outstanding" ? (
              <div className="flex items-center gap-8">
                <Field
                  placeholder="سبب الشطب"
                  value={reasons[row.id] ?? ""}
                  onChange={(event) =>
                    setReasons((current) => ({
                      ...current,
                      [row.id]: event.target.value,
                    }))
                  }
                />
                <Button
                  size="sm"
                  variant="secondary"
                  loading={busy === row.id}
                  onClick={() => void drop(row)}
                >
                  شطب
                </Button>
              </div>
            ) : (
              <span className="text-12 text-muted">—</span>
            )}
          </>
        )}
      />
    </section>
  );
}
