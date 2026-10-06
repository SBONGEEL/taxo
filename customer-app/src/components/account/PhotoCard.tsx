/** بطاقةُ الهوية والصورة — TAXO 2.0 «R22» (`design/t2-new/rider/R22-profile.dc.html`): **الدائرةُ هي الصورة** — المختارةُ
 *  أو المرفوعةُ في هذه الجلسة، وإلا الحرفُ الأوّل كما في R15 — وبجانبها الاسمُ والرقم، ثمّ البريدُ المُثبَت، ثمّ «صورتي» وأفعالُها.
 *
 * **والصورةُ اختياريةٌ، بمعاينةٍ قبل الرفع، وبلا مراجعة**
 *  (قرارُ المالك 2026-08-22، `PUT`/`DELETE /auth/me/photo`).
 *
 * **ولا تُكتب هنا كلمةٌ توحي بانتظار موافقة**: البابُ يَنشر فور الرفع، وشاشةٌ
 * تقول «قيد المراجعة» عن شيءٍ لا يُراجَع تجعل صاحبَها ينتظر ما وقع أصلاً.
 *
 * **والرفعُ بلا مهلةٍ يلزمه ثلاثة** (SPEC ١٧.٦): **نسبةٌ** تقول «يتقدّم»،
 * **وزرُّ إلغاءٍ** يقول «تستطيع الخروج»، **وكاشفُ ركود** — والثالثُ ليس
 * تكراراً للثاني: الإلغاءُ يعالج من قرّر التوقّف، والركودُ يعالج **وصلةً
 * ماتت صامتة** فيقف الشريطُ بلا حدثٍ ولا رسالة. وهما يمرّان بنفس الحدث
 * ويُفرَّقان: قطعُ الركود خطأٌ يُعرض ومعه **زرٌّ يحمل الملفَّ نفسَه**، وقطعُ
 * صاحبه قرارُه هو فلا يُعرض له شيء.
 *
 * **ولا منطقَ «هل له صورة» في التطبيق**: البابُ الذي يعرضها للكبتن يردّ
 * ٢٠٠ بصورةٍ دائماً بطولٍ ثابت — والغيابُ المرئيُّ نفسُه وشاية (الشكلُ
 * الثالثَ عشر). فلا تُرسم هنا حالٌ اسمُها «لا صورةَ لك» ولا يُقاس عليها شيء.
 *
 * **والاسمُ والرقمُ والبريدُ هنا لا في الشاشة** لأن الدائرةَ بجانبها هي الصورةُ نفسُها — فلا تُرسم دائرتان لشخصٍ واحد.
 * **والرقمُ لا يُحرَّر ولا يُعرَّب** — معرَّفٌ يُقارَن ويُملى؛ **والبريدُ يُعرض ولا يُحرَّر** (قرارُ المالك 2026-08-31): تغييرُ
 * بريدٍ مُثبَتٍ يحتاج إثباتَ الجديد، و`null` تعني لا بريدَ مُثبَت فلا يُرسم سطرٌ فارغ.
 */

import { useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import { clearMyPhoto, setMyPhoto } from "@/api/endpoints";
import { NoteT2 } from "@/screens/t2/KitT2";
import { describeShrink, shrinkImage } from "@/lib/shrink";
import { useSession } from "@/lib/session";
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

/** ما يُقبل من المعرض أو الكاميرا — والخلفيةُ تقرأ النوعَ من البايتات لا من هذا. */
const ACCEPT = "image/*";

export function PhotoCard() {
  const { user, refreshUser } = useSession();
  const picker = useRef<HTMLInputElement>(null);
  const abort = useRef<AbortController | null>(null);

  /** الملفُّ المختار **قبل** الرفع — وجودُه هو حالُ المعاينة. */
  const [picked, setPicked] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  /** آخرُ ما رُفع في هذه الجلسة — يُعرض فيرى صاحبُه أن الرفعَ وقع فعلاً. */
  const [uploadedUrl, setUploadedUrl] = useState<string | null>(null);

  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState<"upload" | "clear" | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [shrunkNote, setShrunkNote] = useState<string | null>(null);

  // **يُحرَّر العنوان**: `createObjectURL` يحجز الصورةَ في الذاكرة حتى يُلغى،
  // وشاشةٌ تُفتح عشرَ مراتٍ تحجز عشرَ نسخ
  useEffect(() => {
    if (!previewUrl) return;
    return () => URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);
  useEffect(() => {
    if (!uploadedUrl) return;
    return () => URL.revokeObjectURL(uploadedUrl);
  }, [uploadedUrl]);

  function choose(file: File | undefined) {
    if (!file) return;
    setError(null);
    setDone(null);
    setShrunkNote(null);
    setPicked(file);
    setPreviewUrl(URL.createObjectURL(file));
  }

  function discard() {
    setPicked(null);
    setPreviewUrl(null);
    setError(null);
  }

  async function send(file: File) {
    setBusy("upload");
    setProgress(0);
    setError(null);
    setDone(null);
    const controller = new AbortController();
    abort.current = controller;
    try {
      // **تُضغط قبل أن تخرج** (`lib/shrink.ts`): كلُّ بابٍ يعرضها في الخلفية
      // يُنزلها إلى ٢٥٦ بكسل، فما فوق ذلك بايتاتٌ تُرفع ثم تُرمى
      const shrunk = await shrinkImage(file);
      await setMyPhoto(shrunk.file, {
        onProgress: setProgress,
        signal: controller.signal,
      });
      await refreshUser();
      // **يُقال بعد نجاح الرفع لا قبله**: سطرٌ يعلن التصغير ثم يفشل الرفعُ
      // يترك صاحبَه يظنّ أن صورتَه ذهبت مصغَّرةً وهي لم تذهب أصلاً
      setShrunkNote(describeShrink(shrunk));
      setUploadedUrl(URL.createObjectURL(shrunk.file));
      setPicked(null);
      setPreviewUrl(null);
      setDone("رُفعت صورتك، وهي ظاهرةٌ الآن لكبتن رحلتك.");
    } catch (caught) {
      // من ألغى يعرف أنه ألغى — ورسالةٌ حمراءُ بعده تجعله يظنّ شيئاً انكسر
      if ((caught as Error)?.name === "AbortError") return;
      // **النصُّ من الخلفية** (§17): لا تخترع الواجهةُ عربيةً لخطأٍ سمّته
      setError(caught instanceof ApiError ? caught.message : "تعذّر رفع الصورة");
    } finally {
      abort.current = null;
      setBusy(null);
      setProgress(0);
    }
  }

  async function remove() {
    setBusy("clear");
    setError(null);
    setDone(null);
    try {
      await clearMyPhoto();
      await refreshUser();
      setUploadedUrl(null);
      setShrunkNote(null);
      setDone("حُذفت صورتك.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر حذف الصورة");
    } finally {
      setBusy(null);
      setConfirmClear(false);
    }
  }

  const shown = previewUrl ?? uploadedUrl;
  const uploading = busy === "upload";

  return (
    <section className="t2-idcard">
      <div className="t2-idcard-top">
        {/* الدائرةُ بلغة R15 — **برقوقيّةٌ في السِمة الوردية** (`t2.css`) */}
        <span className="t2-avatar">{shown ? <img src={shown} alt="" /> : (user?.name.slice(0, 1) ?? "؟")}</span>
        <div className="t2-prof-main">
          <div className="t2-prof-name">{user?.name}</div>
          <div dir="ltr" className="t2-prof-phone">
            {user?.phone}
          </div>
        </div>
      </div>

      {user?.email ? (
        <div className="t2-idcard-sec">
          <p className="t2-idcard-label">البريد المُثبَت</p>
          <p dir="ltr" className="t2-idcard-email">
            {user.email}
          </p>
        </div>
      ) : null}

      <div className="t2-idcard-sec">
        <p className="t2-idcard-title">صورتي</p>
        <p className="t2-idcard-body">
          اختياريةٌ، ويراها كبتنُ رحلتك بعد قبوله طلبَك وحده — لا قبله، ولا يراها راكبٌ آخر. وتظهر فور رفعها.
        </p>

        {/* **حدُّ التطبيق يُقال ولا يُخفى**: لا بابَ يقرأ الصورةَ المرفوعةَ في
            شاشةِ الحساب، فالدائرةُ أعلاه حرفُ الاسم لا الصورة. وسكوتُنا عن ذلك
            يجعل من رفع صورتَه أمس يقرأ الحرفَ «حُذفت صورتي» */}
        {shown ? null : (
          <p className="t2-idcard-note">
            ما في الدائرة حرفُ اسمك لا صورتُك المرفوعة — وعرضُ الصورة الحالية في هذه الشاشة لم يُبنَ بعد. واختيارُ صورةٍ
            جديدةٍ يحلّ محلّ ما قبلها.
          </p>
        )}

        <input
          ref={picker}
          type="file"
          accept={ACCEPT}
          className="t2-idcard-file"
          aria-label="اختر صورة"
          onChange={(event) => {
            choose(event.target.files?.[0]);
            // **يُفرَّغ المدخل**: اختيارُ الملف نفسِه مرةً ثانيةً بعد إلغاءٍ لا
            // يُطلق `change` ما لم تُمسح القيمة
            event.target.value = "";
          }}
        />

        {uploading ? (
          <div className="t2-idcard-progress">
            <div className="t2-idcard-progress-top">
              <span>جارٍ رفع الصورة</span>
              <span dir="ltr" className="t2-num">
                {digits(String(progress))}%
              </span>
            </div>
            <div
              className="t2-idcard-bar"
              role="progressbar"
              aria-label="جارٍ رفع الصورة"
              aria-valuenow={progress}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <span style={{ width: `${progress}%` }} />
            </div>
            <button type="button" className="t2-cbtn soft full" onClick={() => abort.current?.abort()}>
              <Icon name="close" />
              أوقف الرفع
            </button>
          </div>
        ) : picked ? (
          <div className="t2-idcard-row">
            <button type="button" className="t2-cbtn ink grow" onClick={() => void send(picked)}>
              ارفع هذه الصورة
            </button>
            <button type="button" className="t2-cbtn soft" onClick={discard}>
              تراجع
            </button>
          </div>
        ) : (
          <div className="t2-idcard-row">
            <button type="button" className="t2-cbtn soft grow" onClick={() => picker.current?.click()}>
              <Icon name="photo_camera" />
              اختر صورة
            </button>
            <button
              type="button"
              className="t2-cbtn destroy-text"
              disabled={busy !== null}
              onClick={() => setConfirmClear(true)}
            >
              <Icon name="delete" />
              احذف
            </button>
          </div>
        )}

        {/* **خطوةٌ ثانيةٌ للحذف**: الملفُّ يُمحى من القرص ولا يُستردّ، وضغطةٌ
            واحدةٌ على زرٍّ بجانب «اختر صورة» تقع بالخطأ */}
        {confirmClear ? (
          <div className="t2-idcard-confirm">
            <p>ستُحذف صورتك نهائياً، ويرى كبتنُ رحلتك حرفَ اسمك بدلاً منها.</p>
            <div className="t2-idcard-row">
              <button
                type="button"
                className="t2-cbtn destroy grow"
                disabled={busy === "clear"}
                aria-busy={busy === "clear"}
                onClick={() => void remove()}
              >
                نعم، احذفها
              </button>
              <button type="button" className="t2-cbtn soft" onClick={() => setConfirmClear(false)}>
                تراجع
              </button>
            </div>
          </div>
        ) : null}

        {/* **الخطأُ يحمل زرّاً لا نصّاً وحدَه**: من انقطع رفعُه لا يجد المدخلَ
            مفتوحاً، وإعادةُ اختيار الصورة من المعرض خطواتٌ يفقد بينها الغرض */}
        {error ? <NoteT2 tone="danger">{error}</NoteT2> : null}
        {error && picked && !uploading ? (
          <div className="t2-idcard-row">
            <button type="button" className="t2-cbtn soft full" onClick={() => void send(picked)}>
              أعد رفع الصورة نفسها
            </button>
          </div>
        ) : null}

        {done ? <NoteT2 tone="ok">{done}</NoteT2> : null}
        {shrunkNote ? <p className="t2-idcard-note">{shrunkNote}</p> : null}
      </div>
    </section>
  );
}
