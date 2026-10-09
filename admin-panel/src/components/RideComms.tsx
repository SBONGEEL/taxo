/** **محادثةُ الرحلة ومكالماتُها في تفاصيل الرحلة** (A29 · A34 — SPEC §٦٦، `design/TAXO2-DESIGN-REQUESTS.md` §٤/٧ و§٦/٩).
 *
 * **ولا لوحاتٍ لها بعد** (§٦٦-د/٧): من عُدّة اللوحة القائمة (أقسامُ التفاصيل وشاراتُها) وتُطابَق اللوحاتِ حين تصل.
 *
 * - **A29 المحادثة** — تبويبٌ لا يُرسم إلا لمن يملك `trip_chats.read` (`lib/permissions`)، **ولا تُطلب إلا حين يُفتح**: كلُّ فتحٍ
 *   سطرٌ في التدقيق باسم من فتح (§٦٦-ب/١٠)، فطلبُها مع التفاصيل كان سيكتب «فتح» على من لم يفتح. وفوقها «فتحُك هذه المحادثة
 *   يُسجَّل باسمك». **ومنعٌ واضحٌ** إن ردّ الخادم (مصفوفةٌ تغيّرت بعد القراءة).
 * - **A34 المكالمات** — بياناتٌ وصفيّةٌ بقراءة القوائم: من اتصل بمن، ومتى، وكم، ورُدّ أم لا، وكيف انتهت، وهل سُجّلت. **و«استماع»
 *   لمن يملك `call_recordings.listen` وحدَه**، وفوقه «استماعُك يُسجَّل باسمك» — والملفُّ يُجلب بالجلسة إلى `blob` ويُغلق بإغلاقه.
 *   **و«حذف التسجيل» بالصلاحية نفسِها** (§٧١-ب/٧): تأكيدٌ داخل الصفحة وسببٌ مكتوب، ثمّ يُقرأ السجلُّ من جديد.
 */

import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { callRecordingBlob, eraseCallRecording, getRideChat, listRideCalls } from "@/api/endpoints";
import type { AdminCall, AdminChatThread, ChatReportReason } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { moment } from "@/lib/format";
import { CALL_RECORDINGS_LISTEN, useMyPermissions } from "@/lib/permissions";
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "@/t2/comms.css";

export const REPORT_REASON_LABEL: Record<ChatReportReason, string> = {
  abuse: "إساءة",
  harassment: "تحرّش",
  fraud: "احتيال",
  other: "غير ذلك",
};

const SIDE_LABEL: Record<"rider" | "driver", string> = { rider: "الراكب", driver: "الكبتن" };

/** **المنعُ بنصّه** — ومعه أين تُمنح الصلاحية: لا «خطأ» عامّ يُقرأ عطباً. */
export function TripChatsRefusal() {
  return (
    <div className="ad-cm-refusal" role="alert">
      <Icon name="lock" />
      <div>
        <p className="ad-cm-refusal-title">لا تملك صلاحية «قراءة محادثات الرحلات»</p>
        <p className="ad-hint">
          لا تُعطى لأيِّ مشرفٍ افتراضاً، ولا للمشرف الكامل — تُمنح بالاسم من «المستخدمون والصلاحيات»، وكلُّ فتحٍ يُسجَّل باسم
          من فتح.
        </p>
      </div>
    </div>
  );
}

