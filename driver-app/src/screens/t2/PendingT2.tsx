/** «طلبك قيد المراجعة» — TAXO 2.0 «C03» (Claude Design «Captain»)، **في الداكن المرسوم وحدَه** (افتراضُ الكبتن).
 *
 * **الطلبُ هو هو** (`screens/Pending.tsx`): `GET /drivers/me/documents` عند الفتح، ولا غيره. **والأبوابُ هي هي**:
 * «أكمِل ما ينقص»/«أعد رفع المستندات» إلى `/register/documents` بشرطها نفسِه، و«تسجيل الخروج».
 *
 * **وما تغيّر طبقةُ العرض**: الحلقةُ بالساعة الرملية، والخطُّ الزمنيُّ للمراجعة، والملاحظةُ بلون الجمر، وصفوفُ
 * المستندات بأيقوناتها ونبرات حالها.
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته** (`TAXO2-DESIGN-CORRECTIONS.md` §١٧):
 * - **«فحص المركبة» خطوةً في الخطّ**: لا فحصَ ولا موعدَ في التطبيق — خطوةٌ تَعِد بما لا يقع.
 * - **«يمكنك اختيار باقتك من الآن · عرض الباقات»**: لا بابَ إلى الاشتراك من هذه الشاشة اليوم.
 * - **«تواصل مع الدعم»**: لا قناةَ دعمٍ في تطبيق الكبتن.
 *
 * **وما فيها اليومَ ولم يُرسم يبقى**: حالُ كلِّ مستندٍ وسببُ رفضه — **هو ما يجعل إعادةَ الرفع مجدية** — وبابُ ما ينقص،
 * والخروج، **وحالُ الرفض كلُّها**: اللوحةُ لا ترسمها، فتُرسم بلغتها **بلا خطٍّ زمنيٍّ يقول «جارٍ الآن»** عمّا رُفض.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listDocuments } from "@/api/endpoints";
import type { DocumentType, DriverDocument } from "@/api/types";
import { useDriver } from "@/lib/driver";
import { useSession } from "@/lib/session";
import { DISPLAY_LOCALE } from "@/lib/utils";
import { DOC_LABEL, STATUS } from "@/screens/Pending";

import "@/taxo2";
import "./t2.css";

/** أيقونةُ كلِّ مستندٍ بمفردات اللوحة (C12): الرخصةُ والهويةُ والمركبة — **والصورةُ الشخصيةُ بالشخص**. */
const DOC_ICON: Record<DocumentType, string> = {
  driving_license: "badge",
  national_id: "id_card",
  vehicle_registration: "directions_car",
  vehicle_photo: "directions_car",
  vehicle_front: "directions_car",
  vehicle_back: "directions_car",
  vehicle_side_right: "directions_car",
  vehicle_side_left: "directions_car",
  vehicle_interior: "directions_car",
  vehicle_plate: "directions_car",
  profile_photo: "person",
};

/** نبرةُ الحال بألوان C12: ساريةٌ خضراء، ومرفوضةٌ حمراء، وما ينتظر كهرمانيّ. */
const TONE = { approved: "ok", rejected: "danger", pending: "warn" } as const;

