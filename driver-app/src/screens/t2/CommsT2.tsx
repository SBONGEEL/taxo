/** **المحادثةُ والمكالمةُ داخل الرحلة — شاشاتُهما** (SPEC §٦٦، `design/TAXO2-DESIGN-REQUESTS.md` §٤/١ و§٦).
 *
 * **لا لوحاتٍ لهما في TAXO 2.0 بعد** (§٦٦-د/٧): تُبنى من مكوّنات العائلة القائمة (`taxo2` ورموزها) **في الأوضاع الثلاثة** —
 * الفاتح والداكن والنسائيّ (الجمرُ يصير برقوقاً من الرموز نفسِها) — **وتُطابَق اللوحاتِ حين تصل، ولا تُرفع إلى الإنتاج قبلها**.
 *
 * - `CommsButtonsT2` — «رسالة» بشارة ما لم يُقرأ و«اتصال»، في ورقة الرحلة (R08 · R09 عند الراكب، C06 · C07 عند الكبتن).
 * - `CommsLayerT2` — فوق كلِّ شاشة: ورقةُ المحادثة وورقةُ البلاغ، وشاشةُ المكالمة بأطوارها **وشريطُها المصغَّر** أعلى الشاشة.
 *   **وتنبيهُ رسالةٍ والمحادثةُ مغلقة** ببلاغ التطبيق القائم (`toast`) وشارةِ «رسالة».
 *
 * **والصياغاتُ بحرف التصميم المُقَرّ** (`design/APPROVALS-DATA.md` §١ و§٦): سطرُ المراجعة من الخادم (`notice`) لا من هنا، ورفضُ
 * الرسائل بنصّ الخادم. **ونسخةٌ واحدةٌ في التطبيقين حرفاً** — ما يفترق (الطرفُ الآخر ورأسُه) يصل من `useComms`.
 */

import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import type { ChatMessage, ChatReportReason } from "@/api/types";
import { callClock, useComms, type CallView, type ChatView, type CommsPeer } from "@/lib/comms";
import { DISPLAY_LOCALE } from "@/lib/utils";
import { Icon } from "@/taxo2";
import "@/taxo2";
import "./comms.css"; import { tr } from "@/lib/i18n";

/** **الجملةُ المُقَرّة بحرفها** — قبل رنين مكالمةٍ مسجَّلة، عند المتصل وفوق «ردّ» عند المتصَل به (§٦٦-ج/١٦). */
const RECORDING_NOTICE = tr("هذه المكالمة ستُسجَّل للسلامة والجودة، وتُحفظ مدّةً محدودةً ثمّ تُحذف.");
const CLOSED_LINE = tr("انتهت الرحلة، وأُغلقت المحادثة.");

const REASONS: { value: ChatReportReason; label: string }[] = [
  { value: "abuse", label: tr("إساءة") },
  { value: "harassment", label: tr("تحرّش") },
  { value: "fraud", label: tr("احتيال") },
  { value: "other", label: tr("غير ذلك") },
];

/** «10:42» — ساعةُ الرسالة بخاناتٍ لاتينية ولغةٍ مثبَّتة (§20). */
const TIME = new Intl.DateTimeFormat(DISPLAY_LOCALE, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });

function timeOf(iso: string): string {
  return TIME.format(new Date(iso));
}

// ═════════════════════════════════════════ الزرّان في ورقة الرحلة

/** **«رسالة» و«اتصال»** — من قبول الكبتن حتى تنتهي الرحلة (`canMessage` · `canCall`)، **ويغيبان بعدها** (§٦٦-أ/١). */
export function CommsButtonsT2() {
  const comms = useComms();
  if (!comms || (!comms.canMessage && !comms.canCall)) return null;
  return (
    <div className="t2-cm-actions">
      {comms.canMessage ? (
        <button type="button" className="t2-cm-action" onClick={() => comms.openChat()}>
          <Icon name="chat" />
          {tr("رسالة")}
          {comms.unread > 0 ? (
            <span className="t2-cm-count" aria-label={tr("{0} غير مقروءة", { 0: comms.unread })}>
              {comms.unread > 9 ? "9+" : comms.unread}
            </span>
          ) : null}
        </button>
      ) : null}
      {comms.canCall ? (
        <button type="button" className="t2-cm-action" onClick={comms.startCall}>
          <Icon name="call" />
          {tr("اتصال")}
        </button>
      ) : null}
    </div>
  );
}

