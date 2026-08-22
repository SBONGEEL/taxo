/** صورةُ الراكب — **اختياريةٌ، بمعاينةٍ قبل الرفع، وبلا مراجعة**
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
 */

import { Camera, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import { clearMyPhoto, setMyPhoto } from "@/api/endpoints";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { describeShrink, shrinkImage } from "@/lib/shrink";
import { useSession } from "@/lib/session";
import { digits } from "@/lib/utils";

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
    <section className="card space-y-14 p-16">
      <div className="flex items-center gap-14">
        <span className="flex size-64 shrink-0 items-center justify-center overflow-hidden rounded-full border border-brand-brd bg-brand-soft text-26 font-bold text-brand">
          {shown ? (
            <img src={shown} alt="" className="size-full object-cover" />
          ) : (
            user?.name.slice(0, 1) ?? "؟"
          )}
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-medium text-ink">صورتي</p>
          <p className="mt-2 text-12 leading-relaxed text-muted">
            اختياريةٌ، ويراها كبتنُ رحلتك بعد قبوله طلبَك وحده — لا قبله، ولا
            يراها راكبٌ آخر. وتظهر فور رفعها.
          </p>
        </div>
      </div>

      {/* **حدُّ التطبيق يُقال ولا يُخفى**: لا بابَ يقرأ الصورةَ المرفوعةَ في
          شاشةِ الحساب، فالدائرةُ أعلاه حرفُ الاسم لا الصورة. وسكوتُنا عن ذلك
          يجعل من رفع صورتَه أمس يقرأ الحرفَ «حُذفت صورتي» */}
      {shown ? null : (
        <p className="text-11.5 leading-note text-muted">
          ما في الدائرة حرفُ اسمك لا صورتُك المرفوعة — وعرضُ الصورة الحالية في
          هذه الشاشة لم يُبنَ بعد. واختيارُ صورةٍ جديدةٍ يحلّ محلّ ما قبلها.
        </p>
      )}

      <input
        ref={picker}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(event) => {
          choose(event.target.files?.[0]);
          // **يُفرَّغ المدخل**: اختيارُ الملف نفسِه مرةً ثانيةً بعد إلغاءٍ لا
          // يُطلق `change` ما لم تُمسح القيمة
          event.target.value = "";
        }}
      />

      {uploading ? (
        <div className="space-y-8">
          <div className="flex items-baseline justify-between gap-8">
            <p className="text-13 text-muted">جارٍ رفع الصورة</p>
            <p className="text-13 font-semibold text-ink">
              {digits(String(progress))}٪
            </p>
          </div>
          <div
            className="h-6 w-full overflow-hidden rounded-6 bg-surface-2"
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="h-full rounded-6 bg-brand transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <Button variant="ghost" size="sm" onClick={() => abort.current?.abort()}>
            <X className="size-16" />
            أوقف الرفع
          </Button>
        </div>
      ) : picked ? (
        <div className="flex gap-8">
          <Button className="flex-1" onClick={() => void send(picked)}>
            ارفع هذه الصورة
          </Button>
          <Button variant="secondary" onClick={discard}>
            تراجع
          </Button>
        </div>
      ) : (
        <div className="flex gap-8">
          <Button
            variant="secondary"
            className="flex-1"
            onClick={() => picker.current?.click()}
          >
            <Camera className="size-16" />
            اختر صورة
          </Button>
          <Button
            variant="ghost"
            className="text-danger"
            disabled={busy !== null}
            onClick={() => setConfirmClear(true)}
          >
            <Trash2 className="size-16" />
            احذف
          </Button>
        </div>
      )}

      {/* **خطوةٌ ثانيةٌ للحذف**: الملفُّ يُمحى من القرص ولا يُستردّ، وضغطةٌ
          واحدةٌ على زرٍّ بجانب «اختر صورة» تقع بالخطأ */}
      {confirmClear ? (
        <div className="space-y-10 rounded-12 border border-danger bg-surface-2 p-12">
          <p className="text-13 text-ink">
            ستُحذف صورتك نهائياً، ويرى كبتنُ رحلتك حرفَ اسمك بدلاً منها.
          </p>
          <div className="flex gap-8">
            <Button
              variant="danger"
              size="sm"
              className="flex-1"
              loading={busy === "clear"}
              onClick={() => void remove()}
            >
              نعم، احذفها
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setConfirmClear(false)}
            >
              تراجع
            </Button>
          </div>
        </div>
      ) : null}

      {/* **الخطأُ يحمل زرّاً لا نصّاً وحدَه**: من انقطع رفعُه لا يجد المدخلَ
          مفتوحاً، وإعادةُ اختيار الصورة من المعرض خطواتٌ يفقد بينها الغرض */}
      <ErrorNote message={error} />
      {error && picked && !uploading ? (
        <Button variant="secondary" size="sm" onClick={() => void send(picked)}>
          أعد رفع الصورة نفسها
        </Button>
      ) : null}

      <SuccessNote message={done} />
      {shrunkNote ? (
        <p className="text-11.5 leading-note text-muted">{shrunkNote}</p>
      ) : null}
    </section>
  );
}