/** A29 — **محادثةُ الرحلة كما كُتبت**، بأسماء طرفيها لا بأرقامهما، وما عليه بلاغٌ مفتوحٌ موسوم. */
export function RideChatTab({ rideId }: { rideId: string }) {
  const [thread, setThread] = useState<AdminChatThread | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refused, setRefused] = useState(false);

  useEffect(() => {
    let live = true;
    getRideChat(rideId)
      .then((answer) => {
        if (live) setThread(answer);
      })
      .catch((caught) => {
        if (!live) return;
        if (caught instanceof ApiError && caught.status === 403) setRefused(true);
        else setError(caught instanceof ApiError ? caught.message : "تعذّر فتح المحادثة");
      });
    return () => {
      live = false;
    };
  }, [rideId]);

  if (refused) return <TripChatsRefusal />;

  return (
    <section>
      {/* **قبل الرسائل لا بعدها** — من يفتح يعرف أن فتحَه مكتوب */}
      <p className="ad-cm-audit">
        <Icon name="visibility" />
        فتحُك هذه المحادثة يُسجَّل باسمك
      </p>
      <ErrorNote message={error} />
      {thread === null ? (
        error ? null : (
          <div className="ad-sec-loading">
            <Spinner />
          </div>
        )
      ) : thread.messages.length === 0 ? (
        <p className="ad-hint">لا رسائلَ في هذه الرحلة — أو حُذفت بعد مدّة الاحتفاظ.</p>
      ) : (
        <div className="ad-cm-thread">
          {thread.messages.map((message) => (
            <div key={message.id} className={message.sender_role === "driver" ? "ad-cm-msg driver" : "ad-cm-msg"}>
              <p className="ad-cm-who">
                {message.sender_name ?? SIDE_LABEL[message.sender_role]}
                <span className="ad-cm-side"> · {SIDE_LABEL[message.sender_role]}</span>
              </p>
              <p className="ad-cm-body">{message.body}</p>
              <p className="ad-cm-when">
                {moment(message.created_at)}
                {message.read_at ? " · قُرئت" : ""}
                {message.open_reports > 0 ? (
                  <Badge tone="danger" className="ms-8">
                    {message.open_reports > 1 ? `${digits(String(message.open_reports))} بلاغات مفتوحة` : "بلاغٌ مفتوح"}
                  </Badge>
                ) : null}
              </p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

const END_LABEL: Record<NonNullable<AdminCall["end_reason"]>, string> = {
  completed: "اكتملت",
  declined: "رُفضت",
  no_answer: "لم يُجب",
  failed: "تعذّر الاتصال",
  ride_ended: "انتهت الرحلة أثناءها",
  cancelled: "ألغاها المتصل",
};

/** «02:13» — دقائقُ وثوانٍ بخاناتٍ لاتينية. */
function duration(seconds: number | null): string {
  if (seconds === null) return "—";
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

/** A34 — **سجلُّ المكالمات** في التفاصيل، ويغيب القسمُ كلُّه لرحلةٍ بلا مكالمة. */
export function RideCallsSection({ rideId }: { rideId: string }) {
  const held = useMyPermissions();
  const [calls, setCalls] = useState<AdminCall[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    listRideCalls(rideId)
      .then((answer) => {
        if (live) setCalls(answer);
      })
      .catch((caught) => {
        if (live) setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة المكالمات");
      });
    return () => {
      live = false;
    };
  }, [rideId]);

  if (error) return <ErrorNote message={error} />;
  if (!calls || calls.length === 0) return null;
  const listener = held?.has(CALL_RECORDINGS_LISTEN) === true;

  return (
    <section>
      <h3 className="ad-dh">المكالمات</h3>
      <div className="ad-kv">
        {calls.map((call) => (
          <div key={call.id} className="ad-cm-call">
            <div className="ad-cm-call-head">
              <span className="ad-cm-call-who">
                {call.caller_name ?? SIDE_LABEL[call.caller_role]}
                <Icon name="arrow_forward" className="ad-cm-arrow" />
                {call.callee_name ?? SIDE_LABEL[call.caller_role === "rider" ? "driver" : "rider"]}
              </span>
              <Badge tone={call.answered_at ? "ok" : "muted"}>{call.answered_at ? "رُدّ عليها" : "لم يُردّ عليها"}</Badge>
              {call.recorded ? <Badge tone="warn">مسجَّلة</Badge> : null}
            </div>
            <p className="ad-cm-call-line">
              بدأت {moment(call.started_at)} · المدّة <span dir="ltr">{duration(call.duration_seconds)}</span>
              {call.end_reason ? ` · ${END_LABEL[call.end_reason]}` : call.status === "ended" ? "" : " · جارية"}
            </p>
            {call.has_recording && listener ? (
              <>
                <Listen callId={call.id} />
                <Erase
                  callId={call.id}
                  onErased={() =>
                    setCalls((now) =>
                      (now ?? []).map((row) =>
                        row.id === call.id ? { ...row, has_recording: false, recording_expires_at: null } : row,
                      ),
                    )
                  }
                />
              </>
            ) : null}
            {call.recorded && !call.has_recording ? (
              <p className="ad-hint">لا ملفَّ يُستمع إليه — لم يُرفع، أو حُذف بعد مدّة الحفظ.</p>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

/** «استماع» — **الملفُّ لا يُجلب قبل الضغط**: كلُّ جلبٍ سطرٌ في التدقيق، فلا يُكتب استماعٌ لم يقع. */
function Listen({ callId }: { callId: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(
    () => () => {
      if (src) URL.revokeObjectURL(src);
    },
    [src],
  );

  return (
    <div className="ad-cm-listen">
      <p className="ad-cm-audit">
        <Icon name="visibility" />
        استماعُك يُسجَّل باسمك
      </p>
      {src ? (
        <audio className="ad-cm-audio" controls autoPlay src={src} />
      ) : (
        <Button
          size="sm"
          variant="secondary"
          loading={busy}
          onClick={() => {
            setBusy(true);
            setError(null);
            callRecordingBlob(callId)
              .then(setSrc)
              .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "تعذّر فتح التسجيل"))
              .finally(() => setBusy(false));
          }}
        >
          <Icon name="headphones" />
          استماع
        </Button>
      )}
      <ErrorNote message={error} />
    </div>
  );
}

/** «حذف التسجيل» — **تأكيدٌ داخل الصفحة وسببٌ مكتوب** (لا `confirm()`): حذفٌ لا رجعةَ فيه لا يقع بضغطةٍ واحدة. */
function Erase({ callId, onErased }: { callId: string; onErased: () => void }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ready = reason.trim().length >= 8;

  if (!open) {
    return (
      <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>
        <Icon name="close" />
        حذف التسجيل
      </Button>
    );
  }
  return (
    <div className="ad-cm-listen">
      <p className="ad-hint">يُمحى الملفُّ نهائياً ويبقى سطرُ المكالمة. والحذفُ يُسجَّل باسمك وسببِه.</p>
      <Field
        label="السبب"
        id={`erase-${callId}`}
        placeholder="مثال: تسجيلُ تجربةٍ انتهت"
        value={reason}
        onChange={(event) => setReason(event.target.value)}
      />
      <div className="ad-cm-call-head">
        <Button
          size="sm"
          variant="danger"
          disabled={!ready}
          loading={busy}
          onClick={() => {
            setBusy(true);
            setError(null);
            eraseCallRecording(callId, reason.trim())
              .then(onErased)
              .catch((caught: unknown) => setError(caught instanceof ApiError ? caught.message : "تعذّر حذف التسجيل"))
              .finally(() => setBusy(false));
          }}
        >
          احذف نهائياً
        </Button>
        <Button size="sm" variant="secondary" onClick={() => setOpen(false)}>
          تراجع
        </Button>
      </div>
      <ErrorNote message={error} />
    </div>
  );
}
