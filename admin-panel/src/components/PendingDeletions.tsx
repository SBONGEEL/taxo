/** **حساباتٌ في مهلة الحذف** — وموعدُ تجهيلها وسببُ تأجيلها (SPEC §59).
 *
 * **قراءةٌ لا قرار**: الحذفُ يقع بموعده من المهمّة الدورية، **والمشرفُ لا يعجّله
 * ولا يلغيه** — الاستعادةُ لصاحب الحساب بالدخول وحدَه (قرارُ المالك).
 *
 * **والمؤجَّلُ أوّلاً**: حسابٌ حلّ موعدُه ولم يُجهَّل لأن عليه مالاً أو مانعاً —
 * **وهو ما ينتظر مشرفاً**: رصيدٌ لم يُسحب، أو نزاعٌ لم يُحسم. **ويُنبَّه
 * المشرفُ في صندوقه مرّةً عند تغيّر السبب**، وهذه الشاشةُ ما يفتحه التنبيه.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { listPendingDeletions } from "@/api/endpoints";
import type { PendingDeletionRow } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Table } from "@/components/Table";
import { moment } from "@/lib/format";

/** **سببُ التأجيل بجملة المشرف** — والرمزُ من الخلفية (`account_deletion.py`). */
const DEFER_TEXT: Record<string, string> = {
  active_ride: "رحلةٌ جارية",
  open_dispute: "نزاعٌ مفتوح على دفعة",
  unpaid_charge: "رسمُ إلغاءٍ مستحقٌّ عليه",
  unpaid_advance: "سلفةٌ غيرُ مسدَّدة",
  pending_money: "شحنٌ أو سحبٌ أو دفعُ بطاقةٍ لم يُحسم",
  rider_balance_changed: "رصيدُ الراكب تغيّر بعد موافقته على ضياعه",
  driver_balance: "في محفظة الكبتن رصيدٌ لم يُسحب",
};

export function PendingDeletions({ onError }: { onError: (message: string) => void }) {
  const [rows, setRows] = useState<PendingDeletionRow[]>([]);

  const load = useCallback(() => {
    listPendingDeletions()
      .then(setRows)
      .catch((caught) =>
        onError(caught instanceof ApiError ? caught.message : "تعذّر التحميل"),
      );
  }, [onError]);

  useEffect(load, [load]);

  return (
    <section className="card mt-16 p-16">
      <h2 className="mb-4 text-15 font-bold text-ink">حسابات في مهلة الحذف</h2>
      <p className="mb-12 text-12 text-muted">
        يُحذف الحساب بموعده بلا تدخّل. والمؤجَّل حلّ موعده ولم يُحذف لأن عليه مالاً أو
        مانعاً — ويُحذف في الدورة التي تلي زوال سببه.
      </p>

      <Table
        height="compact"
        columns="1.4fr 0.9fr 0.9fr 1.8fr"
        headers={["الحساب", "طُلب", "موعد الحذف", "الحال"]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{ title: "لا حسابات في المهلة", hint: "لم يطلب أحدٌ حذف حسابه." }}
        render={(row) => (
          <>
            <span className="text-12.5 text-ink">
              {row.name}
              <span className="ms-6 font-mono text-11 text-muted" dir="ltr">
                {row.phone ?? "—"}
              </span>
            </span>
            <span className="text-12 text-muted">{moment(row.deletion_requested_at)}</span>
            <span className="text-12 text-muted">{moment(row.deletion_due_at)}</span>
            {row.deletion_deferred_reason ? (
              <span className="flex items-center gap-8">
                <Badge tone="warn">مؤجَّل</Badge>
                <span className="text-12 text-muted">
                  {DEFER_TEXT[row.deletion_deferred_reason] ?? row.deletion_deferred_reason}
                </span>
              </span>
            ) : (
              <span className="flex items-center gap-6">
                <Badge tone="muted">في المهلة</Badge>
              </span>
            )}
          </>
        )}
      />
    </section>
  );
}