// ═════════════════════════════════════════ الطبقة فوق الشاشات

export function CommsLayerT2() {
  const comms = useComms();
  if (!comms) return null;
  const { chat, call, peer, peerRole } = comms;
  const live = call !== null && call.stage !== "broken" && call.stage !== "unanswered" && call.stage !== "tripover";
  // **ورسالةٌ والمحادثةُ مغلقة تُقال ببلاغ التطبيق نفسِه** (`lib/comms.tsx → alertMessage`) — لا تنبيهَ ثانٍ هنا يقع فوقه
  return (
    <>
      {chat ? <ChatSheetT2 chat={chat} /> : null}
      {call && call.minimized && live ? <CallStripT2 call={call} peer={peer} peerRole={peerRole} /> : null}
      {call && !call.minimized ? <CallScreenT2 call={call} peer={peer} peerRole={peerRole} /> : null}
    </>
  );
}

/** دائرةُ الطرف الآخر — صورتُه حيث تُعرض (الكبتن عند الراكب)، وإلا حرفٌ لا يكشف أحداً. */
function PeerFace({ peer, large = false }: { peer: CommsPeer | null; large?: boolean }) {
  return (
    <span className={large ? "t2-cm-face lg" : "t2-cm-face"}>
      {peer?.avatar ?? <Icon name="person" />}
    </span>
  );
}

// ═════════════════════════════════════════ ورقةُ المحادثة

