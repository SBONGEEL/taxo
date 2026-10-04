/** الوثائق — TAXO 2.0 «C12» (Claude Design «Captain»)، **في الداكن المرسوم وحدَه**.
 *
 * **وجهٌ ثانٍ لا شاشةٌ ثانية**: المستنداتُ ورفعُها والمركبةُ وتعديلُها من `useVehicleScreen` (`screens/Vehicle.tsx`) —
 * **فالرفعُ نفسُه** (الضغطُ ثمّ `POST /drivers/me/documents/{type}` ثمّ إعادةُ القراءة) **ورسالتُه نفسُها**.
 *
 * **والحالُ من الصفّ لا من اللوحة**: «سارية حتى» و«تنتهي خلال» و«انتهى في» من `expires_on`، و«رُفعت» من `updated_at`،
 * و«الاستقبال متوقف» من حال الكبتن (`drivers.status`) — **والتعليقُ عند الانتهاء تفعله الخلفيةُ لا هذه الشاشة**
 * (`services/document_expiry.py`: «تنتهي في ١٥» تعني أنها **لا تصلح في ١٥**).
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته** (`design/drafts/captain-C09-C12.md`):
 * - **«تأمين المركبة» و«شهادة عدم محكومية»**: لا نوعَ لهما في `DocumentType` ولا تطلبهما الخلفية — والصفوفُ
 *   هي المطلوبُ كما في الشاشة القائمة (`REQUIRED_DOCUMENTS`).
 * - **«لن تصلك طلبات حتى ترفع وثيقة سارية»**: الرفعُ يعيدها «قيد المراجعة» والتعليقُ لا يُرفع إلا باعتمادها
 *   (`document_expiry.py` §٤) — فالجملةُ تقول ذلك.
 *
 * **وما في الشاشة القائمة ولم يُرسم يبقى بلغة اللوحة**: صورُ المركبة الستّ · المرفوضُ وسببُه · المركبةُ وتعديلُها ·
 * سطرُ الاستبدال. **واستبدالُ وثيقةٍ سارية** (زرُّ «استبدال الملف» في القائمة): الصفُّ نفسُه زرّ.
 */

import { useRef } from "react";

import type { DocumentType, DriverDocument } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { CATEGORY_LABEL } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";
import {
  DOC_LABEL,
  REVIEW_LABEL,
  VehicleForm,
  useVehicleScreen,
} from "@/screens/Vehicle";

import { countDays } from "./count";

import "@/taxo2";
import "./t2.css";

/** **أيقونةُ كلِّ نوعٍ كما رسمتها اللوحة** — وصورُ المركبة (لم تُرسم) بالكاميرا: صورةٌ تُلتقط لا وثيقةٌ تُحمل. */
const DOC_ICON: Record<DocumentType, string> = {
  driving_license: "badge",
  national_id: "id_card",
  vehicle_registration: "directions_car",
  vehicle_photo: "photo_camera",
  vehicle_front: "photo_camera",
  vehicle_back: "photo_camera",
  vehicle_side_right: "photo_camera",
  vehicle_side_left: "photo_camera",
  vehicle_interior: "photo_camera",
  vehicle_plate: "photo_camera",
  profile_photo: "person",
};

/** صورُ المركبة — زرُّها «ارفع صورة» كما في الشاشة القائمة، والوثائقُ «ارفع الوثيقة» كما في اللوحة. */
const PHOTO = new Set<DocumentType>([
  "vehicle_photo",
  "vehicle_front",
  "vehicle_back",
  "vehicle_side_right",
  "vehicle_side_left",
  "vehicle_interior",
  "vehicle_plate",
  "profile_photo",
]);

/** **عتبةُ «تنتهي خلال»**: أبعدُ عتبات التنبيه في الخلفية (`document_expiry.NOTICE_DAYS` = 30 · 7 · 1) — فما يُرسم
 *  كهرمانياً هنا هو ما وصل الكبتنَ إشعارُه. */
