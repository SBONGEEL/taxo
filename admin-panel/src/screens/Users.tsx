/** المستخدمون والصلاحيات — SPEC القسم 13/8.
 *
 * **وصارت المصفوفةُ جدولاً يُقرأ ويُكتب** (البند ٥، §39٫٥، قرارُ المالك
 * 2026-09-02) — **وكان هذا الملفُّ يقول عكسَه**: «ثابتةٌ في الكود لا في جدول».
 *
 * **وعلّةُ المنعِ القديمة كانت صحيحةً وزالت**: «خليةٌ تُنقر تعني جدولَ صلاحيات
 * يصير مصدرَ الحقيقة بدل الكود» — **والجدولُ اليومَ هو الحارسُ نفسُه**:
 * `require_permission` يقرأ الصفوفَ في كلِّ طلب، **فلا حالتان تختلفان**.
 * ومن أطفأ خليةً هنا أطفأ باباً حقيقياً.
 *
 * **والاثنتا عشرةَ مشتقّةٌ من الموجّهات لا مخترعة**، **والغيابُ يُقرأ «افتراضُ
 * الدور»** لا «لا يملك شيئاً» — ولذلك يُعرض `explicit` صراحةً.
 *
 * **ولا زرَّ «دعوة مستخدم»**: الحساب يُنشأ بإثبات ملكية رقمٍ من التطبيق (القسم
 * 15/أ)، ولا مسارَ في المشروع يفتح حساباً بلا ذلك الإثبات. ورفعُ حسابٍ قائم
 * إلى `support` تغييرُ دورٍ لا يصفه هذا المستند — فالشاشة تقول أين يقع ذلك
 * اليوم (في القاعدة، بيد من يملكها) بدل أن تخترع له باباً.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  listAdminPermissions,
  listUsers,
  setAdminPermissions,
} from "@/api/endpoints";
import type { AdminPermissions, User, UserRole } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Table } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { moment } from "@/lib/format";
import { cn } from "@/lib/utils";

const ROLE_LABEL: Record<UserRole, string> = {
  admin: "مالك · صلاحيات كاملة",
  support: "دعم فني",
  rider: "راكب",
  driver: "سائق",
};

/** ما تفرضه الخلفية فعلاً — كلُّ سطرٍ يقابل حارساً في `core/deps.py`. */
/** أسماءُ الصلاحيات الاثنتي عشرة كما يعرضها العربيُّ — **والمفاتيحُ من
 *  الخلفية**: قائمةٌ تُكتب هنا بيدٍ تفترق عن التعداد أوّلَ عضوٍ يُضاف. */
const PERMISSION_LABEL: Record<string, string> = {
  "settings.write": "الإعدادات — التسعيرة والخطط والمفاتيح",
  "users.manage": "الحسابات والكباتن — الاعتماد والإيقاف والوثائق",
  "finance.manage": "المالية — الشحن والصرف والتسويات والاشتراكات",
  "growth.manage": "النمو — الحملات والعروض والكوبونات والإحالات",
  "fleet.manage": "الأسطول — المهامّ والشارات ومركبات المتجر",
  "providers.manage": "العقود وقوالب الرسائل",
  "backups.manage": "النسخ الاحتياطية",
  "payments.resolve": "فصل النزاعات",
  "read.only": "قراءة القوائم والتقارير",
  "security.manage": "الأمان — سياسة الدخول والعامل الثاني",
  "permissions.manage": "منح الصلاحيات ونزعها",
  "errors.read": "شاشة الأعطال — قراءتها وحسمُها",
};

const COLUMNS = "1.6fr 1.2fr 1.2fr 1fr";

export function UsersScreen() {
  const [rows, setRows] = useState<User[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(null);
    // الدوران في نداءين: القائمةُ تُفلتر بدورٍ واحد، والموظفون دوران
    const [admins, support] = await Promise.all([
      listUsers({ role: "admin", limit: 100 }),
      listUsers({ role: "support", limit: 100 }),
    ]);
    setRows([...admins, ...support]);
  }, []);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الحسابات",
      ),
    );
  }, [load]);

  return (
    <Shell
      title="المستخدمون والصلاحيات"
      subtitle="دوران تفرضهما الخلفية على كل مسار — وما تخفيه الشاشة راحةٌ لا حماية"
    >
      <ErrorNote message={error} />
      <SuccessNote message={done} />

      <Table
        columns={COLUMNS}
        headers={["المستخدم", "الهاتف", "الدور", "منذ"]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{
          title: "لا حسابات إدارية",
          hint: "أوّلُ حسابٍ إداريٍّ يُنشأ من سكربت التهيئة لا من هذه الشاشة.",
        }}
        render={(row) => (
          <>
            <span className="flex items-center gap-9">
              <span className="flex size-30 flex-none items-center justify-center rounded-full border border-line bg-surface-2 text-11 font-bold text-ink">
                {row.name.trim().slice(0, 1)}
              </span>
              <span className="min-w-0 truncate font-semibold text-ink">
                {row.name}
              </span>
            </span>

            <span dir="ltr" className="text-start text-muted">
              {row.phone}
            </span>

            <span>
              <Badge tone={row.role === "admin" ? "ink" : "muted"}>
                {ROLE_LABEL[row.role]}
              </Badge>
            </span>

            <span className="text-muted">{moment(row.created_at)}</span>
          </>
        )}
      />

      <PermissionsMatrix onError={setError} onDone={setDone} />
    </Shell>
  );
}



