/** **صورةُ الراكب — يراها كبتنُ الرحلة بعد القبول** (البند ٥٢، 2026-08-22).
 *
 * **ولا منطقَ «هل له صورة» هنا إطلاقاً**: البابُ يردّ **٢٠٠ بصورةٍ دائماً**
 * — الحقيقيةَ لمن رُوجعت، وحرفَ اسمه مرسوماً في الخادم لمن سواه — **بطولٍ
 * ثابتٍ بالبايت ونوعٍ ثابت**. فحقلٌ أو شرطٌ في التطبيق يقول «له صورة» يعيد
 * الوشايةَ التي أُغلقت في الخادم من بابٍ آخر: من لا صورةَ له يُعرف بغيابها.
 *
 * **ومفتاحُه الرحلةُ لا المستخدم**: لا يُستعرض وجهُ أحدٍ بعدِّ المعرّفات.
 *
 * **والبلاغُ يُخفيها في الحال ويعرضها على المشرف** — والحجبُ قبل القرار لا
 * بعده: الضررُ يقع في الدقائق. **وبلاغٌ واحدٌ يكفي** (صورةٌ لا تصويت).
 *
 * **وضغطتان لا واحدة**: البلاغُ يُسجَّل على حساب إنسان، وزرٌّ يُضغط سهواً
 * على شاشةٍ يقودها كبتنٌ بيدٍ واحدة يحجب صورةَ بريءٍ ويستدعي مشرفاً. فالصورةُ
 * تُفتح أولاً، ثم يُطلب البلاغ، ثم يُؤكَّد بنصٍّ يقول ما سيقع.
 */

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";

import { ApiError, api } from "@/api/client";
import { reportRiderPhoto } from "@/api/endpoints";
import { ErrorNote } from "@/components/ui/Feedback";
import { cn } from "@/lib/utils";

export function RiderAvatar({
  rideId,
  className,
}: {
  rideId: string;
  className?: string;
}) {
  const [src, setSrc] = useState<string | null>(null);
  // **يُعاد التحميلُ بعد البلاغ**: البابُ نفسُه يردّ عندها الحرفَ المرسوم،
  // فلا تحتاج الشاشةُ أن تعرف ما صار — تسأل ثانيةً وتعرض ما وصل
  const [round, setRound] = useState(0);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    api
      .blob(`/rides/${rideId}/rider/photo`)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      // شبكةٌ تعثّرت — تُرسم دائرةٌ فارغةٌ ولا يُقال شيء: هذه حالُ اتصالٍ لا
      // خبرٌ عن صاحب الصورة
      .catch(() => undefined);

    return () => {
      cancelled = true;
      // **ويُحرَّر العنوان**: `createObjectURL` يحجز الصورةَ في الذاكرة حتى
      // يُلغى، ورحلةٌ تُفتح عشرَ مراتٍ تحجز عشرَ نسخ
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [rideId, round]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="صورة الراكب"
        className={cn(
          "pressable flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-line bg-surface-2",
          className,
        )}
      >
        {src ? (
          <img src={src} alt="" className="size-full object-cover" />
        ) : null}
      </button>

      {open ? (
        <RiderPhotoSheet
          rideId={rideId}
          src={src}
          onReported={() => setRound((value) => value + 1)}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </>
  );
}

function RiderPhotoSheet({
  rideId,
  src,
  onReported,
  onClose,
}: {
  rideId: string;
  src: string | null;
  onReported: () => void;
  onClose: () => void;
}) {
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const report = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await reportRiderPhoto(rideId);
      onReported();
      onClose();
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر إرسال البلاغ",
      );
    } finally {
      setBusy(false);
    }
  }, [rideId, onReported, onClose]);

  return (
    <div
      className="absolute inset-0 z-50 animate-fadein-fast bg-dim"
      onClick={onClose}
    >
      <div
        className="absolute inset-x-0 bottom-0 animate-slideup rounded-t-24 border-t border-line bg-surface px-18 pb-24 pt-20"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="mb-12 text-16 font-bold text-ink">صورة الراكب</h2>

        <div className="mx-auto mb-14 size-150 overflow-hidden rounded-18 border border-line bg-surface-2">
          {src ? (
            <img src={src} alt="" className="size-full object-cover" />
          ) : null}
        </div>

        <ErrorNote message={error} />

        {asking ? (
          <>
            {/* **النصُّ يقول ما سيقع بالضبط** — لا «هل أنت متأكد؟»: من يقرأ
                سؤالاً عامّاً يضغط «نعم» بلا قراءة، ومن يقرأ الأثرَ يتأمّل */}
            <p className="mb-12 mt-6 rounded-14 border border-line bg-surface-2 px-14 py-11 text-11.5 leading-note text-warn">
              ستُحجب صورةُ هذا الراكب فوراً عن الجميع، ويُعرض البلاغُ على
              مشرفٍ يفصل فيه. ولا يُلغى البلاغُ بعد إرساله.
            </p>
            <div className="flex flex-col gap-9">
              <button
                type="button"
                disabled={busy}
                onClick={() => void report()}
                className="pressable w-full rounded-16 bg-danger p-15 text-center text-14 font-bold text-white disabled:opacity-50"
              >
                {busy ? "…" : "تأكيد البلاغ"}
              </button>
              <button
                type="button"
                onClick={() => setAsking(false)}
                className="pressable w-full py-8 text-center text-12.5 font-semibold text-muted"
              >
                تراجع
              </button>
            </div>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={() => setAsking(true)}
              className="pressable flex w-full items-center justify-center gap-8 rounded-16 border border-line p-14 text-13.5 font-semibold text-danger"
            >
              <AlertTriangle size={16} />
              بلّغ عن هذه الصورة
            </button>
            <button
              type="button"
              onClick={onClose}
              className="pressable mt-9 w-full py-8 text-center text-12.5 font-semibold text-muted"
            >
              إغلاق
            </button>
          </>
        )}
      </div>
    </div>
  );
}
