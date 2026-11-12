/** **الدفعُ بالبطاقة عبر Whop** (أمرُ المالك ٢٠٢٦-١١-١٣) — الكباتنُ (الاشتراكُ والمستحقّات) والركّابُ (الشحنُ ودفعُ الرحلة)، في الأردن.
 *
 * **شاشةٌ واحدةٌ للمالك**: المفاتيحُ الثلاثةُ للأردن (والجزائرُ وليبيا مقفلتان في الخادم)، وحالُ العقد (أأُدخلت القيمُ الثلاث — بلا
 * قيمها)، وحدّا كلِّ طريقة، **وكلُّ دفعةٍ بنوعها وحالها ومبلغها ومرجع Whop وما قاله Whop عنها**. **وكلُّ إعدادٍ يُشرح بجانبه.**
 *
 * **والكتابةُ من أبوابها القائمة**: المفاتيحُ بـ`PUT /admin/settings/feature-flags`، والحدّان بـ`PATCH /admin/payment-methods/{id}`.
 * **والأرقامُ كلُّها من الخلفية** — لا حسابَ هنا.
 */

import { type ReactNode, useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { getWhopPay, getWhopPayLive, saveWhopLimits, setFeatureFlag } from "@/api/endpoints";
import type { FeatureKey, WhopLive, WhopOverview } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Table } from "@/components/Table";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Switch } from "@/components/ui/Field";
import { MoneyField } from "@/components/ui/Inputs";
import { PAYMENT_REQUEST_PURPOSE_LABEL, PAYMENT_REQUEST_STATUS_LABEL, PAYMENT_REQUEST_STATUS_TONE } from "@/lib/labels";
import { DISPLAY_LOCALE, cn, digits } from "@/lib/utils";

function when(iso: string): string {
  const at = new Date(iso);
  return `${digits(at.toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long" }))} ${digits(
    at.toLocaleTimeString(DISPLAY_LOCALE, { hour: "numeric", minute: "2-digit" }),
  )}`;
}

function Explain({ children }: { children: ReactNode }) {
  return <p className="mt-4 text-11 leading-note text-muted">{children}</p>;
}

