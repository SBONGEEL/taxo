/** **الطوارئ** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٧) — كلُّ ضغطةٍ على زرّ الطوارئ في التطبيقين.
 *
 * **كلُّ بطاقةٍ تجيب**: مَن ضغط وبأيِّ صفة · الطرفان بالاسم والرقم (للاتّصال المباشر) · السيارةُ واللوحة · من أين وإلى أين ·
 * **أين ضُغط، وأين السيارةُ الآن** (يُحدَّث كلَّ عشر ثوانٍ). **و«عولجت» بملاحظةٍ إلزاميّة** — ما فُعل يُكتب في التدقيق.
 *
 * **وأرقامُ التواصل لكلِّ دولة** أسفلَ الصفحة: رقمُ الطوارئ الذي يتّصل به الزرُّ، وواتسابُ «تواصل معنا» (البند ٨).
 */

import { useCallback, useEffect, useState } from "react";

import { getSupportSettings, handleEmergency, listEmergencies, saveSupportSettings } from "@/api/endpoints";
import type { CountryCode, EmergencyRow } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Segmented } from "@/components/ui/Segmented";
import { moment } from "@/lib/format";

type EmergencyFilter = "open" | "handled" | "all";

const ROLE_LABEL: Record<string, string> = { rider: "الراكب", driver: "الكبتن" };
const COUNTRY_LABEL: Record<string, string> = { JO: "الأردن", DZ: "الجزائر" };

function mapLink(lat: number, lng: number): string {
  return `https://www.google.com/maps?q=${lat},${lng}`;
}

function Person({ label, name, phone }: { label: string; name: string; phone: string | null }) {
  return (
    <p className="ad-report-line">
      {label}: <span className="font-semibold text-ink">{name}</span>{" "}
      {phone ? (
        <a dir="ltr" className="ad-ltr underline" href={`tel:${phone}`}>
          {phone}
        </a>
      ) : null}
    </p>
  );
}

function HandleForm({ row, onDone }: { row: EmergencyRow; onDone: () => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await handleEmergency(row.id, note.trim());
      onDone();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="mt-8 flex flex-col gap-8">
      <Field
        label="ما فُعل (إلزاميّ)"
        value={note}
        placeholder="اتّصلنا بالراكب وهو بخير…"
        onChange={(event) => setNote(event.target.value)}
      />
      <ErrorNote message={error} />
      <div>
        <Button size="sm" disabled={busy || note.trim().length < 3} onClick={() => void submit()}>
          عولجت
        </Button>
      </div>
    </div>
  );
}

function ContactsCard() {
  const [country, setCountry] = useState<CountryCode>("JO");
  const [emergency, setEmergency] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    setDone(null);
    getSupportSettings(country)
      .then((row) => {
        setEmergency(row.emergency_number ?? "");
        setWhatsapp(row.whatsapp_number ?? "");
      })
      .catch((cause) => setError((cause as Error).message));
  }, [country]);

  const save = async () => {
    setError(null);
    setDone(null);
    try {
      const row = await saveSupportSettings(country, {
        emergency_number: emergency.trim() || null,
        whatsapp_number: whatsapp.trim() || null,
      });
      setEmergency(row.emergency_number ?? "");
      setWhatsapp(row.whatsapp_number ?? "");
      setDone("حُفظ — يصل التطبيقين في الحال.");
    } catch (cause) {
      setError((cause as Error).message);
    }
  };

  return (
    <section className="card mt-16 flex flex-col gap-10 p-16" aria-labelledby="contacts-title">
      <div className="flex flex-wrap items-end justify-between gap-12">
        <div>
          <h2 id="contacts-title" className="text-15 font-bold text-ink">
            أرقام التواصل لكلِّ دولة
          </h2>
          <p className="text-12 text-muted">
            <b>رقمُ الطوارئ</b> يتّصل به زرُّ الطوارئ في التطبيقين مباشرةً (الافتراضيّ الرسميّ: الأردن 911 · الجزائر 17 — الشرطة؛ والحمايةُ
            المدنيّة 14). <b>رقمُ واتساب الدعم</b> يظهر زرّاً في «تواصل معنا»؛ فارغاً يختفي الزرّ. يُكتب بالصيغة الدوليّة: 9627… أو 213….
          </p>
        </div>
        <Segmented
          label="الدولة"
          value={country}
          onPick={(key) => setCountry(key as CountryCode)}
          options={[
            { key: "JO", label: "الأردن" },
            { key: "DZ", label: "الجزائر" },
          ]}
        />
      </div>
      <div className="grid gap-10 sm:grid-cols-2">
        <Field label="رقم الطوارئ" dir="ltr" value={emergency} onChange={(event) => setEmergency(event.target.value)} />
        <Field
          label="واتساب الدعم"
          dir="ltr"
          value={whatsapp}
          placeholder="9627XXXXXXXX"
          onChange={(event) => setWhatsapp(event.target.value)}
        />
      </div>
      <ErrorNote message={error} />
      <SuccessNote message={done} />
      <div>
        <Button size="sm" onClick={() => void save()}>
          حفظ
        </Button>
      </div>
    </section>
  );
}

