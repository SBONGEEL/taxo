/** **حسابُ مراجع تحويلات BaridiMob** (SPEC §٨٢-ب/٥) — **ينشئه المالكُ بيده** من «المستخدمون والصلاحيات».
 *
 * الاسمُ واسمُ الدخول وكلمةٌ مؤقّتة يضعها المالكُ ويعطيها لصاحبها بنفسه. **وعند أوّل دخول**: يُسجِّل العاملَ الثاني أوّلاً (إلزاميٌّ كالمالك)
 * ثمّ يغيّر الكلمة — ولا تُفتح له قبلهما صفحة. **ولا يرى بعدها إلا صفحةَ المراجعة**: الجزائر وحدَها، اعتمادٌ أو رفضٌ لا غير.
 *
 * **والإيقافُ من شاشة الحساب نفسِه** («حظر») — كأيِّ حسابٍ غيرِ إداريّ.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { createTransferReviewer, listTransferReviewers } from "@/api/endpoints";
import type { TransferReviewer } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { moment } from "@/lib/format";
import { cn } from "@/lib/utils";

export function ReviewersCard({ onDone }: { onDone: (message: string) => void }) {
  const [rows, setRows] = useState<TransferReviewer[] | null>(null);
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => setRows(await listTransferReviewers()), []);

  useEffect(() => {
    load().catch((caught) => setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة المراجعين"));
  }, [load]);

  async function create() {
    setBusy(true);
    setError(null);
    try {
      await createTransferReviewer({ name: name.trim(), username: username.trim(), password });
      setName("");
      setUsername("");
      setPassword("");
      onDone("أُنشئ حسابُ المراجع — أعطِه اسمَ الدخول والكلمةَ المؤقّتة بنفسك");
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الإنشاء");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-18 rounded-18 border border-line bg-surface px-16 py-14">
      <h2 className="text-14 font-bold text-ink">مراجعو تحويلات BaridiMob — الجزائر</h2>
      <p className="mt-4 text-12 leading-note text-muted">
        يرى صفحةَ «تحويلات BaridiMob» وحدَها: الاسمَ الأوّلَ وهاتفاً مقنَّعاً، ويعتمد أو يرفض لا غير. العاملُ الثاني إلزاميٌّ عند أوّل
        دخول، ثمّ يغيّر الكلمةَ المؤقّتة.
      </p>
      {rows && rows.length > 0 ? (
        <ul className="mt-10 grid gap-6">
          {rows.map((row) => (
            <li key={row.id} className="flex flex-wrap items-baseline justify-between gap-8 rounded-14 border border-line bg-surface-2 px-14 py-10">
              <span className="font-semibold text-ink">
                {row.name}
                <span dir="ltr" className="ms-8 text-11.5 font-normal text-muted">
                  {row.username ?? ""}
                </span>
              </span>
              <span className={cn("text-11.5", row.is_blocked ? "text-danger" : row.has_factor ? "text-ok" : "text-warn-ink")}>
                {row.is_blocked
                  ? "محظور"
                  : !row.has_factor
                    ? "لم يسجّل العاملَ الثاني بعد"
                    : row.must_change_password
                      ? "لم يغيّر الكلمةَ المؤقّتة بعد"
                      : "جاهز"}{" "}
                · {moment(row.created_at)}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="mt-12 grid gap-10 md:grid-cols-3">
        <Field label="اسمُه" name="reviewer_name" value={name} onChange={(event) => setName(event.target.value)} />
        <Field
          label="اسمُ الدخول"
          name="reviewer_username"
          dir="ltr"
          autoComplete="off"
          value={username}
          onChange={(event) => setUsername(event.target.value.toLowerCase())}
        />
        <Field
          label="كلمةٌ مؤقّتة"
          name="reviewer_password"
          type="password"
          dir="ltr"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>
      <ErrorNote message={error} />
      <div className="mt-12 flex justify-end">
        <Button
          size="md"
          loading={busy}
          disabled={name.trim().length < 2 || username.trim().length < 3 || password.length < 8}
          onClick={() => void create()}
        >
          أنشئ حسابَ المراجع
        </Button>
      </div>
    </section>
  );
}