const EXPIRING_DAYS = 30;

/** ما يقبله الرفعُ — **نفسُ قائمة الشاشة القائمة** (`DocumentRow`)، والخلفيةُ هي الحكَم. */
const ACCEPT = "image/jpeg,image/png,image/webp,application/pdf";

type Tone = "ok" | "warn" | "danger" | "off";

interface DocView {
  tone: Tone;
  sub: string;
  /** يُعدّ في «X من Y سارية»: مقبولٌ لم ينتهِ — **وما ينتهي قريباً ما زال سارياً** كما في اللوحة. */
  valid: boolean;
  end: "valid" | "pending" | "renew" | "upload";
  /** إطارٌ أحمر: ما يوقف الاستقبالَ أو يمنع الاعتماد. */
  alarm: boolean;
  note: string | null;
}

/** «2028-03-14» ← «14/03/2028» — **من النصّ لا من `Date`**: تاريخٌ بلا ساعةٍ لا ينزاح بمنطقة الجهاز. */
function dmyOfDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

/** لحظةُ الرفع بيوم الجهاز. */
function dmyOfInstant(iso: string): string {
  const at = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(at.getDate())}/${pad(at.getMonth() + 1)}/${at.getFullYear()}`;
}

/** الأيامُ من اليوم إلى تاريخ — موجبٌ لما بعده وسالبٌ لما قبله (يومُ الجهاز). */
function daysUntil(iso: string, today: Date): number {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  const target = Date.UTC(y, m - 1, d);
  const base = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((target - base) / 86_400_000);
}

function viewOf(
  docType: DocumentType,
  document: DriverDocument | undefined,
  today: Date,
): DocView {
  if (!document) {
    return {
      tone: "off",
      sub: "لم يُرفع",
      valid: false,
      end: "upload",
      alarm: false,
      note: null,
    };
  }
  const uploaded = `رُفعت ${dmyOfInstant(document.updated_at)}`;
  if (document.review_status === "pending") {
    return {
      tone: "off",
      sub: uploaded,
      valid: false,
      end: "pending",
      alarm: false,
      note: null,
    };
  }
  if (document.review_status === "rejected") {
    // **وسببُ الرفض بنصّ المشرف** كما في الشاشة القائمة — سطرٌ أحمرُ تحت الصفّ بلغة اللوحة
    return {
      tone: "danger",
      sub: REVIEW_LABEL.rejected.text,
      valid: false,
      end: "upload",
      alarm: true,
      note: document.review_note,
    };
  }
  if (!document.expires_on) {
    return {
      tone: "ok",
      sub: uploaded,
      valid: true,
      end: "valid",
      alarm: false,
      note: null,
    };
  }
  const left = daysUntil(document.expires_on, today);
  const date = dmyOfDate(document.expires_on);
  if (left <= 0) {
    const since = left === 0 ? "اليوم" : `منذ ${countDays(-left, true)}`;
    return {
      tone: "danger",
      sub: `انتهى في ${date}`,
      valid: false,
      end: "upload",
      alarm: true,
      note: `انتهت صلاحية ${DOC_LABEL[docType]} ${since} — لن تصلك طلبات حتى ترفع وثيقةً ساريةً ويعتمدها المشرف.`,
    };
  }
  if (left <= EXPIRING_DAYS) {
    return {
      tone: "warn",
      sub: `تنتهي خلال ${countDays(left, true)} · ${date}`,
      valid: true,
      end: "renew",
      alarm: false,
      note: null,
    };
  }
  return {
    tone: "ok",
    sub: `سارية حتى ${date}`,
    valid: true,
    end: "valid",
    alarm: false,
    note: null,
  };
}

export function VehicleT2Screen() {
  const s = useVehicleScreen();
  const today = new Date();
  const rows = s.types.map((docType) => ({
    docType,
    view: viewOf(
      docType,
      s.state?.documents.find((entry) => entry.doc_type === docType),
      today,
    ),
  }));
  const valid = rows.filter((row) => row.view.valid).length;
  // **«الاستقبال متوقف» حالُ الكبتن لا حسابُ الشاشة**: معلَّقٌ أو قيدُ المراجعة لا يصله طلب
  const stopped = s.profile !== null && s.profile.driver.status !== "approved";

  return (
    <div className="t2 t2-vdocs scr">
      <div className="t2-head">
        <button
          type="button"
          className="t2-back"
          aria-label="رجوع"
          onClick={() => s.goBack()}
        >
          <span className="t2-icon" aria-hidden="true">
            arrow_forward
          </span>
        </button>
        <h1 className="t2-title">الوثائق</h1>
      </div>

      {s.state ? (
        <div className="t2-vdocs-sum">
          <div className="t2-vdocs-sum-top">
            <span className="t2-vdocs-count">
              {digits(String(valid))} من {digits(String(rows.length))} سارية
            </span>
            {stopped ? (
              <span className="t2-vdocs-stop">الاستقبال متوقف</span>
            ) : null}
          </div>
          <div className="t2-vdocs-bar" aria-hidden="true">
            {rows.map((row) => (
              <span
                key={row.docType}
                className={`t2-vdocs-seg ${row.view.tone}`}
              />
            ))}
          </div>
        </div>
      ) : null}

      {s.error ? (
        <p className="t2-note danger">
          <span className="t2-icon" aria-hidden="true">
            error
          </span>
          {s.error}
        </p>
      ) : null}
      {s.done ? <p className="t2-vdocs-done">{s.done}</p> : null}

      {s.state === null && !s.error ? (
        <div className="t2-vdocs-loading">
          <Spinner />
        </div>
      ) : null}

      {s.state ? (
        <div className="t2-vdocs-list">
          {rows.map(({ docType, view }) => (
            <DocRow
              key={docType}
              docType={docType}
              view={view}
              busy={s.busy === docType}
              onPick={(file) => void s.replace(docType, file)}
            />
          ))}
        </div>
      ) : null}

      {/* سطرُ الاستبدال بنصّه — ثمنُ الرفع يُقال قبل الرفع */}
      <p className="t2-vdocs-fine">
        رفعُ مستندٍ من جديد يستبدل القديم ويعيده «قيد المراجعة». وإن كان حسابك
        معتمداً فسيعود قيد المراجعة حتى تُقبل الوثيقة الجديدة.
      </p>

      {/* ── المركبة: في الشاشة القائمة ولم تُرسم — بياناتُها وتعديلُها بنموذجها نفسِه ── */}
      <div className="t2-section">المركبة</div>
      {s.vehicle ? (
        <div className="t2-vdocs-car">
          <div className="t2-vdocs-car-top">
            <span className="t2-vdocs-car-name">
              {s.vehicle.make} {s.vehicle.model}
            </span>
            <span className="t2-vdocs-car-cat">
              {CATEGORY_LABEL[s.vehicle.category]}
            </span>
          </div>
          {s.editing ? (
            // **نموذجُ التعديل نفسُه** — بألوان الهوية عبر جسر الألوان القائمة (`.t2-legacy`)، ويقول ثمنَ التعديل قبل الحفظ
            <div className="t2-legacy t2-vdocs-form">
              <VehicleForm
                vehicle={s.vehicle}
                approved={s.profile?.driver.status === "approved"}
                onCancel={() => s.setEditing(false)}
                onSaved={(reverted) => {
                  s.setEditing(false);
                  s.setReverted(reverted);
                  void s.refresh();
                }}
              />
            </div>
          ) : (
            <>
              <div className="t2-vdocs-pair">
                <span>سنة الصنع</span>
                <span>{digits(String(s.vehicle.year))}</span>
              </div>
              <div className="t2-vdocs-pair">
                <span>اللون</span>
                <span>{s.vehicle.color}</span>
              </div>
              {/* اللوحةُ معرّفٌ مطبوعٌ على المركبة — تُعرض كما هي */}
              <div className="t2-vdocs-pair">
                <span>رقم اللوحة</span>
                <span dir="ltr">{s.vehicle.plate_number}</span>
              </div>
              <button
                type="button"
                className="t2-more t2-vdocs-edit"
                onClick={() => s.setEditing(true)}
              >
                تعديل بيانات المركبة
              </button>
              {s.reverted ? (
                <p className="t2-note warn">
                  <span className="t2-icon" aria-hidden="true">
                    error
                  </span>
                  غُيّرت بياناتٌ في رخصة المركبة، فعاد حسابُك «قيد المراجعة» حتى
                  يعتمدها المشرف — ولا تصلك طلباتٌ حتى ذلك.
                </p>
              ) : null}
            </>
          )}
        </div>
      ) : (
        <p className="t2-empty">
          لا مركبة مسجّلة على حسابك. راجع الدعم لتسجيلها.
        </p>
      )}
    </div>
  );
}

/** **صفُّ الوثيقة كما رسمته اللوحة** — والصفُّ كلُّه زرٌّ يفتح الملفّات: «جدّد» و«ارفع الوثيقة» يُرسمان فيه، **والساري
 *  وقيدُ المراجعة يُستبدلان منه** كما كان «استبدال الملف» في الشاشة القائمة. */
function DocRow({
  docType,
  view,
  busy,
  onPick,
}: {
  docType: DocumentType;
  view: DocView;
  busy: boolean;
  onPick: (file: File) => void;
}) {
  const input = useRef<HTMLInputElement | null>(null);
  const label = DOC_LABEL[docType];

  return (
    <div>
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onPick(file);
          event.target.value = "";
        }}
      />
      {/* **صفُّ C03 نفسُه** (`.t2-doc` · `.t2-doc-row` · `.t2-doc-icon` في `PendingT2`) — اللوحةُ ترسمه في الشاشتين بقيمٍ واحدة */}
      <button
        type="button"
        disabled={busy}
        aria-label={`${label} — ${view.end === "upload" ? "ارفع" : "استبدال الملف"}`}
        className={
          view.alarm ? "t2-doc t2-vdocs-row alarm" : "t2-doc t2-vdocs-row"
        }
        onClick={() => input.current?.click()}
      >
        <span className="t2-doc-row">
          <span
            className={
              view.tone === "off" ? "t2-doc-icon" : `t2-doc-icon ${view.tone}`
            }
            aria-hidden="true"
          >
            <span className="t2-icon">{DOC_ICON[docType]}</span>
          </span>
          <span className="t2-vdocs-main">
            <span className="t2-vdocs-title">{label}</span>
            <span
              className={
                view.tone === "warn" ? "t2-vdocs-sub warn" : "t2-vdocs-sub"
              }
            >
              {view.sub}
            </span>
          </span>
          {busy ? (
            <span className="t2-vdocs-busy">…</span>
          ) : view.end === "valid" ? (
            <span className="t2-chip ok">سارية</span>
          ) : view.end === "pending" ? (
            <span className="t2-chip t2-vdocs-chip-off">
              {REVIEW_LABEL.pending.text}
            </span>
          ) : view.end === "renew" ? (
            <span className="t2-vdocs-renew">جدّد</span>
          ) : (
            <span className="t2-vdocs-upload">
              {PHOTO.has(docType) ? "ارفع صورة" : "ارفع الوثيقة"}
            </span>
          )}
        </span>
      </button>
      {view.note ? (
        <p className="t2-note danger t2-vdocs-note">
          <span className="t2-icon" aria-hidden="true">
            error
          </span>
          {view.note}
        </p>
      ) : null}
    </div>
  );
}
