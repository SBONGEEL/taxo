/** **مراجعةُ الخريطة** (أمرُ المالك ٢٠٢٦-١١-١٨ السابع، المهمّتان ٢-٣ و٣-٣): اقتراحاتُ «أضف مكاناً / اقترح تصحيحاً» من الركّاب،
 *  وبلاغاتُ الطريق من الكباتن. **الاقتراحُ لا يظهر على الخريطة إلا بموافقةٍ من هنا** (فيصير مكاناً بمصدر «مجتمع» في «الأماكن»)،
 *  **والبلاغُ يظهر بتأكيد كبتنٍ ثانٍ أو بموافقةٍ من هنا**، ويُزال من هنا — حالٌ لا محو. وتتبع مبدّلَ الدولة. */
import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  approveMapSuggestion,
  listMapSuggestions,
  listRoadReports,
  rejectMapSuggestion,
  approveRoadReport,
  removeRoadReport,
} from "@/api/endpoints";
import type { MapSuggestion, RoadReportRow } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Table } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { useCountry } from "@/lib/country";
import { day } from "@/lib/format";
import { useSession } from "@/lib/session";

const REPORT_LABEL: Record<string, string> = { works: "صيانة", closed: "طريق مغلق", accident: "حادث", jam: "ازدحام" };
const KIND_LABEL: Record<string, string> = { add: "مكانٌ جديد", fix: "تصحيح" };
const mapLink = (lat: number, lng: number) => `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=18/${lat}/${lng}`;

export function MapReviewScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();
  const [suggestions, setSuggestions] = useState<MapSuggestion[] | null>(null);
  const [reports, setReports] = useState<RoadReportRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<MapSuggestion | null>(null);
  const [reason, setReason] = useState("");

  const load = useCallback(async () => {
    const [s, r] = await Promise.all([listMapSuggestions(country), listRoadReports(country)]);
    setSuggestions(s);
    setReports(r);
  }, [country]);

  useEffect(() => {
    setSuggestions(null);
    setReports(null);
    setError(null);
    load().catch((caught) => setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة طابور المراجعة"));
  }, [load]);

  async function act(run: () => Promise<unknown>, message: string) {
    setError(null);
    setDone(null);
    try {
      await run();
      setDone(message);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    }
  }

  return (
    <Shell title="مراجعة الخريطة" subtitle="ما يقترحه الركّابُ من أماكن، وما يبلّغ به الكباتنُ عن الطرق — لا يظهر اقتراحٌ قبل موافقتك">
      <ErrorNote message={error} />
      <SuccessNote message={done} />

      <h2 className="mb-4 mt-2 text-14 font-bold text-ink">اقتراحات الأماكن</h2>
      <Table
        columns="1.4fr 0.8fr 0.8fr 1.2fr 1fr 0.8fr auto"
        headers={["الاسم المقترح", "النوع", "الفئة", "الاسم الحاليّ / ملاحظة", "الموقع", "التاريخ", ""]}
        rows={suggestions}
        keyOf={(row) => row.id}
        height="auto"
        empty={{ title: "لا اقتراحات قيد المراجعة", hint: "تصل هنا من زرّ «أضف مكاناً» و«اقترح تصحيحاً» في تطبيق الراكب حين يُشعَل مفتاحُهما." }}
        render={(row) => (
          <>
            <span className="ad-fac-name">{row.name_ar}</span>
            <Badge tone={row.kind === "fix" ? "warn" : "ink"}>{KIND_LABEL[row.kind] ?? row.kind}</Badge>
            <span className="ad-tone-muted">{row.category}</span>
            <span className="ad-tone-muted">{[row.current_name, row.note].filter(Boolean).join(" · ") || "—"}</span>
            <a href={mapLink(row.lat, row.lng)} target="_blank" rel="noreferrer" dir="ltr">
              {row.lat.toFixed(5)}, {row.lng.toFixed(5)}
            </a>
            <span className="ad-tone-muted">{day(row.created_at)}</span>
            {isAdmin ? (
              <span className="flex gap-2">
                <Button size="sm" className="w-auto" onClick={() => void act(() => approveMapSuggestion(row.id), "وُوفق عليه وصار مكاناً على الخريطة")}>
                  وافق
                </Button>
                <Button size="sm" variant="secondary" className="w-auto" onClick={() => { setRejecting(row); setReason(""); }}>
                  ارفض
                </Button>
              </span>
            ) : (
              <span />
            )}
          </>
        )}
      />

      <h2 className="mb-4 mt-6 text-14 font-bold text-ink">بلاغات الطريق النشطة</h2>
      <Table
        columns="0.9fr 0.7fr 0.8fr 1.1fr 0.9fr auto"
        headers={["البلاغ", "التأكيدات", "الحال", "الموقع", "ينتهي", ""]}
        rows={reports}
        keyOf={(row) => row.id}
        height="auto"
        empty={{ title: "لا بلاغاتٍ نشطة", hint: "يبلّغ الكابتنُ من خريطته بلمسة، ويظهر البلاغُ بتأكيد كابتنٍ ثانٍ أو بموافقتك." }}
        render={(row) => {
          const shown = row.approved || row.confirmations >= 2;
          return (
            <>
              <span className="ad-fac-name">{REPORT_LABEL[row.kind] ?? row.kind}</span>
              <span dir="ltr">{row.confirmations}</span>
              <Badge tone={shown ? "ok" : "muted"}>{shown ? "ظاهر" : "ينتظر تأكيداً"}</Badge>
              <a href={mapLink(row.lat, row.lng)} target="_blank" rel="noreferrer" dir="ltr">
                {row.lat.toFixed(5)}, {row.lng.toFixed(5)}
              </a>
              <span className="ad-tone-muted">{day(row.expires_at)}</span>
              {isAdmin ? (
                <span className="flex gap-2">
                  {!row.approved ? (
                    <Button size="sm" className="w-auto" onClick={() => void act(() => approveRoadReport(row.id), "صار البلاغُ ظاهراً")}>
                      أظهر
                    </Button>
                  ) : null}
                  <Button size="sm" variant="secondary" className="w-auto" onClick={() => void act(() => removeRoadReport(row.id), "أُزيل البلاغ")}>
                    أزل
                  </Button>
                </span>
              ) : (
                <span />
              )}
            </>
          );
        }}
      />

      {rejecting ? (
        <Modal title={`رفض «${rejecting.name_ar}»`} onClose={() => setRejecting(null)}>
          <Field label="السبب" value={reason} onChange={(event) => setReason(event.target.value)} maxLength={300} />
          <Button
            disabled={reason.trim().length < 2}
            onClick={() => {
              const row = rejecting;
              setRejecting(null);
              void act(() => rejectMapSuggestion(row.id, reason.trim()), "رُفض الاقتراح");
            }}
          >
            ارفض
          </Button>
        </Modal>
      ) : null}
    </Shell>
  );
}
