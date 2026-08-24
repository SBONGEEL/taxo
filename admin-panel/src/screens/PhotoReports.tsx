/** بلاغاتُ صور الركاب — **الحجبُ وقع، والقرارُ هنا** (قرارُ المالك 2026-08-22).
 *
 * **وترتيبُ الأمرين هو المعنى**: الكبتنُ يبلّغ فتُحجب الصورةُ **في الحال** بلا
 * انتظارِ أحد — صورةٌ مسيئةٌ تبقى ساعةً حتى يستيقظ مشرفٌ أسوأُ من بلاغٍ كاذبٍ
 * يُعالَج بعد ساعة. فما ينتظر هنا ليس الحجبَ بل **الفصلَ فيه**.
 *
 * **وزرّان لا ثلاثة**: «أعِد» و«احذف». ولا «تجاهُل» — تجاهلُ بلاغٍ يترك الصورةَ
 * محجوبةً إلى الأبد بلا قرار، **وهو حذفٌ لا يقوله أحد**.
 *
 * **والصورةُ تُعرض هنا وحدَها**: `GET /admin/photo-reports/{id}/photo` هو
 * البابُ الوحيدُ الذي يراها وهي محجوبة — لأن **قراراً بلا رؤيةٍ تخمين**.
 *
 * **والاسمُ والرقمُ يظهران** كالخريطةِ الحيّة: قرارٌ على شخصٍ لا يُتّخذ على
 * معرّفٍ سُداسيٍّ عشريّ.
 */

import { useCallback, useEffect, useState } from "react";

import { photoReportBlob } from "@/api/endpoints";
import { listPhotoReports, resolvePhotoReport } from "@/api/endpoints";
import type { PhotoReport } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Shell } from "@/components/Shell";
import { moment } from "@/lib/format";

/** **الصورةُ تُجلب بالجلسة لا برابطٍ مكشوف**: `<img src>` لا يحمل ترويسةَ
 * تفويض، فتُقرأ إلى `blob:` ثم تُرسم — وبهذا لا يوجد عنوانٌ لصورةِ شخصٍ يعمل
 * بلا جلسةٍ لو نُسخ من شريط العنوان. */
function ReportedPhoto({ reportId }: { reportId: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null;
    let alive = true;
    (async () => {
      // **البابُ مُعلَنٌ في `endpoints.ts`** — ومسارٌ تكتبه شاشةٌ بيدها يقفز
      // فوق `check:contract`، فيبقى حيّاً بعد أن يتغيّر في الخلفية.
      try {
        url = await photoReportBlob(reportId);
      } catch {
        return;
      }
      if (alive) setSrc(url);
      else { URL.revokeObjectURL(url); url = null; }
    })();
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [reportId]);
  return (
    <div className="size-82 overflow-hidden rounded-13 bg-stripe-a">
      {src ? (
        <img src={src} alt="الصورةُ المبلَّغ عنها" className="size-full object-cover" />
      ) : null}
    </div>
  );
}

export function PhotoReports() {
  const [rows, setRows] = useState<PhotoReport[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await listPhotoReports());
    } catch (cause) {
      setError((cause as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const decide = async (row: PhotoReport, remove: boolean) => {
    setBusy(row.id);
    setError(null);
    setDone(null);
    try {
      await resolvePhotoReport(row.id, remove);
      setDone(remove ? "حُذفت الصورة." : "أُعيدت الصورة.");
      await load();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <Shell title="بلاغات الصور">
      {error ? <ErrorNote message={error} /> : null}
      {done ? <SuccessNote message={done} /> : null}
      {rows === null ? <Spinner /> : null}
      {rows !== null && rows.length === 0 ? (
        <p className="text-14 text-muted">لا بلاغاتٍ معلّقة.</p>
      ) : null}
      <div className="flex flex-col gap-12">
        {(rows ?? []).map((row) => (
          <div
            key={row.id}
            className="flex items-start gap-16 rounded-13 border border-line bg-surface p-16"
          >
            <ReportedPhoto reportId={row.id} />
            <div className="flex flex-1 flex-col gap-6">
              <p className="text-15 text-ink">{row.subject_name ?? "—"}</p>
              <p className="text-13 text-muted">{row.subject_phone ?? "—"}</p>
              <p className="text-13 text-muted">
                بلّغ: {row.reporter_name ?? "—"} · {moment(row.created_at)}
              </p>
              <div className="mt-8 flex gap-8">
                <Button
                  variant="ghost"
                  disabled={busy === row.id}
                  onClick={() => void decide(row, false)}
                >
                  أعِد الصورة
                </Button>
                <Button
                  variant="danger"
                  disabled={busy === row.id}
                  onClick={() => void decide(row, true)}
                >
                  احذفها
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Shell>
  );
}