function ChatSheetT2({ chat }: { chat: ChatView }) {
  const comms = useComms()!;
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [reporting, setReporting] = useState<ChatMessage | null>(null);
  const list = useRef<HTMLDivElement | null>(null);
  const thread = chat.thread;
  const messages = thread?.messages ?? [];
  const writable = thread !== null && thread.open && chat.live;
  // **الطرفُ الآخر في الرأس للرحلة الجارية وحدَها** — محادثةُ رحلةٍ مضت تُقرأ برأسٍ عامّ
  const current = chat.live;
  const peer = current ? comms.peer : null;
  const max = thread?.max_chars ?? 300;
  // **«قُرئت» تحت آخر رسالةٍ منّي قرأها الطرفُ الآخر**
  const lastRead = [...messages].reverse().find((message) => message.mine && message.read_at !== null)?.id ?? null;

  useLayoutEffect(() => {
    const box = list.current;
    if (box) box.scrollTop = box.scrollHeight;
  }, [messages.length]);

  /** **الحقلُ يُفرَّغ لحظةَ الإرسال لا بعد جواب الخادم** (قِيس في تجربة المتصفّحين ٢٠٢٦-١٠-٠٨): البابُ يُرسل إشعارَ الطرف الآخر قبل
   *  أن يجيب، والرسالةُ تظهر من المقبس قبله (٠٫٢ ث) — **وجوابُه جاء بعد ٠٫٩ ث في تشغيلٍ، ولم يجئ في خمسٍ وثلاثين ثانيةً في آخر**
   *  (أوّلُ إشعارٍ إلى رمزٍ ميت). وكان الحقلُ معطَّلاً طوالها، **ثمّ يمحو ما كُتب بعدها حين يصل الجواب**. فيُفرَّغ فوراً، **ويعود النصُّ
   *  إن رُفض** (رقمُ هاتف · رابط) ما لم يُكتب غيرُه — ولا تعطيلَ بينهما. */
  async function submit() {
    const text = draft.trim();
    if (!text) return;
    setError(null);
    setDraft("");
    const refused = await comms.send(text);
    if (refused) {
      setError(refused);
      setDraft((current) => (current ? current : text));
    }
  }

  return (
    <div className="t2 t2-cm-shade" onClick={comms.closeChat}>
      <section
        className="t2-cm-sheet"
        role="dialog"
        aria-modal="true"
        aria-label={tr("المحادثة")}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="t2-cm-grab" aria-hidden="true" />
        <header className="t2-cm-head">
          <button type="button" className="t2-cm-round" onClick={comms.closeChat} aria-label={tr("إغلاق")}>
            <Icon name="close" />
          </button>
          <PeerFace peer={peer} />
          <div className="t2-cm-who">
            <div className="t2-cm-name">{peer?.name ?? comms.peerRole}</div>
            {peer?.meta || peer?.plate ? (
              <div className="t2-cm-meta">
                {peer.meta}
                {peer.meta && peer.plate ? " · " : null}
                {peer.plate ? <span dir="ltr">{peer.plate}</span> : null}
              </div>
            ) : null}
          </div>
          {/* **«اتصال» في رأس المحادثة نفسِها** (§٦ البند ٧) — ويغيب بإغلاقها */}
          {current && comms.canCall && writable ? (
            <button type="button" className="t2-cm-round accent" onClick={comms.startCall} aria-label={tr("اتصال")}>
              <Icon name="call" />
            </button>
          ) : null}
        </header>

        {thread ? (
          <p className="t2-cm-notice">
            <Icon name="verified_user" />
            <span>{thread.notice}</span>
          </p>
        ) : null}

        <div className="t2-cm-list" ref={list}>
          {thread === null ? (
            chat.error ? (
              <p className="t2-note danger" role="alert">
                <Icon name="error" />
                <span>{chat.error}</span>
              </p>
            ) : (
              <span className="t2-cm-loading" role="status" aria-label={tr("جارٍ التحميل")} />
            )
          ) : messages.length === 0 ? (
            <p className="t2-cm-empty">{tr("لا رسائلَ بعد — اكتب لـ")}{comms.peerRole}{" "}{tr("ما يحتاج أن يعرفه.")}</p>
          ) : (
            messages.map((message) => (
              <Bubble
                key={message.id}
                message={message}
                read={message.id === lastRead}
                onReport={message.mine ? null : () => setReporting(message)}
              />
            ))
          )}
        </div>

        <footer className="t2-cm-foot">
          {thread === null ? null : writable ? (
            <>
              {error ? (
                <p className="t2-note danger t2-cm-error" role="alert">
                  <Icon name="error" />
                  <span>{error}</span>
                </p>
              ) : null}
              <form
                className="t2-cm-compose"
                onSubmit={(event) => {
                  event.preventDefault();
                  void submit();
                }}
              >
                <input
                  className="t2-input t2-cm-input"
                  value={draft}
                  maxLength={max}
                  placeholder={tr("اكتب رسالة…")}
                  aria-label={tr("الرسالة")}
                  enterKeyHint="send"
                  onChange={(event) => {
                    setDraft(event.target.value);
                    if (error) setError(null);
                  }}
                />
                <button type="submit" className="t2-cm-send" disabled={!draft.trim()} aria-label={tr("إرسال")}>
                  <Icon name="send" />
                </button>
              </form>
              {/* **العدّادُ حين يقترب الحدّ** — لا رقمَ يملأ السطرَ من أوّل حرف */}
              {draft.length > max - 40 ? (
                <p className="t2-cm-chars" dir="ltr">
                  {draft.length}/{max}
                </p>
              ) : null}
            </>
          ) : (
            // **بعد الإغلاق**: سطرٌ مكانَ حقل الكتابة، والرسائلُ مقروءة (§٦٦-ب، `APPROVALS-DATA` §١)
            <p className="t2-cm-closed">
              <Icon name="lock" />
              <span>{chat.live ? tr("المحادثةُ غيرُ متاحةٍ الآن.") : CLOSED_LINE}</span>
            </p>
          )}
        </footer>

        {reporting ? <ReportSheetT2 message={reporting} onClose={() => setReporting(null)} /> : null}
      </section>
    </div>
  );
}