/** مصفوفةُ الصلاحيات — **تُقرأ من الحارس نفسِه وتُكتب فيه** (§39٫٥).
 *
 * **ولا تُخفى الخلايا عمّن لا يملك المنح**: `permissions.manage` يحرسه الخادم،
 * **وإخفاءُ الواجهة راحةٌ لا حماية** (§21) — فالجدولُ يُقرأ، والكتابةُ تُردّ
 * بنصِّها إن لم تُملك.
 *
 * **و«افتراضُ الدور» يُقال صراحةً**: مشرفٌ بلا صفوفٍ ليس بلا صلاحيات — **وهو
 * ما يجعل الجدولَ الفارغَ اليومَ مقروءاً على حقيقته**.
 */
function PermissionsMatrix({
  onError,
  onDone,
}: {
  onError: (message: string) => void;
  onDone: (message: string) => void;
}) {
  const [rows, setRows] = useState<AdminPermissions[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await listAdminPermissions());
    } catch (caught) {
      onError(caught instanceof ApiError ? caught.message : "تعذّر قراءة المصفوفة");
    }
  }, [onError]);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggle(row: AdminPermissions, permission: string) {
    const next = row.permissions.includes(permission)
      ? row.permissions.filter((p) => p !== permission)
      : [...row.permissions, permission];
    setBusy(row.user_id);
    try {
      await setAdminPermissions(row.user_id, next);
      onDone(`حُدِّثت صلاحياتُ ${row.name}`);
      await load();
    } catch (caught) {
      onError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    } finally {
      setBusy(null);
    }
  }

  const keys = Object.keys(PERMISSION_LABEL);

  return (
    <section className="mt-22">
      <h2 className="mb-4 text-16 font-bold text-ink">مصفوفة الصلاحيات</h2>
      <p className="mb-12 max-w-prose text-11.5 leading-note text-muted">
        خليةٌ تُنقر هنا تفتح باباً أو تغلقه فعلاً — <b className="text-ink">هذا
        الجدولُ هو الحارسُ نفسُه</b>، يقرؤه الخادمُ في كلِّ طلب. ومشرفٌ بلا
        صفوفٍ ليس بلا صلاحيات: يُقرأ بافتراض دوره، ويقول العمودُ ذلك.
      </p>

      {rows === null ? (
        <Spinner className="mx-auto my-24" />
      ) : (
        <div className="overflow-x-auto rounded-16 border border-line bg-surface">
          <table className="w-full min-w-[52rem] text-12.5">
            <thead>
              <tr className="bg-surface-2 text-11 text-muted">
                <th className="p-12 text-start font-semibold">الصلاحية</th>
                {rows.map((row) => (
                  <th key={row.user_id} className="p-12 text-center font-semibold">
                    <span className="block text-ink">{row.name}</span>
                    <span className="block text-10.5">
                      {row.explicit ? "صفوفٌ ممنوحة" : "افتراضُ الدور"}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key} className="border-t border-line">
                  <td className="p-12 text-ink">{PERMISSION_LABEL[key]}</td>
                  {rows.map((row) => (
                    <td key={row.user_id} className="p-12">
                      <span className="flex justify-center">
                        <button
                          type="button"
                          disabled={busy === row.user_id}
                          aria-label={
                            row.permissions.includes(key) ? "مسموح" : "ممنوع"
                          }
                          onClick={() => void toggle(row, key)}
                          className={cn(
                            "flex size-28 items-center justify-center rounded-8 text-12 font-bold disabled:opacity-60",
                            row.permissions.includes(key)
                              ? "bg-accent text-accent-ink"
                              : "border border-line text-muted",
                          )}
                        >
                          {row.permissions.includes(key) ? "✓" : "—"}
                        </button>
                      </span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