/** «اليوم · 09:12» كما في اللوحة — **بخاناتٍ لاتينية** وساعةٍ بأربعٍ وعشرين. */
function receivedAt(iso: string): { day: string; time: string } {
  const at = new Date(iso);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const time = at.toLocaleTimeString(DISPLAY_LOCALE, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  if (at.getTime() >= today) return { day: "اليوم", time };
  if (at.getTime() >= today - 24 * 60 * 60 * 1000) return { day: "أمس", time };
  return { day: at.toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long" }), time };
}

export function PendingT2Screen() {
  const { signOut } = useSession();
  const { profile } = useDriver();
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<DriverDocument[]>([]);
  // **ما ينقص للاعتماد** — من الخلفية لا من قائمةٍ في الشاشة، كالشاشة القائمة
  const [missing, setMissing] = useState<DocumentType[]>([]);

  useEffect(() => {
    listDocuments()
      .then((response) => {
        setDocuments(response.documents);
        setMissing(response.awaiting_upload);
      })
      .catch(() => undefined);
  }, []);

  const rejected = profile?.driver.status === "rejected";
  const received = profile ? receivedAt(profile.driver.created_at) : null;

  return (
    <div className="t2 t2-pending pb-nav">
      <div className={rejected ? "t2-wait rejected" : "t2-wait"} aria-hidden="true">
        <span className="t2-wait-track" />
        <span className="t2-wait-arc" />
        <span className="t2-wait-core">
          <span className="t2-icon">{rejected ? "error" : "hourglass_top"}</span>
        </span>
      </div>

      <h1 className="t2-pending-title">{rejected ? "لم يُقبل طلبك" : "طلبك قيد المراجعة"}</h1>
      <p className="t2-pending-lede">
        {rejected
          ? "راجع أسباب رفض مستنداتك أدناه، ثم أعد رفعها."
          : "نراجع وثائقك عادةً خلال 24 ساعة، ونرسل لك إشعاراً فور الاعتماد."}
      </p>

      {/* **الخطُّ الزمنيُّ للمنتظِر وحدَه** — ولا «فحص المركبة»: لا خطوةَ كهذه في التطبيق (§١٧) */}
      {rejected ? null : (
        <div className="t2-steps">
          <span className="t2-step-dot done">
            <span className="t2-icon" aria-hidden="true">check</span>
          </span>
          <div>
            <div className="t2-step-title">استلمنا طلبك</div>
            {received ? (
              <div className="t2-step-sub">
                {received.day} · <span dir="ltr">{received.time}</span>
              </div>
            ) : null}
          </div>
          <span className="t2-step-line done" />
          <span />
          <span className="t2-step-dot now" />
          <div>
            <div className="t2-step-title now">مراجعة الوثائق</div>
            <div className="t2-step-sub now">جارٍ الآن</div>
          </div>
          <span className="t2-step-line" />
          <span />
          <span className="t2-step-dot" />
          <div>
            <div className="t2-step-title later">تفعيل الحساب</div>
          </div>
        </div>
      )}

      <div className="t2-hint">
        <span className="t2-icon" aria-hidden="true">info</span>
        <span>لن تصلك طلبات قبل الاعتماد وتفعيل اشتراك.</span>
      </div>

      {documents.length > 0 ? (
        <div className="t2-docs">
          {documents.map((document) => (
            <div key={document.id} className="t2-doc">
              <div className="t2-doc-row">
                <span className={`t2-doc-icon ${TONE[document.review_status]}`}>
                  <span className="t2-icon" aria-hidden="true">{DOC_ICON[document.doc_type]}</span>
                </span>
                <span className="t2-doc-label">{DOC_LABEL[document.doc_type]}</span>
                <span className={`t2-chip ${TONE[document.review_status]}`}>
                  {STATUS[document.review_status].label}
                </span>
              </div>
              {/* سببُ الرفض هو ما يجعل إعادةَ الرفع مجدية */}
              {document.review_note ? <p className="t2-doc-note">{document.review_note}</p> : null}
            </div>
          ))}
        </div>
      ) : null}

      {/* **البابُ إلى ما ينقص** بشرطه في الشاشة القائمة — قاعدةٌ بلا بابٍ ليست قاعدة */}
      {missing.length > 0 || rejected ? (
        <button type="button" className="t2-cta" onClick={() => navigate("/register/documents")}>
          {rejected ? "أعد رفع المستندات" : "أكمِل ما ينقص"}
        </button>
      ) : null}

      <button type="button" className="t2-signout" onClick={() => void signOut()}>
        تسجيل الخروج
      </button>
    </div>
  );
}
