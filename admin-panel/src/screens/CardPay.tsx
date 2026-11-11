/** **الدفعُ بالبطاقة المصرفية** (أمرُ المالك ٢٠٢٦-١١-١١) — اشتراكُ الكبتن ومستحقّاتُه ببطاقته البنكيّة عبر NOWPayments، في الأردن.
 *
 * **شاشةٌ واحدةٌ لكلِّ ما يلزم المالك**: المفتاحُ الرئيسيُّ لكلِّ دولة (الجزائرُ وليبيا مقفلتان في الخادم)، وحالُ العقد (أأُدخل المفتاحان
 * — بلا قيمهما)، وحدّا الدفعة وسقفُ اليوم وسعرُ الصرف، **وكلُّ دفعةٍ بحالها ومبلغها بالدينار ومرجع NOWPayments وما وصل منها**. **وكلُّ
 * إعدادٍ يُشرح بجانبه** — بأمر المالك.
 *
 * **والكتابةُ من أبوابها القائمة**: المفتاحُ بـ`PUT /admin/settings/feature-flags` (وفيه القفلُ بالدولة والتدقيق)، والحدودُ بـ
 * `PUT /admin/card-pay/limits`. **والأرقامُ كلُّها من الخلفية** — لا حسابَ هنا.
 */

import { type ReactNode, useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { getCardPay, getCardPayLive, saveCardPayLimits, setFeatureFlag } from "@/api/endpoints";
import type { CardPayCountry, CardPayLive, CardPayOverview, CountryCode, FeatureKey } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Table } from "@/components/Table";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Field, Switch } from "@/components/ui/Field";
import { MoneyField } from "@/components/ui/Inputs";
import { PAYMENT_REQUEST_PURPOSE_LABEL, PAYMENT_REQUEST_STATUS_LABEL, PAYMENT_REQUEST_STATUS_TONE } from "@/lib/labels";
import { DISPLAY_LOCALE, cn, digits } from "@/lib/utils";

/** **مفتاحُ الطريقة** — يُرسل من هنا كما يُرسل من صفحة «مفاتيح الميزات» */
const FLAG: FeatureKey = "nowpay_card_enabled";

const COUNTRY_NAME: Record<CountryCode, string> = { JO: "الأردن", DZ: "الجزائر", LY: "ليبيا" };

function when(iso: string): string {
  const at = new Date(iso);
  return `${digits(at.toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long" }))} ${digits(
    at.toLocaleTimeString(DISPLAY_LOCALE, { hour: "numeric", minute: "2-digit" }),
  )}`;
}

function Explain({ children }: { children: ReactNode }) {
  return <p className="mt-4 text-11 leading-note text-muted">{children}</p>;
}

