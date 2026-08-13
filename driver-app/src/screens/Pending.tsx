/** «طلبك قيد المراجعة» — SPEC القسم 12/1.
 *
 * ليست شاشةَ انتظارٍ صامتة: تعرض **حالة كل مستند وسببَ رفضه**، لأن كبتناً لا
 * يعرف لماذا رُفضت رخصته يعيد رفع الصورة نفسها ويبقى منتظراً إلى الأبد
 * (المرحلة 9-ب جعلت السبب جزءاً من الإشعار والصف معاً).
 *
 * والشكل من `design/DESIGN.md` §5.3: حلقةٌ برتقالية دوّارة (`spin 2.4s`
 * وقمّتُها شفافة)، عنوان 21/700، نصٌّ 13 بسطرٍ 1.7، ثم بطاقةُ ملاحظةٍ 12
 * بمحاذاةِ بدايةٍ لا توسيط.
 */

import { useEffect, useState } from "react";

import { listDocuments } from "@/api/endpoints";
import { Stagger, StaggerItem } from "@/components/ui/Motion";
import type { DocumentType, DriverDocument } from "@/api/types";
import { useDriver } from "@/lib/driver";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

const DOC_LABEL: Record<DocumentType, string> = {
  driving_license: "رخصة القيادة",
  national_id: "الهوية الشخصية",
  vehicle_registration: "رخصة المركبة والتأمين",
  vehicle_photo: "صور المركبة",
};

const STATUS = {
  approved: { label: "مقبول", tone: "text-ok" },
  rejected: { label: "مرفوض", tone: "text-danger" },
  pending: { label: "قيد المراجعة", tone: "text-warn" },
} as const;

export function PendingScreen() {
  const { signOut } = useSession();
  const { profile } = useDriver();
  const [documents, setDocuments] = useState<DriverDocument[]>([]);

  useEffect(() => {
    listDocuments()
      .then((response) => setDocuments(response.documents))
      .catch(() => undefined);
  }, []);

  const rejected = profile?.driver.status === "rejected";

  return (
    <div className="scr flex h-full flex-col justify-center px-32 pb-safe pt-safe text-center">
      {/* حلقةٌ ناقصةٌ تدور — قمّتُها شفافة كما في التصميم */}
      <span
        className={cn(
          "mx-auto mb-22 block size-64 animate-spin-slow rounded-full border-2 border-t-transparent",
          rejected ? "border-danger" : "border-warn",
        )}
      />

      <h1 className="text-21 font-bold text-ink">
        {rejected ? "لم يُقبل طلبك" : "طلبك قيد المراجعة"}
      </h1>
      <p className="mt-10 text-13 leading-note text-muted">
        {rejected
          ? "راجع أسباب رفض مستنداتك أدناه، ثم أعد رفعها."
          : "تراجع الإدارة مستنداتك عادةً خلال ٢٤ ساعة."}
      </p>

      <div className="mt-22 rounded-14 border border-line bg-surface p-15 text-start text-12 leading-note text-muted">
        لن تستقبل طلبات قبل الاعتماد وقبل شراء اشتراك ساري. سيصلك إشعار عند
        اعتماد الحساب.
      </div>

      {documents.length > 0 ? (
        <Stagger className="mt-12 flex flex-col gap-9 text-start">
          {documents.map((document) => {
            const status = STATUS[document.review_status];
            return (
              <StaggerItem
                key={document.id}
                className="rounded-14 border border-line bg-surface p-13"
              >
                <div className="flex items-center gap-10">
                  <span
                    className={cn(
                      "block size-8 shrink-0 rounded-full",
                      document.review_status === "approved"
                        ? "bg-ok"
                        : document.review_status === "rejected"
                          ? "bg-danger"
                          : "bg-warn",
                    )}
                  />
                  <span className="flex-1 text-12.5 text-ink">
                    {DOC_LABEL[document.doc_type]}
                  </span>
                  <span className={cn("text-11.5 font-semibold", status.tone)}>
                    {status.label}
                  </span>
                </div>
                {/* سببُ الرفض هو ما يجعل إعادة الرفع مجديةً */}
                {document.review_note ? (
                  <p className="mt-8 text-11.5 leading-note text-muted">
                    {document.review_note}
                  </p>
                ) : null}
              </StaggerItem>
            );
          })}
        </Stagger>
      ) : null}

      <button
        type="button"
        onClick={() => void signOut()}
        className="pressable mt-24 p-10 text-13 font-semibold text-danger"
      >
        تسجيل الخروج
      </button>
    </div>
  );
}
