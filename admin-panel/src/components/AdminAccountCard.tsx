/** حسابُ المشرف نفسِه — اسمُ المستخدم وكلمةُ المرور (قرارُ المالك 2026-08-20).
 *
 * **وهو بابُ صاحبِ الحساب لا بابُ إدارةٍ لغيره**: كلُّ نداءٍ هنا يعمل على الجلسة
 * الحالية ولا يقبل مُعرِّفَ أحدٍ آخر. ومشرفٌ يعدّل مشرفاً آخرَ غيرُ مبنيٍّ عمداً
 * (SPEC §25.9).
 *
 * **وموضعُه شاشةُ الأمان**: هي التي فيها العاملُ الثاني، و«ما يخصّ دخولي» سؤالٌ
 * واحدٌ لا يُفرَّق على شاشتين.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  changeAdminPassword,
  changeAdminUsername,
  getAdminAccount,
} from "@/api/endpoints";
import type { AdminAccount } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Spinner, SuccessNote } from "@/components/ui/Feedback";

export function AdminAccountCard({
  onError,
}: {
  onError: (message: string) => void;
}) {
  const [row, setRow] = useState<AdminAccount | null>(null);
  const [username, setUsername] = useState("");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState<"name" | "pass" | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    const value = await getAdminAccount();
    setRow(value);
    setUsername(value.username ?? "");
  }, []);

  useEffect(() => {
    void load().catch((caught: Error) => onError(caught.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  function fail(caught: unknown, fallback: string) {
    onError(caught instanceof ApiError ? caught.message : fallback);
  }

  if (row === null) return <Spinner className="mx-auto" />;

  // حسابٌ بلا اسمِ مستخدم = راكبٌ أو كبتنٌ برقم — والبطاقةُ لا تخصّه
  if (row.username === null) return null;

  return (
    <section className="rounded-16 border border-line bg-surface p-16">
      <h2 className="mb-4 text-15 font-bold text-ink">حسابُ الدخول</h2>
      <p className="mb-12 text-11.5 leading-note text-muted">
        اللوحةُ تُدخَل باسمِ مستخدمٍ وكلمةِ مرور — لا برقمِ هاتف.
        {row.has_phone ? null : (
          <>
            {" "}
            <b className="text-warn">
              ولا استعادةَ ذاتيةً لكلمة المرور
            </b>
            : تُعاد من الخادم وحدَه، فاحفظها.
          </>
        )}
        {row.is_break_glass ? (
          <>
            {" "}
            <b className="text-ink">وهذا حسابُ طوارئ</b> — كلُّ دخولٍ به يُكتب في
            سجلّ التدقيق.
          </>
        ) : null}
      </p>

      {done ? <SuccessNote message={done} /> : null}

      <div className="grid gap-16 md:grid-cols-2">
        <div className="grid gap-10">
          <Field
            label="اسم المستخدم"
            dir="ltr"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
          <Button
            size="sm"
            variant="secondary"
            loading={busy === "name"}
            disabled={
              username.trim().length < 3 || username.trim() === row.username
            }
            onClick={() => {
              setBusy("name");
              setDone(null);
              changeAdminUsername(username.trim())
                .then((value) => {
                  setRow(value);
                  setDone("غُيّر اسمُ المستخدم — ويُقرأ في سجلّ التدقيق");
                })
                .catch((caught) => fail(caught, "تعذّر التغيير"))
                .finally(() => setBusy(null));
            }}
          >
            غيّر الاسم
          </Button>
        </div>

        <div className="grid gap-10">
          <Field
            label="كلمة المرور الحالية"
            type="password"
            dir="ltr"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
          />
          <Field
            label="الجديدة (8 أحرف على الأقل)"
            type="password"
            dir="ltr"
            value={next}
            onChange={(event) => setNext(event.target.value)}
          />
          <Button
            size="sm"
            loading={busy === "pass"}
            disabled={current.length < 1 || next.length < 8}
            onClick={() => {
              setBusy("pass");
              setDone(null);
              changeAdminPassword({
                current_password: current,
                new_password: next,
              })
                .then(() => {
                  setCurrent("");
                  setNext("");
                  setDone("غُيّرت كلمةُ المرور — وأُبطلت بقيةُ الجلسات");
                })
                .catch((caught) => fail(caught, "تعذّر التغيير"))
                .finally(() => setBusy(null));
            }}
          >
            غيّر كلمة المرور
          </Button>
          <p className="text-11 leading-note text-muted">
            تُبطَل <b className="text-ink">بقيةُ</b> الجلسات لا هذه: من بدّل
            كلمتَه يريد إخراجَ غيره لا نفسِه.
          </p>
        </div>
      </div>
    </section>
  );
}
