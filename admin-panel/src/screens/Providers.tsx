/** عقود مزوّدي API — SPEC القسم 13/7، و`DESIGN.md` §3.3/3.5.
 *
 * **الصفحة الوحيدة التي تُشغّل ميزةً بلا نشر كود**: إدخالُ بيانات عقدٍ
 * وتفعيلُه يرفع مفتاح ميزته آلياً (`credentials.activate` تزامن `feature_key`).
 * ولذلك هي **لـ admin حصراً** (القسم 13/8) — ومن يملك مفاتيح المزودين يملك
 * المال والرسائل والخرائط معاً.
 *
 * **والنموذج يُبنى من `fields` التي تصفها الخلفية**، لا من قائمةٍ مكتوبةٍ هنا:
 * مزوّدٌ جديد يظهر ببطاقته كاملةً بلا سطرٍ في هذا الملف — وقائمةٌ يدوية تُنسى
 * عند أول إضافة.
 *
 * **والسرُّ يعود مقنّعاً `****` ويبقى كذلك**: إعادةُ إرساله كما هو تُبقي
 * المخزَّن، وهي القاعدة التي تجعل «حفظ» بعد تعديل حقلٍ واحد لا يمسح البقية.
 * ولا يخرج سرٌّ من الخلفية أبداً.
 *
 * **واختبارُ الاتصال لا يترك أثراً**: لا طلبَ يُفتح ولا مالَ يُحوَّل ولا رسالةَ
 * مدفوعة إلا برقمٍ يكتبه المشرف صراحةً. ويعمل على عقدٍ **غير مفعّل** — تُختبر
 * قبل أن تفتح الباب لا بعده. ويعود 200 حتى عند الفشل: المشرف طلب أن يعرف وقد
 * عرف، ونصُّ السبب هو كل فائدة الزرّ.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  activateProvider,
  deactivateProvider,
  getProviderCatalog,
  saveProviderCredential,
  testProviderCredential,
} from "@/api/endpoints";
import type {
  CountryCode,
  ProviderCatalog,
  ProviderCredential,
  ProviderSpec,
} from "@/api/types";
import { Shell } from "@/components/Shell";
import { WhatsAppSession } from "@/components/WhatsAppSession";
import { Button } from "@/components/ui/Button";
import { Checkbox, Field } from "@/components/ui/Field";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

/** المزودُ الذي يقبل رقماً للاختبار — إرسالٌ مدفوع لا يقع بالصدفة. */
const TESTS_WITH_PHONE = "sms";

function when(iso: string | null): string {
  if (!iso) return "لم يُختبر بعد";
  const at = new Date(iso);
  return `آخر اختبار: ${at.toLocaleDateString("ar-EG", { day: "numeric", month: "long" })} ${at.toLocaleTimeString("ar-EG", { hour: "numeric", minute: "2-digit" })}`;
}

