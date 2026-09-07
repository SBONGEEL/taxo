/** طلباتُ إلغاء تفعيل الحسابات (البند ١٣).
 *
 * **قرارٌ لا زرُّ تنفيذ**: الموافقةُ تُخرج الكبتنَ من التوزيع **وتُسقط شرطَ
 * الرصيد المحتجَز** فيصير سحبُه كلَّه ممكناً — فهي إذنٌ بمالٍ لا تنظيفُ سجل.
 *
 * **والرفضُ بسببٍ مكتوب** كرفض المستند: الكبتنُ يقرأه في شاشته، و«رُفض» بلا
 * سببٍ تذكرةُ دعمٍ مضمونة.
 *
 * **ولا تُعرض هنا شروطُ المنع**: تُقرأ في الخلفية لحظةَ القرار — فلو بدأ
 * الكبتنُ رحلةً بين الطلب والموافقة يرتدّ القرارُ برسالته. وعرضُها هنا نسخةٌ
 * ثانيةٌ تتقادم بين فتح الشاشة والضغط.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { decideDeactivation, listDeactivations } from "@/api/endpoints";
import type { DeactivationRequestRow } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Table } from "@/components/Table";
import { moment } from "@/lib/format";

const TONE: Record<DeactivationRequestRow["status"], Parameters<typeof Badge>[0]["tone"]> = {
  pending: "warn",
  approved: "ok",
  rejected: "danger",
  cancelled: "muted",
};

const LABEL: Record<DeactivationRequestRow["status"], string> = {
  pending: "قيد المراجعة",
  approved: "أُلغي التفعيل",
  rejected: "مرفوض",
  cancelled: "تراجع عنه",
};

export function Deactivations({ onError }: { onError: (message: string) => void }) {
  const [rows, setRows] = useState<DeactivationRequestRow[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    listDeactivations()
      .then(setRows)
      .catch((caught) =>
        onError(caught instanceof ApiError ? caught.message : "تعذّر التحميل"),
      );
  }, [onError]);

  useEffect(load, [load]);

  async function decide(row: DeactivationRequestRow, approved: boolean) {
    setBusy(row.id);
    try {
      await decideDeactivation(row.id, {
        approved,
        note: notes[row.id]?.trim() || undefined,
      });
      load();
    } catch (caught) {
      onError(caught instanceof ApiError ? caught.message : "تعذّر حفظ القرار");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="card mt-16 p-16">
      <h2 className="mb-4 text-15 font-bold text-ink">طلبات إلغاء التفعيل</h2>
      <p className="mb-12 text-12 text-muted">
        الموافقة تُخرج الكبتن من التوزيع وتُطلق رصيده المحتجَز. والرفض يحتاج سبباً
        يقرؤه صاحبُ الطلب.
      </p>

      <Table
        height="compact"
        columns="1fr 1.4fr 0.8fr 0.9fr 1.6fr"
        headers={["الحساب", "السبب", "الحالة", "التاريخ", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{ title: "لا طلبات", hint: "لم يطلب أحدٌ إغلاق حسابه بعد." }}
        render={(row) => (
          <>
            <span className="font-mono text-11.5">{row.user_id.slice(0, 8)}</span>
            <span className="text-12 text-muted">{row.reason ?? "—"}</span>
            <span className="flex items-center gap-6">
              <Badge tone={TONE[row.status]}>{LABEL[row.status]}</Badge>
            </span>
            <span className="text-12 text-muted">{moment(row.created_at)}</span>
            {row.status === "pending" ? (
              <div className="flex items-center gap-8">
                <Field
                  placeholder="سبب الرفض"
                  value={notes[row.id] ?? ""}
                  onChange={(event) =>
                    setNotes((current) => ({
                      ...current,
                      [row.id]: event.target.value,
                    }))
                  }
                />
                <Button
                  size="sm"
                  loading={busy === row.id}
                  onClick={() => void decide(row, true)}
                >
                  موافقة
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  loading={busy === row.id}
                  onClick={() => void decide(row, false)}
                >
                  رفض
                </Button>
              </div>
            ) : (
              <span className="text-12 text-muted">{row.review_note ?? "—"}</span>
            )}
          </>
        )}
      />

    </section>
  );
}
