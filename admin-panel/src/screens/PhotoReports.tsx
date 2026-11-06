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
 *
 * **وبلغة TAXO 2.0** (A08): كلُّ بلاغٍ بطاقةٌ — الصورةُ ١١٢ إلى جانب الاسم والرقم ومن بلّغ — **والزرّان كما كانا**:
 * «أعِد» ثانويٌّ و«احذف» بلون الخطر، **بلا تأكيدٍ يُضاف** (لم يكن قبلُ).
 */

import { useCallback, useEffect, useState } from "react";

import { photoReportBlob } from "@/api/endpoints";
import { listPhotoReports, resolvePhotoReport } from "@/api/endpoints";
import type { PhotoReport } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Shell } from "@/components/Shell";
import { MediaViewer, useMediaCache } from "@/components/ui/MediaViewer";
import { moment } from "@/lib/format";
import { Icon } from "@/taxo2";

/** **الصورةُ تُجلب بالجلسة لا برابطٍ مكشوف**: `<img src>` لا يحمل ترويسةَ
 * تفويض، فتُقرأ إلى `blob:` ثم تُرسم — وبهذا لا يوجد عنوانٌ لصورةِ شخصٍ يعمل
 * بلا جلسةٍ لو نُسخ من شريط العنوان. */
function ReportedPhoto({ reportId }: { reportId: string }) {
  const [src, setSrc] = useState<string | null>(null);
  // **وتُفتح في العارض** (البند ٠): قرارٌ على صورةِ شخصٍ يُتّخذ عليها مكبَّرةً لا على مربّعٍ بعرض ١١٢
  const media = useMediaCache();
  const [viewing, setViewing] = useState(false);
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
    <div className="ad-report-photo">
      {/* **ما لم تصل الصورةُ فمكانُها رسمُ شخص** — لا بياضٌ يُقرأ «لا صورة» */}
      {src ? (
        <button type="button" className="ad-mv-plain" onClick={() => setViewing(true)} aria-label="اعرض الصورة ملءَ الشاشة">
          <img src={src} alt="الصورةُ المبلَّغ عنها" />
        </button>
      ) : (
        <Icon name="person" />
      )}
      {viewing && src ? (
        <MediaViewer
          cache={media}
          items={[{ key: reportId, label: "الصورةُ المبلَّغ عنها", load: () => Promise.resolve({ url: src, type: "image/jpeg" }) }]}
          index={0}
          onIndex={() => undefined}
          onClose={() => setViewing(false)}
        />
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
      <div className="ad-reports-page">
        <ErrorNote message={error} />
        <SuccessNote message={done} />
        {rows === null ? (
          <div className="ad-sec-loading">
            <Spinner />
          </div>
        ) : null}
        {rows !== null && rows.length === 0 ? (
          <div className="ad-reports-empty">
            <p className="ad-empty-title">لا بلاغاتٍ معلّقة.</p>
          </div>
        ) : null}
        {rows !== null && rows.length > 0 ? (
          <div className="ad-reports">
            {rows.map((row) => (
              <article key={row.id} className="ad-report">
                <ReportedPhoto reportId={row.id} />
                <div className="ad-report-body">
                  <p className="ad-report-name">{row.subject_name ?? "—"}</p>
                  {/* الرقمُ مُعرّفٌ يُقارَن حرفاً بحرف — من اليسار، كالخريطة الحيّة */}
                  <p dir="ltr" className="ad-report-line ad-ltr">
                    {row.subject_phone ?? "—"}
                  </p>
                  <p className="ad-report-line">
                    بلّغ: {row.reporter_name ?? "—"} · {moment(row.created_at)}
                  </p>
                  <div className="ad-report-actions">
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={busy === row.id}
                      onClick={() => void decide(row, false)}
                    >
                      أعِد الصورة
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      disabled={busy === row.id}
                      onClick={() => void decide(row, true)}
                    >
                      احذفها
                    </Button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </div>
    </Shell>
  );
}
