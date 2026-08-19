/** قوالبُ رسالة رمز التحقق — قالبان، كلٌّ بحقله ومعاينته وحفظه المستقل.
 *
 * **والمعاينةُ من الخلفية لا من هنا**: لو حسبتها الشاشةُ لعرضت ما تظنّه، وخرج
 * على السلك ما تصوغه الخلفية — فيوافق المشرفُ على نصٍّ لم يره أحد. فهي تُصاغ
 * بنفس دالّة الإرسال وتصل جاهزة.
 *
 * **وسطرُ الرفض يُعرض هنا لا في السجل وحدَه**: من حرّر نصّاً مخالفاً يظنّه
 * يعمل، والسجلُّ لا يقرؤه إلا من يبحث عن عطبٍ يعرف بوجوده أصلاً.
 *
 * **والمتغيّراتُ معروضةٌ بمعناها تحت كل حقل**: قائمةٌ يحفظها المشرفُ من ذاكرته
 * قائمةٌ يخطئ فيها، وثمنُ الخطأ رسالةٌ تعرض اسمَ المتغيّر مكانَ الرمز.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { listOtpTemplates, saveOtpTemplate } from "@/api/endpoints";
import type { OtpTemplate, OtpTemplates as Payload } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

const VARIABLE_MEANING: Record<string, string> = {
  code: "الرمزُ نفسُه — إلزاميٌّ في القالبين",
  app_name: "اسمُ التطبيق كما يظهر للمستخدم",
  minutes: "مدةُ صلاحية الرمز بالدقائق",
};

function bytesOf(text: string): number {
  return new TextEncoder().encode(text).length;
}

function TemplateCard({
  template,
  maxBytes,
  variables,
  onSaved,
}: {
  template: OtpTemplate;
  maxBytes: number;
  variables: string[];
  onSaved: (next: OtpTemplate) => void;
}) {
  const [body, setBody] = useState(template.body);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setBody(template.body);
  }, [template.body]);

  const size = bytesOf(body);
  const dirty = body !== template.body;

  async function save() {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      onSaved(await saveOtpTemplate(template.purpose, body));
      setSaved(true);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card p-16">
      <div className="mb-10 flex items-center justify-between gap-10">
        <h3 className="text-14 font-semibold text-ink">{template.label}</h3>
        {template.is_default ? (
          <Badge tone="muted">لم يُحرَّر — النصُّ المدمج</Badge>
        ) : null}
      </div>

      {/* **الرفضُ يُقال على الشاشة**، لا في السجل وحدَه */}
      {template.rejected_at_send ? (
        <div className="mb-10 rounded-12 border border-danger px-12 py-10">
          <p className="text-12.5 font-semibold text-danger">
            هذا القالب مرفوضٌ عند الإرسال ويُستعمل النصُّ الافتراضي
          </p>
          <ul className="mt-6 space-y-3">
            {template.violations.map((v) => (
              <li key={v.code} className="text-11.5 leading-note text-muted">
                {v.message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <textarea
        value={body}
        rows={4}
        disabled={busy}
        onChange={(event) => setBody(event.target.value)}
        className="w-full rounded-12 border border-line bg-surface-2 px-12 py-10 text-12.5 leading-note text-ink"
      />

      <div className="mt-6 flex items-center justify-between gap-10">
        <p className="text-11 text-muted">
          {/* عدُّ بايتاتٍ — قياسٌ تقنيٌّ يُقارن برقمٍ في ملفِّ الشروط */}
          {size} / {maxBytes} بايت
        </p>
        {size > maxBytes ? (
          <span className="text-11 font-semibold text-danger">تجاوز الحدّ</span>
        ) : null}
      </div>

      <div className="mt-10 rounded-12 border border-line bg-surface-2 px-12 py-10">
        <p className="mb-4 text-11 font-semibold text-muted">
          المتغيّرات — تُكتب بين قوسين معقوفين
        </p>
        <ul className="space-y-3">
          {variables.map((name) => (
            <li key={name} className="text-11 leading-note text-muted">
              <span className="font-mono text-ink">{"{" + name + "}"}</span>
              {" — "}
              {VARIABLE_MEANING[name] ?? name}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-10 rounded-12 border border-line px-12 py-10">
        <p className="mb-4 text-11 font-semibold text-muted">
          المعاينة — بالقيم الحقيقية، والرمز {template.preview_sample_code}{" "}
          عيّنة
        </p>
        <p className="whitespace-pre-wrap text-12.5 leading-note text-ink">
          {template.preview}
        </p>
      </div>

      {error ? (
        <p className="mt-10 text-11.5 leading-note text-danger">{error}</p>
      ) : null}
      {saved && !dirty ? (
        <p className="mt-10 text-11.5 text-ok">حُفظ ✓</p>
      ) : null}

      <Button className="mt-12" loading={busy} disabled={!dirty} onClick={save}>
        احفظ {template.label}
      </Button>
    </section>
  );
}

export function OtpTemplates() {
  const [payload, setPayload] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    listOtpTemplates()
      .then(setPayload)
      .catch((caught) =>
        setError(caught instanceof ApiError ? caught.message : "تعذّر التحميل"),
      );
  }, []);

  useEffect(load, [load]);

  if (!payload) {
    return error ? (
      <p className="text-12 text-danger">{error}</p>
    ) : (
      <p className="text-12 text-muted">جارٍ التحميل…</p>
    );
  }

  const variables = [
    ...payload.required_variables,
    ...payload.optional_variables,
  ];

  return (
    <div className="space-y-12">
      <p className="text-11.5 leading-note text-muted">
        نصُّ رسالة الرمز على واتساب، ويحكم الناقلَ الذاتيَّ وحدَه — قوالبُ
        المصادقة عند ميتا لا تقبل نصّاً حرّاً، فيُمرَّر إليها الرمزُ وحدَه.
        وقالبٌ يخالف الشروط يُرفض عند الإرسال ويُستعمل النصُّ الافتراضي بدلَه.
      </p>
      {payload.templates.map((template) => (
        <TemplateCard
          key={template.purpose}
          template={template}
          maxBytes={payload.max_body_bytes}
          variables={variables}
          onSaved={(next) =>
            setPayload({
              ...payload,
              templates: payload.templates.map((row) =>
                row.purpose === next.purpose ? next : row,
              ),
            })
          }
        />
      ))}
    </div>
  );
}
