/** مستحقّاتُ الكباتن (الترحيلة `0061`) — ما عليهم، وتأكيدُ سدادٍ وصل، وشطبٌ بسبب.
 *
 * **وموضعُها تحت السلف**: دَينٌ ثالثٌ يُقرأ حيث يُقرأ أخواه، لا في شاشةِ مالٍ
 * منفصلةٍ يُبحث عنها.
 *
 * **ولا زرَّ «أضِف دَيناً»**: النشأةُ من تسوية الرحلة وحدَها — ومن كتب دَيناً
 * بيده كتب رقماً لا رحلةَ خلفه، وهو ما لا تفعله أيُّ شاشةٍ في هذه اللوحة.
 *
 * **وتأكيدُ السداد يكتب ما وصل فعلاً لا ما فُتحت به المطالبة**: المشرفُ يقرأ
 * كشفَ حسابه ويكتب الرقمَ الذي رآه. **والناقصُ يُقبل ويُنقص** — بخلاف
 * الاشتراك الذي لا يُفعَّل بأقلَّ من ثمنه، لأن الدَّينَ عددٌ ينقص والاشتراكَ
 * شيءٌ لا يتجزّأ.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  confirmDebtClaim,
  listDebtClaims,
  listDriverDebts,
  writeOffDebt,
} from "@/api/endpoints";
import type { DebtClaimRow, DriverDebtRow } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Table } from "@/components/Table";
import { day, money } from "@/lib/format";

const TONE: Record<
  DriverDebtRow["status"],
  Parameters<typeof Badge>[0]["tone"]
> = {
  outstanding: "warn",
  settled: "ok",
  written_off: "muted",
};

const LABEL: Record<DriverDebtRow["status"], string> = {
  outstanding: "قائم",
  settled: "سُدِّد",
  written_off: "شُطب",
};

const SOURCE: Record<DriverDebtRow["source"], string> = {
  ride_commission: "عمولة رحلة نقدية",
};

export function DriverDebts({ onError }: { onError: (message: string) => void }) {
  const [rows, setRows] = useState<DriverDebtRow[]>([]);
  const [claims, setClaims] = useState<DebtClaimRow[]>([]);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [credited, setCredited] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([listDriverDebts(), listDebtClaims()])
      .then(([debts, pending]) => {
        setRows(debts);
        setClaims(pending);
      })
      .catch((caught) =>
        onError(caught instanceof ApiError ? caught.message : "تعذّر التحميل"),
      );
  }, [onError]);

  useEffect(load, [load]);

  async function confirm(claim: DebtClaimRow) {
    // **المبلغُ الافتراضيُّ ما فُتحت به** — والمشرفُ يعدّله إن وصل غيرُه
    const value = (credited[claim.id] ?? claim.amount).trim();
    setBusy(claim.id);
    try {
      await confirmDebtClaim(claim.id, value);
      load();
    } catch (caught) {
      onError(caught instanceof ApiError ? caught.message : "تعذّر التأكيد");
    } finally {
      setBusy(null);
    }
  }

  async function drop(row: DriverDebtRow) {
    const reason = reasons[row.id]?.trim();
    if (!reason) {
      onError("سبب الشطب مطلوب — خسارةٌ بلا سببٍ مكتوبٍ لا يملكها أحد");
      return;
    }
    setBusy(row.id);
    try {
      await writeOffDebt(row.id, reason);
      load();
    } catch (caught) {
      onError(caught instanceof ApiError ? caught.message : "تعذّر الشطب");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="card mt-16 p-16">
      <h2 className="mb-4 text-15 font-bold text-ink">مستحقّات الكباتن</h2>
      <p className="mb-12 text-12 text-muted">
        عمولةُ رحلةٍ قبض الكبتنُ أجرتها بيده تبقى مستحقّةً عليه، وتُحصَّل
        تلقائياً من أول أجرةٍ تدخل محفظته. وفوق سقف السوق يخرج من التوزيع حتى
        يبلغ المستحقُّ صفراً. والشطبُ اعترافٌ بالخسارة ويرفع الإيقاف.
      </p>

      <h3 className="mb-6 mt-16 text-13 font-bold text-ink">
        مطالبات سداد بانتظار التأكيد
      </h3>
      <Table
        columns="1fr 0.9fr 1fr 1.4fr"
        headers={["المرجع", "المبلغ", "فُتحت", ""]}
        rows={claims}
        keyOf={(claim) => claim.id}
        empty={{ title: "لا مطالبات", hint: "لا سداد ينتظر تأكيداً." }}
        render={(claim) => (
          <>
            <span className="font-mono text-11.5">{claim.cart_id}</span>
            <span className="text-12 text-ink">
              {money(claim.amount, claim.currency)}
            </span>
            <span className="text-12 text-muted">{day(claim.created_at)}</span>
            <div className="flex items-center gap-8">
              <Field
                placeholder="المبلغ الواصل"
                value={credited[claim.id] ?? claim.amount}
                onChange={(event) =>
                  setCredited((current) => ({
                    ...current,
                    [claim.id]: event.target.value,
                  }))
                }
              />
              <Button
                size="sm"
                loading={busy === claim.id}
                onClick={() => void confirm(claim)}
              >
                أكّد الوصول
              </Button>
            </div>
          </>
        )}
      />

      <h3 className="mb-6 mt-20 text-13 font-bold text-ink">المستحقّات</h3>
      <Table
        columns="1.2fr 0.9fr 0.9fr 1fr 0.8fr 1.6fr"
        headers={["الكبتن", "المبلغ", "المحصَّل", "المصدر", "الحالة", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{ title: "لا مستحقّات", hint: "لم ينشأ مستحقٌّ بعد." }}
        render={(row) => (
          <>
            <span className="text-12 text-ink">{row.driver_name}</span>
            <span className="text-12 text-ink">
              {money(row.amount, row.currency)}
            </span>
            <span className="text-12 text-muted">
              {money(row.collected, row.currency)}
            </span>
            <span className="text-11.5 text-muted">{SOURCE[row.source]}</span>
            {/* **الشارةُ في `span` لا عاريةً في الشبكة** — خليةُ `grid` تمطّ
                ابنَها على عرض العمود */}
            <span className="flex items-center gap-6">
              <Badge tone={TONE[row.status]}>{LABEL[row.status]}</Badge>
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