/** فقاعة — **ولمسةٌ مطوّلةٌ على رسالة الطرف الآخر تفتح البلاغ** (وزرُّ القائمة السياقية مثلُها: لوحةُ مفاتيح أو فأرة). */
function Bubble({ message, read, onReport }: { message: ChatMessage; read: boolean; onReport: (() => void) | null }) {
  const timer = useRef<number | null>(null);
  const cancel = () => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
  };
  useEffect(() => cancel, []);
  const press = (event: ReactPointerEvent) => {
    if (!onReport || event.button > 0) return;
    cancel();
    timer.current = window.setTimeout(() => {
      timer.current = null;
      onReport();
    }, 550);
  };
  return (
    <div className={message.mine ? "t2-cm-row mine" : "t2-cm-row"}>
      <div
        className="t2-cm-bubble"
        onPointerDown={press}
        onPointerUp={cancel}
        onPointerLeave={cancel}
        onPointerCancel={cancel}
        onContextMenu={(event) => {
          if (!onReport) return;
          event.preventDefault();
          cancel();
          onReport();
        }}
      >
        {message.body}
      </div>
      <div className="t2-cm-when">
        <span dir="ltr">{timeOf(message.created_at)}</span>
        {read ? <span className="t2-cm-read">{" "}{tr("· قُرئت")}</span> : null}
      </div>
    </div>
  );
}

