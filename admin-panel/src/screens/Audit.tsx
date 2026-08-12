/** سجل التدقيق — SPEC القسم 14.
 *
 * **شاشةُ قراءةٍ لسجلٍّ لا يُكتب من مسار ولا يُعدَّل ولا يُحذف.** كلُّ قيدٍ
 * فيه كتبته **معاملةُ التغيير نفسها** (`services/audit.py`): لا تغييرَ بلا
 * قيد، ولا قيدَ لتغييرٍ فشل — فالجدولان يتفقان أو يسقطان معاً.
 *
 * **و`details` أسماءُ الحقول المتغيّرة لا قيمُها**، وهي قاعدةٌ أمنية لا
 * اختصار: سجلُّ تدقيقٍ يخزّن قيم الحقول يصير نسخةً ثانيةً من الأسرار التي
 * حُفظت مشفَّرةً في مكانها. ولذلك تعرض الشاشة `details` كما هو ولا تدّعي
 * صياغةً له: حقلٌ جديدٌ في الخلفية يظهر هنا بلا تعديل، وصياغةٌ تعرف حقولاً
 * بعينها تصمت عمّا لا تعرفه.
 *
 * **والقراءةُ الوحيدة المسجَّلة في المشروع هي فتحُ الخريطة الحيّة**
 * (`read` على `live_map`، القسم 13/1) — ولذلك تُميَّز في القائمة: صلاحيةٌ
 * بهذا الاتساع تُسأل عنها، وقيدُها مخنوقٌ بنافذةٍ فجلسةُ مراقبةٍ قيدٌ واحد.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { listAuditLogs } from "@/api/endpoints";
import type { AuditAction, AuditLog } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Pills, Table } from "@/components/Table";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Field } from "@/components/ui/Field";
import { ErrorNote } from "@/components/ui/Feedback";
import { moment } from "@/lib/format";

const ACTION_LABEL: Record<AuditAction, string> = {
  create: "إنشاء",
  update: "تعديل",
  delete: "حذف",
  activate: "تفعيل",
  deactivate: "تعطيل",
  read: "قراءة",
};

const ACTION_TONE: Record<AuditAction, Tone> = {
  create: "ok",
  update: "ink",
  delete: "danger",
  activate: "ok",
  deactivate: "warn",
  // القراءةُ المسجَّلة حسّاسةٌ بطبعها — لا تُسجَّل إلا حيث تكون كذلك
  read: "danger",
};

/** أنواعُ العناصر كما تكتبها الخدمات — ما ليس هنا يُعرض كما هو.
 *
 * **القائمة منسوخةٌ من `entity_type=` في الخلفية حرفاً بحرف**، وقد كُتبت أولَ
 * مرة من الذاكرة فخرج منها `wallet_topup_request` باسمٍ مختصر و`push_test`
 * بلا اسمٍ أصلاً — فظهرا في الشاشة بمفاتيحهما الإنجليزية. والسقوطُ إلى المفتاح
 * الخام مقصودٌ ويبقى: نوعٌ جديد في الخلفية يُقرأ باسمه البرمجي ولا يختفي.
 */
const ENTITY_LABEL: Record<string, string> = {
  user: "حساب",
  driver: "سائق",
  driver_document: "وثيقة سائق",
  payment: "دفعة",
  wallet: "محفظة",
  wallet_transaction: "قيد محفظة",
  wallet_topup_request: "طلب شحن",
  withdrawal_request: "طلب سحب",
  driver_subscription: "اشتراك",
  subscription_plan: "باقة",
  pricing_rule: "تسعيرة",
  commission_setting: "إعداد عمولة",
  wallet_setting: "حدود محفظة",
  payment_setting: "إعداد دفع",
  feature_flag: "مفتاح ميزة",
  provider_credential: "عقد مزوّد",
  notification_campaign: "حملة",
  push_test: "مِجَسّ إشعار",
  live_map: "الخريطة الحيّة",
};