export function ProvidersScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();

  const [catalog, setCatalog] = useState<ProviderCatalog | null>(null);
  const [open, setOpen] = useState<ProviderSpec | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    setCatalog(await getProviderCatalog());
  }, []);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة العقود",
      ),
    );
  }, [load]);

  /** عقدُ هذا المزود في الدولة المعروضة — والعامُّ لا دولةَ له. */
  function credentialOf(spec: ProviderSpec): ProviderCredential | undefined {
    return catalog?.credentials.find(
      (row) =>
        row.provider_key === spec.provider_key &&
        (spec.per_country ? row.country_code === country : true),
    );
  }

  if (!isAdmin) {
    return (
      <Shell title="عقود مزوّدي الخدمات" subtitle="لـ admin حصراً">
        <p className="rounded-16 border border-line bg-surface p-18 text-12.5 leading-note text-muted">
          هذه الصفحة لـ admin وحده (القسم 13/8): من يملك مفاتيح المزودين يملك
          المال والرسائل والخرائط معاً.
        </p>
      </Shell>
    );
  }

  return (
    <Shell
      title="عقود مزوّدي الخدمات وواجهات API"
      subtitle="المدفوعات والرسائل والخرائط — إدخال عقدٍ وتفعيلُه يشغّل ميزته بلا نشر"
    >
      <ErrorNote message={error} />
      <SuccessNote message={done} />

      {/* **بطاقةُ الجلسة فوق العقود لا بينها**: العقدُ يُدخَل مرةً وتُقرأ
          الجلسةُ كلَّ يوم — ومن يفتح هذه الصفحة وواتساب ساقطٌ يفتحها لها */}
      <div className="mt-12">
        <WhatsAppSession onError={setError} />
      </div>

      {catalog === null ? (
        <Spinner className="mx-auto" />
      ) : (
        <div className="mt-12 grid gap-12 lg:grid-cols-2">
          {catalog.providers.map((spec) => {
            const credential = credentialOf(spec);
            return (
              <article
                key={spec.provider_key}
                className="rounded-16 border border-line bg-surface p-18"
              >
                <div className="mb-8 flex items-start gap-12">
                  <div className="flex-1">
                    <h2 className="text-14 font-bold text-ink">{spec.label}</h2>
                    <p className="mt-3 text-11 text-muted">
                      {spec.per_country
                        ? `عقدٌ لكل دولة · ${country}`
                        : "عقدٌ واحد لكل المنصة"}
                      {spec.feature_key
                        ? " · يرفع مفتاح ميزته عند التفعيل"
                        : ""}
                    </p>
                  </div>
                  <span
                    className={cn(
                      "rounded-full border px-11 py-6 text-11 font-bold",
                      credential?.is_active
                        ? "border-ok text-ok"
                        : "border-line text-muted",
                    )}
                  >
                    {credential
                      ? credential.is_active
                        ? "متصل"
                        : "معطّل"
                      : "بلا عقد"}
                  </span>
                </div>

                <p className="mb-12 text-10.5 text-muted">
                  {when(credential?.last_tested_at ?? null)}
                </p>

                <div className="flex flex-wrap gap-10">
                  <button
                    type="button"
                    onClick={() => setOpen(spec)}
                    className="text-11.5 font-semibold text-ink underline"
                  >
                    {credential ? "تعديل العقد" : "ربط مزوّد"}
                  </button>

                  {credential ? (
                    <>
                      <TestButton
                        credential={credential}
                        withPhone={spec.provider_key === TESTS_WITH_PHONE}
                        onResult={(message) => {
                          setDone(message);
                          void load();
                        }}
                        onError={setError}
                      />
                      <button
                        type="button"
                        onClick={() => {
                          const action = credential.is_active
                            ? deactivateProvider
                            : activateProvider;
                          action(credential.id)
                            .then(() => {
                              setDone(
                                credential.is_active
                                  ? "عُطّل العقد — أُطفئت ميزته"
                                  : "فُعّل العقد — رُفعت ميزته",
                              );
                              void load();
                            })
                            .catch((caught) =>
                              setError(
                                caught instanceof ApiError
                                  ? caught.message
                                  : "تعذّر التنفيذ",
                              ),
                            );
                        }}
                        className={cn(
                          "text-11.5 font-semibold",
                          credential.is_active ? "text-danger" : "text-ok",
                        )}
                      >
                        {credential.is_active ? "تعطيل" : "تفعيل"}
                      </button>
                    </>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      )}

      <p className="mt-16 text-11.5 leading-note text-muted">
        القيم السرية تُعرض مقنّعة (****) بعد الحفظ ولا تغادر الخلفية. وإعادةُ
        إرسال القناع تُبقي المخزَّن كما هو — فتعديلُ حقلٍ واحد لا يمسح البقية.
      </p>

      {open ? (
        <CredentialModal
          spec={open}
          credential={credentialOf(open)}
          country={country}
          onClose={() => setOpen(null)}
          onSaved={(message) => {
            setOpen(null);
            setDone(message);
            void load();
          }}
        />
      ) : null}
    </Shell>
  );
}

function TestButton({
  credential,
  withPhone,
  onResult,
  onError,
}: {
  credential: ProviderCredential;
  withPhone: boolean;
  onResult: (message: string) => void;
  onError: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);

  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => {
        // رقمُ الاختبار يُطلب صراحةً: رسالةٌ مدفوعة لا تُرسل بالصدفة
        const phone = withPhone
          ? (window.prompt(
              "رقمٌ لإرسال رسالة اختبارٍ إليه (اتركه فارغاً للتحقق بلا إرسال)",
            ) ?? "")
          : "";
        setBusy(true);
        testProviderCredential(credential.id, phone.trim() || undefined)
          .then((result) =>
            onResult(
              result.ok
                ? `الاتصال سليم — ${result.detail}`
                : `فشل: ${result.detail}`,
            ),
          )
          .catch((caught) =>
            onError(
              caught instanceof ApiError ? caught.message : "تعذّر الاختبار",
            ),
          )
          .finally(() => setBusy(false));
      }}
      className="text-11.5 font-semibold text-muted disabled:opacity-60"
    >
      {busy ? "…" : "اختبار الاتصال"}
    </button>
  );
}

/** النموذجُ يُبنى من `spec.fields` — لا حقلَ مكتوبٌ في هذا الملف. */
function CredentialModal({
  spec,
  credential,
  country,
  onClose,
  onSaved,
}: {
  spec: ProviderSpec;
  credential: ProviderCredential | undefined;
  country: CountryCode;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const [values, setValues] = useState<Record<string, string | boolean>>(() =>
    Object.fromEntries(
      spec.fields.map((field) => [
        field.key,
        // **المفتاحُ منطقٌ لا نصّ** (2026-08-14): كان كلُّ حقلٍ يُحوَّل إلى
        // `String(...)`، فيصير «لا» النصَّ `"false"` — و`bool("false")` في
        // بايثون **صادق**، فيشتغل المزوّدُ الوهميُّ وهو مطفأ. قِيس من القاعدة.
        field.kind === "toggle"
          ? credential?.values[field.key] === true
          : String(credential?.values[field.key] ?? ""),
      ]),
    ),
  );
  const [busy, setBusy] = useState(false);
  const form = useFormError();
  const error = form.message;
  const setError = form.setMessage;

  const missing = spec.fields.filter(
    (field) => field.required && !String(values[field.key] ?? "").trim(),
  );

  return (
    <FormErrors value={form.field}>
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-dim px-20"
      onClick={onClose}
    >
      <div
        className="scr max-h-[86vh] w-modal max-w-full rounded-20 border border-line bg-surface p-24"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="mb-4 text-16 font-bold text-ink">{spec.label}</h2>
        <p className="mb-16 text-12 leading-note text-muted">
          {spec.per_country ? `عقدُ ${country}. ` : "عقدٌ واحد لكل المنصة. "}
          الحقولُ السرية تعود مقنّعة — اتركها كما هي لتبقى، أو اكتب قيمةً جديدة
          لتحلّ محلها.
        </p>

        <div className="flex flex-col gap-12">
          {spec.fields.map((field) =>
            field.kind === "toggle" ? (
              <Checkbox
                key={field.key}
                checked={values[field.key] === true}
                onChange={(next) =>
                  setValues((current) => ({ ...current, [field.key]: next }))
                }
              >
                {field.label}
              </Checkbox>
            ) : (
              <Field
                key={field.key}
                name={field.key}
                label={`${field.label}${field.required ? "" : " (اختياري)"}`}
                dir="ltr"
                value={String(values[field.key] ?? "")}
                onChange={(event) =>
                  setValues((current) => ({
                    ...current,
                    [field.key]: event.target.value,
                  }))
                }
              />
            ),
          )}
        </div>

        <ErrorNote message={error} />

        <div className="mt-18 flex gap-10">
          <Button
            className="flex-1"
            size="md"
            loading={busy}
            disabled={missing.length > 0}
            onClick={() => {
              setBusy(true);
              setError(null);
              saveProviderCredential(spec.provider_key, {
                country_code: spec.per_country ? country : null,
                values,
              })
                .then(() =>
                  onSaved("حُفظ العقد — فعّله ليعمل، واختبره قبل أن تفعّله"),
                )
                .catch((caught) => form.capture(caught, "تعذّر الحفظ"))
                .finally(() => setBusy(false));
            }}
          >
            حفظ
          </Button>
          <Button
            className="flex-1"
            size="md"
            variant="secondary"
            onClick={onClose}
          >
            تراجع
          </Button>
        </div>

        {missing.length > 0 ? (
          <p className="mt-12 text-11 leading-note text-warn">
            ينقص: {missing.map((field) => field.label).join("، ")}
          </p>
        ) : null}
      </div>
    </div>
    </FormErrors>
  );
}