export function EmergenciesScreen() {
  const [status, setStatus] = useState<EmergencyFilter>("open");
  const [rows, setRows] = useState<EmergencyRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await listEmergencies(status));
      setError(null);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }, [status]);

  useEffect(() => {
    setRows(null);
    void load();
    // **الموقعُ الحيُّ يتحرّك** — كلَّ عشر ثوانٍ ما دامت الصفحةُ مفتوحة
    const timer = window.setInterval(() => void load(), 10_000);
    return () => window.clearInterval(timer);
  }, [load]);

  const open = (rows ?? []).filter((row) => row.status === "open").length;

  return (
    <Shell
      title="الطوارئ"
      subtitle={`ضغطاتُ زرّ الطوارئ من الركّاب والكباتن — المفتوحةُ ${open}`}
      actions={
        <Segmented
          label="الحال"
          value={status}
          onPick={(key) => setStatus(key as EmergencyFilter)}
          options={[
            { key: "open", label: "مفتوحة" },
            { key: "handled", label: "عولجت" },
            { key: "all", label: "الكلّ" },
          ]}
        />
      }
    >
      <div className="ad-reports-page">
        <ErrorNote message={error} />
        {rows === null ? (
          <div className="ad-sec-loading">
            <Spinner />
          </div>
        ) : null}
        {rows !== null && rows.length === 0 ? (
          <div className="ad-reports-empty">
            <p className="ad-empty-title">{status === "open" ? "لا حالةَ مفتوحة." : "لا شيءَ هنا."}</p>
          </div>
        ) : null}
        {rows !== null && rows.length > 0 ? (
          <div className="ad-reports">
            {rows.map((row) => (
              <article key={row.id} className="ad-report" data-emergency-id={row.id} data-status={row.status}>
                <div className="ad-report-body">
                  <p className="ad-report-name">
                    {row.status === "open" ? "🔴 " : ""}
                    ضغطه {ROLE_LABEL[row.role] ?? row.role} · {COUNTRY_LABEL[row.country_code] ?? row.country_code} ·{" "}
                    {moment(row.created_at)}
                  </p>
                  <Person label="من ضغط" name={row.reporter.name} phone={row.reporter.phone} />
                  {row.rider ? <Person label="الراكب" name={row.rider.name} phone={row.rider.phone} /> : null}
                  {row.driver ? <Person label="الكبتن" name={row.driver.name} phone={row.driver.phone} /> : null}
                  {row.plate_number ? (
                    <p className="ad-report-line">
                      اللوحة: <span dir="ltr">{row.plate_number}</span>
                    </p>
                  ) : null}
                  {row.pickup_address || row.dropoff_address ? (
                    <p className="ad-report-line">
                      {row.pickup_address ?? "—"} ← {row.dropoff_address ?? "—"}
                    </p>
                  ) : null}
                  {row.ride_id === null ? <p className="ad-report-line">خارج رحلة</p> : null}
                  <p className="ad-report-line">
                    {row.lat !== null && row.lng !== null ? (
                      <a className="underline" href={mapLink(row.lat, row.lng)} target="_blank" rel="noreferrer">
                        أين ضُغط
                      </a>
                    ) : (
                      "الموقعُ لحظةَ الضغط غيرُ معروف"
                    )}
                    {row.live_lat !== null && row.live_lng !== null ? (
                      <>
                        {" · "}
                        <a className="font-semibold underline" href={mapLink(row.live_lat, row.live_lng)} target="_blank" rel="noreferrer">
                          أين السيارةُ الآن
                        </a>
                      </>
                    ) : null}
                  </p>
                  {row.status === "open" ? (
                    <HandleForm row={row} onDone={() => void load()} />
                  ) : (
                    <p className="mt-8 whitespace-pre-wrap text-13 leading-relaxed text-ink">
                      عولجت {row.handled_at ? moment(row.handled_at) : ""} {row.handled_by_name ? `· ${row.handled_by_name}` : ""}
                      {"\n"}
                      {row.note}
                    </p>
                  )}
                </div>
              </article>
            ))}
          </div>
        ) : null}
        <ContactsCard />
      </div>
    </Shell>
  );
}