/** ورقةُ البلاغ — السببُ وسطرٌ اختياريّ و«أبلغ» ← «وصل بلاغُك، وسيراجعه فريقُ TAXO.» */
function ReportSheetT2({ message, onClose }: { message: ChatMessage; onClose: () => void }) {
  const comms = useComms()!;
  const [reason, setReason] = useState<ChatReportReason | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function submit() {
    if (!reason || busy) return;
    setBusy(true);
    setError(null);
    const refused = await comms.report(message.id, reason, note);
    setBusy(false);
    if (refused) setError(refused);
    else setSent(true);
  }

  return (
    <div className="t2-cm-report-shade" onClick={onClose}>
      <div className="t2-cm-report" role="dialog" aria-modal="true" aria-label={tr("أبلغ عن الرسالة")} onClick={(e) => e.stopPropagation()}>
        <div className="t2-cm-grab" aria-hidden="true" />
        {sent ? (
          <>
            <p className="t2-cm-report-done">
              <Icon name="check_circle" fill />
              <span>{tr("وصل بلاغُك، وسيراجعه فريقُ TAXO.")}</span>
            </p>
            <button type="button" className="t2-button primary t2-cm-wide" onClick={onClose}>
              {tr("تمّ")}
            </button>
          </>
        ) : (
          <>
            <h2 className="t2-cm-report-title">
              <Icon name="flag" />
              {tr("أبلغ عن الرسالة")}
            </h2>
            <blockquote className="t2-cm-quote">{message.body}</blockquote>
            <div className="t2-cm-reasons" role="radiogroup" aria-label={tr("السبب")}>
              {REASONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  role="radio"
                  aria-checked={reason === option.value}
                  className={reason === option.value ? "t2-cm-reason on" : "t2-cm-reason"}
                  onClick={() => setReason(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <input
              className="t2-input t2-cm-note"
              value={note}
              maxLength={200}
              placeholder={tr("سطرٌ يوضّح ما وقع (اختياريّ)")}
              aria-label={tr("ملاحظة")}
              onChange={(event) => setNote(event.target.value)}
            />
            {error ? (
              <p className="t2-note danger" role="alert">
                <Icon name="error" />
                <span>{error}</span>
              </p>
            ) : null}
            <button
              type="button"
              className="t2-button action t2-cm-wide"
              disabled={!reason || busy}
              aria-busy={busy}
              onClick={() => void submit()}
            >
              {tr("أبلغ")}
            </button>
            <button type="button" className="t2-cm-text" onClick={onClose}>
              {tr("تراجع")}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ═════════════════════════════════════════ المكالمة

/** المدّةُ تعدّ — كلَّ ثانية، **من لحظة وصول الصوت** لا من الرنين. */
function useElapsed(since: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (since === null) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, [since]);
  return since === null ? 0 : Math.max(0, (now - since) / 1000);
}

/** سطرُ الحال تحت الاسم — **بحرف التصميم** (§٦ البنود ٢–٦). */
function stageLine(call: CallView, elapsed: number): string {
  switch (call.stage) {
    case "preparing":
    case "joining":
      return tr("جارٍ الاتصال…");
    case "consent":
      return tr("قبل أن نتّصل");
    case "dialing":
      return tr("يرنّ…");
    case "incoming":
      return tr("مكالمةٌ واردة — رحلتُك الحالية");
    case "talking":
      return callClock(elapsed);
    case "broken":
      return call.reason ?? tr("تعذّر الاتصال، الشبكةُ ضعيفة.");
    case "unanswered":
      return tr("لم يُجب");
    case "tripover":
      return tr("انتهت الرحلة، فلا اتصال الآن.");
    case "hungup":
      return call.lasted !== null && call.lasted > 0 ? tr("انتهت المكالمة · {0}", { 0: callClock(call.lasted) }) : tr("انتهت المكالمة");
  }
}

function CallScreenT2({ call, peer, peerRole }: { call: CallView; peer: CommsPeer | null; peerRole: string }) {
  const comms = useComms()!;
  const elapsed = useElapsed(call.stage === "talking" ? call.since : null);
  const ongoing = call.stage === "preparing" || call.stage === "dialing" || call.stage === "joining" || call.stage === "talking";
  const failed = call.stage === "broken" || call.stage === "unanswered";
  return (
    <div className="t2 t2-cm-call" role="dialog" aria-modal="true" aria-label={call.stage === "incoming" ? tr("مكالمةٌ واردة") : tr("المكالمة")}>
      <div className="t2-cm-call-top">
        {ongoing ? (
          <button type="button" className="t2-cm-round" onClick={() => comms.minimize(true)} aria-label={tr("تصغير")}>
            <Icon name="expand_more" />
          </button>
        ) : (
          <span />
        )}
        {call.recording && (call.stage === "talking" || call.stage === "joining" || call.stage === "dialing") ? (
          <span className="t2-cm-rec">
            <Icon name="radio_button_checked" fill />
            {tr("مسجَّلة")}
          </span>
        ) : null}
      </div>

      <div className="t2-cm-call-who">
        <PeerFace peer={peer} large />
        <div className="t2-cm-call-name">{peer?.name ?? peerRole}</div>
        {peer?.meta ? <div className="t2-cm-call-meta">{peer.meta}</div> : null}
        <div
          className={failed || call.stage === "tripover" ? "t2-cm-call-line bad" : "t2-cm-call-line"}
          dir={call.stage === "talking" ? "ltr" : undefined}
          role={failed ? "alert" : "status"}
        >
          {stageLine(call, elapsed)}
        </div>
        {call.stage === "talking" && call.weak ? <div className="t2-cm-call-weak">{tr("الشبكةُ ضعيفة…")}</div> : null}
      </div>

      {call.stage === "consent" ? (
        <div className="t2-cm-consent">
          <p className="t2-cm-consent-text">
            <Icon name="radio_button_checked" fill />
            <span>{RECORDING_NOTICE}</span>
          </p>
          <div className="t2-cm-pair">
            <button type="button" className="t2-button secondary" onClick={() => comms.consent(false)}>
              {tr("إلغاء")}
            </button>
            <button type="button" className="t2-button action" onClick={() => comms.consent(true)}>
              {tr("متابعة")}
            </button>
          </div>
        </div>
      ) : call.stage === "incoming" ? (
        <div className="t2-cm-incoming">
          {call.recording ? (
            <p className="t2-cm-consent-text">
              <Icon name="radio_button_checked" fill />
              <span>{RECORDING_NOTICE}</span>
            </p>
          ) : null}
          <div className="t2-cm-big">
            <button type="button" className="t2-cm-bigbtn decline" onClick={comms.decline}>
              <span className="t2-cm-bigbtn-dot">
                <Icon name="call_end" />
              </span>
              {tr("رفض")}
            </button>
            <button type="button" className="t2-cm-bigbtn accept" onClick={comms.answer}>
              <span className="t2-cm-bigbtn-dot">
                <Icon name="call" />
              </span>
              {tr("ردّ")}
            </button>
          </div>
        </div>
      ) : ongoing ? (
        <div className="t2-cm-controls">
          <div className="t2-cm-keys">
            <button
              type="button"
              className={call.muted ? "t2-cm-key on" : "t2-cm-key"}
              onClick={comms.toggleMute}
              aria-pressed={call.muted}
              disabled={call.stage === "preparing"}
            >
              <span className="t2-cm-key-dot">
                <Icon name={call.muted ? "mic_off" : "mic"} />
              </span>
              {tr("كتم")}
            </button>
            {/* **مكبّرُ الصوت حيث يختار المتصفّحُ المخرج وحدَه** (`speakerReady`) — وغيابُه في الغلاف مكتوبٌ في `lib/call-session` */}
            {call.speakerReady ? (
              <button
                type="button"
                className={call.speaker ? "t2-cm-key on" : "t2-cm-key"}
                onClick={comms.toggleSpeaker}
                aria-pressed={call.speaker}
              >
                <span className="t2-cm-key-dot">
                  <Icon name="volume_up" />
                </span>
                {tr("مكبّر الصوت")}
              </button>
            ) : null}
            <button type="button" className="t2-cm-key end" onClick={comms.hangUp}>
              <span className="t2-cm-key-dot">
                <Icon name="call_end" />
              </span>
              {tr("إنهاء")}
            </button>
          </div>
          {comms.canMessage ? (
            <button type="button" className="t2-cm-text" onClick={() => comms.openChat(call.rideId)}>
              <Icon name="chat" />
              {tr("رسالة")}
            </button>
          ) : null}
        </div>
      ) : (
        <div className="t2-cm-after">
          {failed ? (
            <>
              <button type="button" className="t2-button action t2-cm-wide" onClick={comms.messageInstead}>
                <Icon name="chat" />
                {tr("راسِله بدلاً من ذلك")}
              </button>
              {/* **بشروط «اتصال» نفسِها** (`canCall`) — مقبسٌ ساقطٌ أو ميكروفونٌ غائبٌ لا تُعاد عليه محاولة */}
              {comms.canCall ? (
                <button type="button" className="t2-button secondary t2-cm-wide" onClick={comms.retry}>
                  {tr("أعد المحاولة")}
                </button>
              ) : null}
            </>
          ) : null}
          {call.stage !== "hungup" ? (
            <button type="button" className="t2-cm-text" onClick={comms.dismissCall}>
              {tr("إغلاق")}
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}

/** **الشريطُ المصغَّر أعلى الشاشة** (§٦ البند ٤) — المدّةُ وزرُّ الإنهاء، ويُلمس فتعود الشاشةُ الكاملة. */
function CallStripT2({ call, peer, peerRole }: { call: CallView; peer: CommsPeer | null; peerRole: string }) {
  const comms = useComms()!;
  const elapsed = useElapsed(call.stage === "talking" ? call.since : null);
  return (
    <div className="t2 t2-cm-strip" role="status">
      <button type="button" className="t2-cm-strip-open" onClick={() => comms.minimize(false)}>
        <Icon name="call" fill />
        <span className="t2-cm-strip-name">{peer?.name ?? peerRole}</span>
        <span className="t2-cm-strip-time" dir={call.stage === "talking" ? "ltr" : undefined}>
          {stageLine(call, elapsed)}
        </span>
        {call.recording ? <span className="t2-cm-strip-rec">{tr("مسجَّلة")}</span> : null}
      </button>
      <button type="button" className="t2-cm-strip-end" onClick={comms.hangUp} aria-label={tr("إنهاء")}>
        <Icon name="call_end" />
      </button>
    </div>
  );
}