export function CardPayScreen() {
  const [data, setData] = useState<CardPayOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [minAmount, setMinAmount] = useState("");
  const [maxAmount, setMaxAmount] = useState("");
  const [dailyCap, setDailyCap] = useState("");
  const [rate, setRate] = useState("");
  const [live, setLive] = useState<Record<string, CardPayLive | string>>({});

  const fill = useCallback((next: CardPayOverview) => {
    setData(next);
    setMinAmount(next.method?.min_amount ?? "");
    setMaxAmount(next.method?.max_amount ?? "");
    setDailyCap(next.daily_cap ?? "");
    setRate(next.usd_per_jod ?? "");
  }, []);

  const load = useCallback(() => {
    setError(null);
    getCardPay()
      .then(fill)
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "تعذّر التحميل"));
  }, [fill]);

  useEffect(load, [load]);

  async function toggle(row: CardPayCountry, next: boolean) {
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      await setFeatureFlag({ country_code: row.country_code, feature_key: FLAG, enabled: next });
      setSaved(next ? `أُشعل الدفعُ بالبطاقة في ${COUNTRY_NAME[row.country_code]}` : `أُطفئ الدفعُ بالبطاقة في ${COUNTRY_NAME[row.country_code]}`);
      load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  async function saveLimits() {
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      fill(
        await saveCardPayLimits({
          min_amount: minAmount.trim() || null,
          max_amount: maxAmount.trim() || null,
          daily_cap: dailyCap.trim() || null,
          usd_per_jod: rate.trim() || null,
        }),
      );
      setSaved("حُفظت الحدود");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  async function askLive(requestId: string) {
    try {
      const answer = await getCardPayLive(requestId);
      setLive((current) => ({ ...current, [requestId]: answer }));
    } catch (caught) {
      setLive((current) => ({ ...current, [requestId]: caught instanceof ApiError ? caught.message : "تعذّر السؤال" }));
    }
  }

  return (
    <Shell
      title="الدفع بالبطاقة المصرفية"
      subtitle="الكبتنُ يدفع اشتراكَه ومستحقّاتِه ببطاقته البنكيّة — ويصل المالُ حسابَك في NOWPayments"
    >
      <ErrorNote message={error} />
      <SuccessNote message={saved} />
      {data === null ? (
        error ? null : (
          <div className="ad-sec-loading">
            <Spinner />
          </div>
        )
      ) : (
        <div className="flex flex-col gap-16">
          <section className="ad-report">
            <div className="ad-report-body">
              <p className="ad-report-name">الحالُ الآن</p>
              <p className={cn("ad-report-line font-semibold", data.ready ? "text-ok" : "text-danger")}>
                {data.ready
                  ? "جاهز — تظهر «الدفع بالبطاقة المصرفية» للكباتن في الأردن حين يكون المفتاحُ مشتعلاً."
                  : "مخفيّةٌ عن الكباتن تلقائيّاً — لم يُدخل مفتاحا العقد بعد، أو العقدُ غيرُ مفعَّل."}
              </p>
              <p className="ad-report-line">
                مفتاحا العقد: {data.keys_entered ? "أُدخلا" : "لم يُدخلا"} · العقد: {data.contract_active ? "مفعَّل" : "غيرُ مفعَّل"}
                {data.sandbox ? " · وضعُ التجربة (مالٌ غيرُ حقيقيّ)" : ""}
              </p>
              <Explain>
                أدخل المفتاحين بنفسك من «العقود» ← «NOWPayments — الدفع بالبطاقة المصرفية (الكباتن)» ← الأردن: «مفتاح API» من لوحة
                NOWPayments (Settings ← Payments ← API keys)، و«سرّ الإشعارات» (Settings ← Payments ← Instant payment notifications)،
                ثم فعّل العقد. وعنوانُ الإشعارات الذي تضعه هناك:
              </Explain>
              <p dir="ltr" className="ad-ltr mt-4 select-all text-11 text-ink">
                {data.webhook_url}
              </p>
              <Explain>
                عنوانُ المحفظة التي يُحوَّل إليها المالُ تضبطه أنت في لوحة NOWPayments. ولا تُطلب هنا عبارةُ استعادتها ولا مفتاحُها
                الخاصّ، ولا تُحفظ في أيِّ مكان.
              </Explain>
            </div>
          </section>

          <section className="ad-report">
            <div className="ad-report-body">
              <p className="ad-report-name">المفتاحُ الرئيسيّ لكلِّ دولة</p>
              {data.countries.map((row) => (
                <div key={row.country_code} className="mt-8 flex items-center justify-between gap-10">
                  <span className="text-12 text-ink">
                    {COUNTRY_NAME[row.country_code]}
                    {row.locked ? <span className="ms-6 text-11 text-muted">— مقفلة</span> : null}
                  </span>
                  <Switch
                    checked={row.enabled}
                    disabled={busy || row.locked}
                    label={`الدفع بالبطاقة المصرفية في ${COUNTRY_NAME[row.country_code]}`}
                    onChange={(next) => void toggle(row, next)}
                  />
                </div>
              ))}
              <Explain>
                مشتعلاً في الأردن يرى كلُّ كبتنٍ هناك «الدفع بالبطاقة المصرفية» جوارَ كليك في صفحة الاشتراك وفي «المستحقّات عليك» —
                ما دام العقدُ جاهزاً. ومطفأً يختفي الزرّ ولا يُفتح دفعٌ جديد، وما بدأ قبله يُحسم كما هو. والجزائرُ وليبيا مقفلتان في
                الخادم: لا تُشعَلان من هنا ولا من غيرها.
              </Explain>
            </div>
          </section>

          <section className="ad-report">
            <div className="ad-report-body">
              <p className="ad-report-name">الحدود</p>
              <div className="mt-8 grid gap-12 md:grid-cols-2">
                <div>
                  <MoneyField label="أقلُّ مبلغٍ للدفعة الواحدة" value={minAmount} onChange={setMinAmount} currency="JOD" />
                  <Explain>
                    أقلُّ ما يُقبل في دفعةٍ واحدة (يبدأ 10 دنانير). تحتَه لا يرى الكبتنُ زرَّ البطاقة، ويرى سطراً: «أقلُّ دفعٍ بالبطاقة … —
                    للمبالغ الأصغر ادفع بكليك». ولمَ حدٌّ أدنى: رسمُ الشريك الثابت (2 دولار) تتحمّله TAXO، فالدفعةُ الصغيرةُ تكلّف أكثرَ
                    ممّا تجلب. فارغٌ = بلا حدٍّ أدنى.
                  </Explain>
                </div>
                <div>
                  <MoneyField label="أكثرُ مبلغٍ للدفعة الواحدة" value={maxAmount} onChange={setMaxAmount} currency="JOD" />
                  <Explain>أكثرُ ما يُقبل في دفعةٍ واحدة — يحدّ ما يُخاطَر به في دفعةٍ واحدة. فارغٌ = بلا حدٍّ أعلى.</Explain>
                </div>
                <div>
                  <MoneyField label="سقفُ مجموع اليوم" value={dailyCap} onChange={setDailyCap} currency="JOD" />
                  <Explain>
                    مجموعُ ما يُدفع بالبطاقة في يومٍ واحدٍ (بتوقيت الأردن) لكلِّ الكباتن معاً. إن بلغه رُدّ الدفعُ التالي برسالةٍ تقول
                    «ادفع بطريقةٍ أخرى أو حاول غداً». فارغٌ = بلا سقف. يُحفظ مع العقد، فيلزم إدخالُ المفتاحين أوّلاً.
                  </Explain>
                </div>
                <div>
                  <Field label="كم دولاراً لكلِّ دينار" value={rate} onChange={(event) => setRate(event.target.value)} dir="ltr" inputMode="decimal" />
                  <Explain>
                    البطاقةُ تُخصم بالدولار الأمريكي. يُحسب مبلغُ الدولار من مبلغ الدينار بهذا السعر ويُقرَّب للأعلى إلى السنت. فارغٌ =
                    ربطُ الدينار الرسميّ {digits("1.4104")}. يُحفظ مع العقد.
                  </Explain>
                </div>
              </div>
              <div className="mt-12">
                <Button size="md" loading={busy} onClick={() => void saveLimits()}>
                  حفظ الحدود
                </Button>
              </div>
              <p className="ad-report-line mt-12">
                ما دُفع اليوم بالبطاقة: <b>{digits(data.today_total)}</b> دينار
                {data.daily_cap ? <> من سقف {digits(data.daily_cap)}</> : null}
              </p>
              {data.partner ? (
                <Explain>
                  شريكُ البطاقة: {data.partner} — ورسمُه (<span dir="ltr">{data.partner_fee}</span>){" "}
                  {data.method?.fee_bearer === "taxo"
                    ? "تتحمّله TAXO: تُخفَّض الفاتورةُ حتى تُخصم بطاقةُ الكبتن مستحقَّه وحدَه، ويُقيَّد له كاملاً، ويصلك أقلّ."
                    : "على الكبتن الدافع، ويقال له قبل أن يدفع."}{" "}
                  ورسمُ NOWPayments على حسابك (0.5%) يُخصم مما يصلك. وأنّ رسمَ الشريك يُضاف فوق الفاتورة منقولٌ عن NOWPayments —
                  تؤكّده تجربتُك الأولى: إن خُصمت بطاقتُك أقلَّ من المستحقّ بالدولار فالرسمُ يُحسب بطريقةٍ أخرى.
                </Explain>
              ) : null}
            </div>
          </section>

          <Table
            columns="1.3fr 0.9fr 0.9fr 0.9fr 1.2fr 1.1fr 1.4fr 1fr"
            headers={["الكبتن", "المستحقّ", "خصمُ البطاقة", "الغرض", "مرجع NOWPayments", "الحال", "ما وصل حسابَك", "رسمٌ تحمّلته TAXO"]}
            rows={data.requests}
            keyOf={(row) => row.id}
            height="compact"
            empty={{
              title: "لا دفعات بالبطاقة بعد",
              hint: "يظهر هنا كلُّ دفعٍ بالبطاقة من كبتن: مستحقُّه بالدينار، وخصمُ بطاقته بالدولار، ومرجعُه عند NOWPayments، وحالُه، وما وصل حسابَك، والرسمُ الذي تحمّلته TAXO.",
            }}
            render={(row) => {
              const answer = live[row.id];
              return (
                <>
                  <span className="min-w-0">
                    <span className="block truncate text-11.5 text-ink">{row.user_name ?? "—"}</span>
                    <span dir="ltr" className="block text-10.5 text-muted">
                      {row.user_phone ?? ""}
                    </span>
                    <span className="block text-10.5 text-muted">{when(row.created_at)}</span>
                  </span>
                  <span className="font-semibold text-ink">{digits(row.amount)} دينار</span>
                  <span dir="ltr" className="text-ink">
                    {row.card_charge_usd ? `${digits(row.card_charge_usd)} USD` : "—"}
                  </span>
                  <span className="text-muted">{PAYMENT_REQUEST_PURPOSE_LABEL[row.purpose]}</span>
                  <span dir="ltr" className="text-10.5 text-muted">
                    {row.external_id ?? "—"}
                  </span>
                  <span className={cn("font-semibold", PAYMENT_REQUEST_STATUS_TONE[row.status])}>
                    {PAYMENT_REQUEST_STATUS_LABEL[row.status]}
                    {row.rejection_reason ?? row.cancel_reason ?? row.outcome_note ? (
                      <span className="block text-10.5 font-normal text-muted">
                        {row.rejection_reason ?? row.cancel_reason ?? row.outcome_note}
                      </span>
                    ) : null}
                    {row.subscription_id ? <span className="block text-10.5 font-normal text-ok">فُعِّل الاشتراك</span> : null}
                  </span>
                  <span className="text-10.5 text-muted">
                    {row.gateway_message ? (
                      <span dir="ltr" className="block">
                        {row.gateway_message}
                      </span>
                    ) : null}
                    {typeof answer === "string" ? <span className="block text-danger">{answer}</span> : null}
                    {answer && typeof answer !== "string" ? (
                      <span dir="ltr" className="block">
                        {[answer.status, answer.paid, answer.received].filter(Boolean).join(" · ")}
                      </span>
                    ) : null}
                    {row.external_id ? (
                      <button type="button" className="text-10.5 font-semibold text-ink underline" onClick={() => void askLive(row.id)}>
                        اسأل NOWPayments الآن
                      </button>
                    ) : null}
                  </span>
                  <span className="text-10.5 text-ink">
                    {row.taxo_fee ? <span className="block">{digits(row.taxo_fee)} دينار</span> : "—"}
                    {row.taxo_fee_usd ? (
                      <span dir="ltr" className="block text-muted">
                        {digits(row.taxo_fee_usd)} USD
                      </span>
                    ) : null}
                  </span>
                </>
              );
            }}
          />
          <Explain>
            «خصمُ البطاقة» محسوبٌ بسعر الصرف المحفوظ في العقد، و«رسمٌ تحمّلته TAXO» رسمُ الشريك الذي خُفّضت به الفاتورة (بالدينار كما
            كُتب عند فتح الدفعة). «ما وصل حسابَك» هو ما قاله NOWPayments عمّا أُضيف إلى حسابك بالأصل الرقميّ. لا يتغيّر اشتراكٌ ولا مستحقٌّ إلا حين يقول NOWPayments
            «اكتمل» (finished)؛ والجزئيُّ يُرفض بسببه ويُكتب ما وصل منه، والمنتهي والفاشل يُغلقان بلا أثر. وإن فات إشعارٌ سُئل NOWPayments
            كلَّ دقيقتين.
          </Explain>
        </div>
      )}
    </Shell>
  );
}