export function WhopPayScreen() {
  const [data, setData] = useState<WhopOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [limits, setLimits] = useState<Record<string, { min: string; max: string }>>({});
  const [live, setLive] = useState<Record<string, WhopLive | string>>({});

  const fill = useCallback((next: WhopOverview) => {
    setData(next);
    setLimits(
      Object.fromEntries(
        next.methods.map((row) => [row.method.id, { min: row.method.min_amount ?? "", max: row.method.max_amount ?? "" }]),
      ),
    );
  }, []);

  const load = useCallback(() => {
    setError(null);
    getWhopPay()
      .then(fill)
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "تعذّر التحميل"));
  }, [fill]);

  useEffect(load, [load]);

  async function toggle(key: string, title: string, next: boolean) {
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      await setFeatureFlag({ country_code: "JO", feature_key: key as FeatureKey, enabled: next });
      setSaved(next ? `أُشعل «${title}» في الأردن` : `أُطفئ «${title}» في الأردن`);
      load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  async function saveLimits(methodId: string) {
    const row = limits[methodId];
    if (!row) return;
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      await saveWhopLimits(methodId, { min_amount: row.min.trim() || null, max_amount: row.max.trim() || null });
      setSaved("حُفظ الحدّان");
      load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  async function askLive(requestId: string) {
    try {
      const answer = await getWhopPayLive(requestId);
      setLive((current) => ({ ...current, [requestId]: answer }));
    } catch (caught) {
      setLive((current) => ({ ...current, [requestId]: caught instanceof ApiError ? caught.message : "تعذّر السؤال" }));
    }
  }

  return (
    <Shell title="الدفع بالبطاقة عبر Whop" subtitle="الكباتنُ والركّابُ في الأردن يدفعون ببطاقتهم البنكيّة في صفحة Whop الآمنة">
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
                  ? "جاهز — تظهر الطريقةُ لمن اشتعل مفتاحُه في الأردن."
                  : "مخفيّةٌ عن الجميع تلقائيّاً — لم تُدخل قيمُ العقد الثلاث بعد، أو العقدُ غيرُ مفعَّل."}
              </p>
              <p className="ad-report-line">
                قيمُ العقد: {data.keys_entered ? "أُدخلت" : "لم تُدخل"} · العقد: {data.contract_active ? "مفعَّل" : "غيرُ مفعَّل"}
                {data.currency ? ` · عملةُ الخصم: ${data.currency}` : ""}
                {data.sandbox ? " · وضعُ التجربة (مالٌ غيرُ حقيقيّ)" : ""}
              </p>
              <Explain>
                القيمُ الثلاث في «العقود» ← «Whop — الدفع بالبطاقة المصرفية (الكباتن)» ← الأردن: «مفتاح API» و«سرّ الإشعارات» (يبدأ بـ ws_)
                و«معرّف الحساب» (يبدأ بـ biz_). وعنوانُ الإشعارات المضبوطُ في لوحة Whop (Developer ← Webhooks):
              </Explain>
              <p dir="ltr" className="ad-ltr mt-4 select-all text-11 text-ink">
                {data.webhook_url}
              </p>
              <Explain>
                رسومُ Whop المنشورة على كلِّ دفعةٍ ناجحة: 2.7% + 0.30 دولار، و1.5% زيادةً للبطاقة الدوليّة، و1% إن لزم تحويلُ عملة — تُخصم من
                رصيدك عند Whop لا من الدافع: تُخصم بطاقتُه مستحقَّه وحدَه. والسحبُ إلى بنكك من Whop يحتاج تحقّقَ هويّتك هناك (Settings ←
                Verifications).
              </Explain>
            </div>
          </section>

          <section className="ad-report">
            <div className="ad-report-body">
              <p className="ad-report-name">مفاتيحُ الأردن</p>
              {data.switches.map((row) => (
                <div key={row.key} className="mt-8">
                  <div className="flex items-center justify-between gap-10">
                    <span className="text-12 text-ink">{row.title}</span>
                    <Switch
                      checked={row.enabled}
                      disabled={busy}
                      label={`${row.title} في الأردن`}
                      onChange={(next) => void toggle(row.key, row.title, next)}
                    />
                  </div>
                  <Explain>{row.hint}</Explain>
                </div>
              ))}
              <Explain>
                مطفأً يختفي الزرّ ولا يُفتح دفعٌ جديد، وما بدأ قبله يُحسم كما هو. والجزائرُ وليبيا مقفلتان في الخادم — لا تُشعلان من هنا.
              </Explain>
            </div>
          </section>

          <section className="ad-report">
            <div className="ad-report-body">
              <p className="ad-report-name">حدّا الدفعة الواحدة (بالدينار)</p>
              {data.methods.map((row) => {
                const value = limits[row.method.id] ?? { min: "", max: "" };
                return (
                  <div key={row.method.id} className="mt-10">
                    <p className="text-12 font-semibold text-ink">
                      {row.audience} — {row.method.name}
                    </p>
                    <div className="mt-6 grid grid-cols-2 gap-10">
                      <MoneyField
                        label="أقلُّ مبلغٍ للدفعة"
                        currency="JOD"
                        value={value.min}
                        onChange={(next) => setLimits((current) => ({ ...current, [row.method.id]: { ...value, min: next } }))}
                      />
                      <MoneyField
                        label="أكثرُ مبلغٍ للدفعة"
                        currency="JOD"
                        value={value.max}
                        onChange={(next) => setLimits((current) => ({ ...current, [row.method.id]: { ...value, max: next } }))}
                      />
                    </div>
                    <div className="mt-6">
                      <Button size="md" loading={busy} onClick={() => void saveLimits(row.method.id)}>
                        احفظ الحدّين
                      </Button>
                    </div>
                  </div>
                );
              })}
              <Explain>فارغٌ يعني بلا حدّ. وما خرج عن الحدّين يُرفض قبل فتح صفحة Whop، ويُقال للدافع بالعربيّة.</Explain>
            </div>
          </section>

          <Table
            columns="1.3fr 0.8fr 1fr 0.9fr 1.2fr 1.1fr 1.3fr"
            headers={["الدافع", "من", "النوع", "المبلغ", "مرجع Whop", "الحال", "ما قاله Whop"]}
            rows={data.requests}
            keyOf={(row) => row.id}
            height="compact"
            empty={{
              title: "لا دفعات Whop بعد",
              hint: "يظهر هنا كلُّ دفعٍ بالبطاقة عبر Whop: من دفع ونوعُه ومبلغُه ومرجعُه عند Whop وحالُه وما قاله Whop عنه.",
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
                  <span className="text-muted">{row.audience}</span>
                  <span className="text-muted">{PAYMENT_REQUEST_PURPOSE_LABEL[row.purpose]}</span>
                  <span className="font-semibold text-ink">{digits(row.amount)} دينار</span>
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
                    {answer && typeof answer !== "string"
                      ? answer.payments.map((item) => (
                          <span key={String(item.id)} dir="ltr" className="block">
                            {[item.id, item.status, item.substatus, item.total].filter(Boolean).join(" · ")}
                          </span>
                        ))
                      : null}
                    {row.external_id ? (
                      <button type="button" className="text-10.5 font-semibold text-ink underline" onClick={() => void askLive(row.id)}>
                        اسأل Whop الآن
                      </button>
                    ) : null}
                  </span>
                </>
              );
            }}
          />
          <Explain>
            «المبلغ» ما أُضيف أو سُدِّد بالدينار، ولا يتغيّر إلا حين يقول Whop «دُفع» بإشعارٍ موقَّعٍ متحقَّق (أو بالسؤال المباشر إن فات
            الإشعار). والمستردُّ والمتنازَعُ عليه يُرفضان بسببهما، والمحاولةُ التي رفضها البنكُ لا تُغلق الطلبَ حتى تنقضي مهلتُه. ورسمُ Whop
            لا يُكتب هنا — يُخصم من رصيدك عند Whop.
          </Explain>
        </div>
      )}
    </Shell>
  );
}
