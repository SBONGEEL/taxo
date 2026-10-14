/** **«أرسل ملاحظة»** (SPEC §٧٦/٤) — نصٌّ وصورةُ شاشةٍ اختياريّة، **تصل صفحةَ «ملاحظات المستخدمين» في اللوحة** ومعها: مَن أرسل ·
 * أيُّ تطبيق · أيُّ إصدار · متى.
 *
 * **والصورةُ تُصغَّر على الجهاز قبل الرفع** (أطولُ ضلعٍ ١٦٠٠ بكسل، JPEG): لقطةُ شاشةٍ بدقّة الهاتف قد تبلغ ميغابايتات على شبكةٍ
 * بطيئة، **والقراءةُ لا تحتاج أكثر**. وإن تعذّر التصغيرُ تُرسل كما هي — **والخادمُ يقيس نوعَها من البايتات وحجمَها بالقراءة**.
 *
 * **والشاشةُ واحدةٌ في التطبيقين** (`FEEDBACK_APP` وحدَه يختلف) — ونسختاها تُحرَّران معاً.
 */

import { useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import { sendFeedback } from "@/api/endpoints";
import { useGoBack } from "@/lib/back";
import { clientInfo } from "@/lib/client-info";

import "@/taxo2";
import "./t2.css";
import "./feedback.css"; import { tr } from "@/lib/i18n";

const FEEDBACK_APP = "driver" as const;
const MAX_CHARS = 2000;
const MAX_SIDE = 1600;

/** يُصغّر الصورةَ إلى `MAX_SIDE` JPEG — **وأيُّ تعثّرٍ يعيد الأصل** لا يُسقط الإرسال. */
async function shrink(file: File): Promise<File> {
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
    if (!blob || blob.size >= file.size) return file;
    return new File([blob], "screenshot.jpg", { type: "image/jpeg" });
  } catch {
    return file;
  }
}

export function FeedbackT2Screen() {
  const goBack = useGoBack("/account");
  const [message, setMessage] = useState("");
  const [shot, setShot] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const picker = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!shot) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(shot);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [shot]);

  const busy = progress !== null;
  const ready = message.trim().length > 0 && !busy;

  const send = async () => {
    if (!ready) return;
    setError(null);
    setProgress(0);
    try {
      const info = await clientInfo();
      await sendFeedback(
        {
          app: FEEDBACK_APP,
          message: message.trim(),
          app_version: info.app_version,
          web_build: info.web_build,
          platform: info.platform,
          route: info.route,
        },
        shot ? await shrink(shot) : null,
        { onProgress: setProgress },
      );
      setSent(true);
      setMessage("");
      setShot(null);
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setError(caught instanceof ApiError ? caught.message : tr("تعذّر إرسالُ الملاحظة — أعد المحاولة"));
    } finally {
      setProgress(null);
    }
  };

  return (
    <div className="t2 t2-fb">
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label={tr("رجوع")} onClick={goBack}>
          <span className="t2-icon" aria-hidden="true">arrow_forward</span>
        </button>
        <h1 className="t2-title">{tr("أرسل ملاحظة")}</h1>
      </div>

      {sent ? (
        <div className="t2-fb-done" role="status">
          <span className="t2-icon" aria-hidden="true">check_circle</span>
          <p className="t2-fb-done-title">{tr("وصلت ملاحظتك — شكراً لك")}</p>
          <p className="t2-fb-lede">{tr("يقرؤها فريقُ TAXO ويعمل بها. يمكنك إرسالُ غيرها متى شئت.")}</p>
          <button type="button" className="t2-button secondary t2-fb-send" onClick={() => setSent(false)}>
            {tr("أرسل ملاحظةً أخرى")}
          </button>
        </div>
      ) : (
        <>
          <p className="t2-fb-lede">
            {tr("رأيُك أو خللٌ رأيتَه أو فكرةٌ تريدها — اكتبها هنا وتصل فريقَ TAXO مباشرة، ومعها إصدارُ التطبيق ليُعرف ما كنتَ تستعمل.")}
          </p>

          <textarea
            className="t2-input t2-fb-text"
            maxLength={MAX_CHARS}
            value={message}
            disabled={busy}
            onChange={(event) => setMessage(event.target.value)}
            placeholder={tr("ما الذي حدث؟ ما الذي توقّعتَه؟")}
            aria-label={tr("ملاحظتك")}
          />
          <p className="t2-fb-count" dir="ltr">
            {message.length}/{MAX_CHARS}
          </p>

          <div className="t2-fb-shot">
            <input
              ref={picker}
              type="file"
              accept="image/*"
              hidden
              onChange={(event) => {
                setShot(event.target.files?.[0] ?? null);
                event.target.value = "";
              }}
            />
            {preview ? (
              <>
                <img className="t2-fb-thumb" src={preview} alt={tr("صورة الشاشة المرفقة")} />
                <button type="button" className="t2-button secondary t2-fb-pick" disabled={busy} onClick={() => setShot(null)}>
                  {tr("أزل الصورة")}
                </button>
              </>
            ) : (
              <button type="button" className="t2-button secondary t2-fb-pick" disabled={busy} onClick={() => picker.current?.click()}>
                <span className="t2-icon" aria-hidden="true">add_photo_alternate</span>
                {tr("أرفق صورة شاشة (اختياري)")}
              </button>
            )}
          </div>

          {error ? (
            <p className="t2-note danger" role="alert">
              <span className="t2-icon" aria-hidden="true">error</span>
              {error}
            </p>
          ) : null}

          <button type="button" className="t2-button primary t2-fb-send" disabled={!ready} onClick={() => void send()}>
            {busy ? tr("يُرسل… {0}٪", { 0: progress ?? 0 }) : tr("أرسل")}
          </button>
        </>
      )}
    </div>
  );
}