const COLUMNS = "1fr 1fr 0.8fr 1.1fr 0.8fr 1.6fr";

export function AuditScreen() {
  const [action, setAction] = useState<AuditAction | "all">("all");
  const [entity, setEntity] = useState("");
  const [applied, setApplied] = useState("");
  const [rows, setRows] = useState<AuditLog[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(null);
    setRows(
      await listAuditLogs({
        action: action === "all" ? undefined : action,
        entity_type: applied || undefined,
        limit: 200,
      }),
    );
  }, [action, applied]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة السجل",
      ),
    );
  }, [load]);

  return (
    <Shell
      title="سجل التدقيق"
      subtitle="كلُّ إجراءٍ إداريٍّ مسجَّلٌ في معاملة التغيير نفسها — والقيمُ لا تُخزَّن، أسماءُ الحقول فقط"
    >
      <Pills
        value={action}
        onPick={(key) => setAction(key)}
        options={[
          { key: "all", label: "الكل" },
          { key: "create", label: "إنشاء" },
          { key: "update", label: "تعديل" },
          { key: "delete", label: "حذف" },
          { key: "read", label: "قراءةٌ حسّاسة" },
        ]}
      />

      <form
        className="mb-14 flex max-w-modal items-end gap-9"
        onSubmit={(event) => {
          event.preventDefault();
          setApplied(entity.trim());
        }}
      >
        <div className="flex-1">
          <Field
            label="نوع العنصر"
            placeholder="driver · payment · provider_credential …"
            dir="ltr"
            value={entity}
            onChange={(event) => setEntity(event.target.value)}
          />
        </div>
        <button
          type="submit"
          className="rounded-13 border border-line px-16 py-13 text-13 font-semibold text-ink"
        >
          فلترة
        </button>
      </form>

      <ErrorNote message={error} />

      <div className="mt-12">
        <Table
          columns={COLUMNS}
          headers={[
            "الوقت",
            "من فعل",
            "الإجراء",
            "العنصر",
            "المُعرّف",
            "التفاصيل",
          ]}
          rows={rows}
          keyOf={(row) => row.id}
          empty={{
            title: "لا قيود في هذه الفلترة",
            hint: "امسح الفلترة أو بدّل نوع الإجراء.",
          }}
          render={(row) => (
            <>
              <span className="text-muted">{moment(row.created_at)}</span>

              {/* الاسمُ يذهب بحذف الحساب ويبقى القيد — لا العكس */}
              <span className="min-w-0 truncate text-ink">
                {row.actor_name ?? (
                  <span className="text-muted">
                    {row.actor_id ? "حسابٌ محذوف" : "النظام"}
                  </span>
                )}
              </span>

              <span>
                <Badge tone={ACTION_TONE[row.action]}>
                  {ACTION_LABEL[row.action]}
                </Badge>
              </span>

              <span className="text-ink">
                {ENTITY_LABEL[row.entity_type] ?? row.entity_type}
              </span>

              {/* المُعرّف يُقارَن حرفاً بحرف — بلا تعريب خانات */}
              <span dir="ltr" className="truncate text-start text-muted">
                {row.entity_id ? row.entity_id.slice(0, 8) : "—"}
              </span>

              <span className="min-w-0 truncate text-muted" dir="ltr">
                {row.details ? JSON.stringify(row.details) : "—"}
              </span>
            </>
          )}
        />
      </div>

      <p className="mt-14 max-w-prose text-11.5 leading-note text-muted">
        القيدُ يحمل من فعل ومتى وعلى أيّ عنصر، ويبقى بعد حذف حساب فاعله — يذهب
        الاسمُ ويبقى الأثر، لا العكس. و«النظام» قيدٌ لا فاعلَ بشريَّ له: كإسقاط
        اعتمادِ سائقٍ استبدل وثيقةً بنفسه.
      </p>
    </Shell>
  );
}
