/** شاشةُ «الموقع» — ما يعرضه `taxo.tajora.ly` (**البند ٤٩، §52**).
 *
 * **ولا نصَّ ولا رابطَ في الصفحة مخبوزٌ في HTML**: كلُّ ما هنا يصل الزائرَ
 * **بلا نشرٍ ولا بناء** — وهو شرطُ المالك المكتوب. والصفحةُ تقرأ
 * `GET /public/site`، وهذه الشاشةُ تكتب `PATCH /admin/site`.
 *
 * ## وثلاثةُ حقولٍ تُعرض ولا تُكتب هنا
 *
 * **نسبةُ العمولة** بيتُها `commission_settings` في شاشة الإعدادات —
 * **وشاشتان تكتبان قاعدةَ مالٍ واحدةً حالان يمكن أن تختلفا**. تُعرض هنا لأن
 * الصفحةَ تنشرها، **ويُقال أين تُغيَّر**.
 *
 * **ومفاتيحُ الميزات** من صفحة العقود والإعدادات — والصفحةُ ترسم «قريباً»
 * لِما أُطفئ. **ولا مفتاحَ ثانٍ يُخترع هنا لمفهومٍ قائم.**
 *
 * ## والفرقُ بين «مخفيّ» و«مطفأ» مكتوبٌ في الشاشة لا مضمَرٌ فيها
 *
 * **المطفأُ يُرسم بشارة «قريباً»** (مفتاحُ ميزةٍ في مكانه)، **والمخفيُّ لا
 * يُرسم أصلاً** (هذه الشاشة). وخلطُهما يجعل «قريباً» تعني «لا شيء».
 */

import { useCallback, useEffect, useState } from "react";

import { readSite, updateSite } from "@/api/endpoints";
import type { SiteSettings, SiteUpdate } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox, Field, Select } from "@/components/ui/Field";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { useFormError } from "@/lib/form-errors";
import { moment } from "@/lib/format";
import { digits } from "@/lib/utils";

/** **أثرُ كلِّ وضعٍ يُقال بجانبه** — ولا يُترك للمشرف أن يستنتجه. */
const MODE_EFFECT: Record<string, string> = {
  apk: "تجريبي: روابط APK",
  play: "المتجر: شارات Google Play",
};

/** أقسامُ الصفحة بمفاتيحها — **والمفتاحُ هو ما يقرؤه الموقع**. */
const SECTIONS: { key: string; label: string }[] = [
  { key: "why", label: "لماذا TAXO" },
  { key: "story", label: "قصة الرحلة" },
  { key: "rider", label: "للراكب" },
  { key: "captain", label: "للكبتن" },
  { key: "women", label: "الخدمة النسائية" },
  { key: "how", label: "كيف تعمل" },
  { key: "trust", label: "الأمان والثقة" },
  { key: "wallet", label: "المحفظة والدفع" },
  { key: "soon", label: "قريباً" },
  { key: "download", label: "التحميل" },
  { key: "faq", label: "الأسئلة الشائعة" },
];

const SOCIALS: { key: keyof SiteUpdate; label: string }[] = [
  { key: "social_facebook", label: "فيسبوك" },
  { key: "social_instagram", label: "إنستغرام" },
  { key: "social_tiktok", label: "تيك توك" },
  { key: "social_x", label: "إكس" },
  { key: "social_whatsapp", label: "واتساب" },
];

interface FaqRow {
  q: string;
  a: string;
}

export function SiteScreen() {
  const [site, setSite] = useState<SiteSettings | null>(null);
  const [draft, setDraft] = useState<SiteUpdate>({});
  const [faq, setFaq] = useState<FaqRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState("");
  const form = useFormError();

  const load = useCallback(async () => {
    const row = await readSite();
    setSite(row);
    setFaq(
      (row.faq ?? []).map((item) => ({
        q: String(item.q ?? ""),
        a: String(item.a ?? ""),
      })),
    );
    setDraft({});
  }, []);

  useEffect(() => {
    load().catch((caught) => form.capture(caught, "تعذّرت قراءة إعدادات الموقع"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  /** **ما لم يتغيّر لا يُرسل** — والباب يفرّق «لم يُرسَل» عن «أُرسل فارغاً». */
  function edit<K extends keyof SiteUpdate>(key: K, value: SiteUpdate[K]) {
    setDraft((prev) => ({ ...prev, [key]: value }));
    setDone("");
  }

  function valueOf<K extends keyof SiteUpdate & keyof SiteSettings>(key: K) {
    return (draft[key] ?? site?.[key] ?? "") as string;
  }

  function boolOf(key: keyof SiteUpdate & keyof SiteSettings) {
    return Boolean(draft[key] ?? site?.[key] ?? false);
  }

  function toggleHidden(list: "hidden_sections" | "hidden_cards", key: string) {
    const current = (draft[list] ?? site?.[list] ?? []) as string[];
    const next = current.includes(key)
      ? current.filter((k) => k !== key)
      : [...current, key];
    edit(list, next);
  }

  async function save() {
    form.clear();
    setBusy(true);
    try {
      const body: SiteUpdate = { ...draft };
      // **الأسئلةُ تُرسل حين تُحرَّر وحدَها** — وإرسالُها دائماً يجعل كلَّ حفظٍ
      // تعديلاً على الأسئلة في سجلّ التدقيق، ولو لم تُمسّ.
      const original = JSON.stringify(
        (site?.faq ?? []).map((r) => ({ q: r.q, a: r.a })),
      );
      if (JSON.stringify(faq) !== original) {
        body.faq = faq.map((row, index) => ({ ...row, order: index + 1 }));
      }
      const row = await updateSite(body);
      setSite(row);
      setDraft({});
      setDone("حُفظ — ويصل الزائرَ خلال دقيقة.");
    } catch (caught) {
      form.capture(caught, "تعذّر حفظ إعدادات الموقع");
    } finally {
      setBusy(false);
    }
  }

  if (!site) {
    return (
      <Shell title="الموقع" subtitle="ما يعرضه taxo.tajora.ly">
        <ErrorNote message={form.message} />
      </Shell>
    );
  }

  const mode = (draft.distribution_mode ?? site.distribution_mode) as string;

  return (
    <Shell
      title="الموقع"
      subtitle="ما يعرضه taxo.tajora.ly — يُبدَّل من هنا بلا نشر"
    >
      <ErrorNote message={form.message} />
      <SuccessNote message={done} />

      <div className="mt-12 grid gap-16">
        {/* ── الواجهة ─────────────────────────────────────────────── */}
        <section className="rounded-14 border border-line bg-surface p-16">
          <h2 className="mb-4 text-13 font-semibold text-ink">الواجهة</h2>
          <p className="mb-12 text-11.5 leading-note text-muted">
            العنوانُ والسطرُ تحته وملاحظةُ السوق — كما تُقرأ في أعلى الصفحة.
          </p>
          <Field
            label="العنوان"
            name="hero_title"
            value={valueOf("hero_title")}
            maxLength={120}
            onChange={(event) => edit("hero_title", event.target.value)}
          />
          <div className="mt-8">
            <Field
              label="السطر تحته"
              name="hero_subtitle"
              value={valueOf("hero_subtitle")}
              maxLength={240}
              onChange={(event) => edit("hero_subtitle", event.target.value)}
            />
          </div>
          <div className="mt-8">
            <Field
              label="ملاحظة السوق"
              name="hero_note"
              value={valueOf("hero_note")}
              maxLength={80}
              onChange={(event) => edit("hero_note", event.target.value)}
            />
          </div>
        </section>

        {/* ── الشريط الإعلاني ─────────────────────────────────────── */}
        <section className="rounded-14 border border-line bg-surface p-16">
          <h2 className="mb-4 text-13 font-semibold text-ink">الشريط الإعلاني</h2>
          <p className="mb-12 text-11.5 leading-note text-muted">
            شريطٌ فوق الصفحة كلِّها. <b>ومفتاحُه منفصلٌ عن نصِّه</b> — فإطفاؤه لا
            يمحو ما كُتب.
          </p>
          <Checkbox
            checked={boolOf("announce_enabled")}
            onChange={(next) => edit("announce_enabled", next)}
          >
            أظهِر الشريط
          </Checkbox>
          <div className="mt-8">
            <Field
              label="النص"
              name="announce_text"
              value={valueOf("announce_text")}
              maxLength={200}
              onChange={(event) => edit("announce_text", event.target.value)}
            />
          </div>
          <div className="mt-8">
            <Field
              label="الرابط (https، ويجوز تركه فارغاً)"
              name="announce_url"
              value={valueOf("announce_url")}
              maxLength={300}
              onChange={(event) => edit("announce_url", event.target.value)}
            />
          </div>
        </section>

        {/* ── التحميل ─────────────────────────────────────────────── */}
        <section className="rounded-14 border border-line bg-surface p-16">
          <h2 className="mb-4 text-13 font-semibold text-ink">التحميل</h2>
          <p className="mb-12 text-11.5 leading-note text-muted">
            <b>مفتاحٌ واحدٌ للتطبيقين</b>، ويصل الزائرَ خلال دقيقة بلا نشر.
          </p>
          <div className="flex flex-wrap items-center gap-10">
            <Select
              label="وضع التوزيع"
              name="distribution_mode"
              value={mode}
              onChange={(event) =>
                edit("distribution_mode", event.target.value as "apk" | "play")
              }
            >
              <option value="apk">تجريبي — APK</option>
              <option value="play">المتجر — Google Play</option>
            </Select>
            <Badge tone={mode === "play" ? "ok" : "warn"}>
              {MODE_EFFECT[mode] ?? mode}
            </Badge>
          </div>
          <div className="mt-8">
            <Field
              label="رابط الراكب على Google Play"
              name="play_url_rider"
              value={valueOf("play_url_rider")}
              maxLength={300}
              onChange={(event) => edit("play_url_rider", event.target.value)}
            />
          </div>
          <div className="mt-8">
            <Field
              label="رابط الكبتن على Google Play"
              name="play_url_driver"
              value={valueOf("play_url_driver")}
              maxLength={300}
              onChange={(event) => edit("play_url_driver", event.target.value)}
            />
          </div>
          <div className="mt-8">
            <Field
              label="رابط iOS (فارغ = شارة معطَّلة)"
              name="ios_url"
              value={valueOf("ios_url")}
              maxLength={300}
              onChange={(event) => edit("ios_url", event.target.value)}
            />
          </div>
          <div className="mt-10">
            <Checkbox
              checked={boolOf("apk_page_enabled")}
              onChange={(next) => edit("apk_page_enabled", next)}
            >
              أتِح صفحة APK غير المفهرسة في وضع المتجر
            </Checkbox>
          </div>
          <p className="mt-10 text-11.5 leading-note text-muted">
            <b>ولا زرَّ بلا رابط</b>: رابطٌ فارغٌ يعطي شارةً معطَّلةً بنصِّ «قريباً
            على Google Play»، لا زرّاً يفتح لا شيء.
          </p>
        </section>

        {/* ── التواصل ─────────────────────────────────────────────── */}
        <section className="rounded-14 border border-line bg-surface p-16">
          <h2 className="mb-4 text-13 font-semibold text-ink">التواصل</h2>
          <p className="mb-12 text-11.5 leading-note text-muted">
            <b>الفارغُ لا يُرسم أيقونةً معطَّلة</b> — يختفي من التذييل.
          </p>
          <Field
            label="بريد الدعم"
            name="support_email"
            value={valueOf("support_email")}
            maxLength={120}
            onChange={(event) => edit("support_email", event.target.value)}
          />
          <div className="mt-8">
            <Field
              label="بريد الخصوصية"
              name="privacy_email"
              value={valueOf("privacy_email")}
              maxLength={120}
              onChange={(event) => edit("privacy_email", event.target.value)}
            />
          </div>
          {SOCIALS.map((row) => (
            <div className="mt-8" key={String(row.key)}>
              <Field
                label={row.label}
                name={String(row.key)}
                value={valueOf(row.key as never)}
                maxLength={300}
                onChange={(event) => edit(row.key, event.target.value as never)}
              />
            </div>
          ))}
        </section>

        {/* ── إظهار وإخفاء ────────────────────────────────────────── */}
        <section className="rounded-14 border border-line bg-surface p-16">
          <h2 className="mb-4 text-13 font-semibold text-ink">أقسام الصفحة</h2>
          <p className="mb-12 text-11.5 leading-note text-muted">
            <b>المخفيُّ لا يُرسم أصلاً</b> — وهو غيرُ «المطفأ» الذي يُرسم بشارة
            «قريباً»، وذاك مفتاحُ ميزةٍ في صفحة الإعدادات لا هنا.
          </p>
          <div className="grid gap-8">
            {SECTIONS.map((row) => {
              const hidden = (
                (draft.hidden_sections ?? site.hidden_sections ?? []) as string[]
              ).includes(row.key);
              return (
                <Checkbox
                  key={row.key}
                  checked={!hidden}
                  onChange={() => toggleHidden("hidden_sections", row.key)}
                >
                  {row.label}
                </Checkbox>
              );
            })}
          </div>
        </section>

        {/* ── الأسئلة ─────────────────────────────────────────────── */}
        <section className="rounded-14 border border-line bg-surface p-16">
          <h2 className="mb-4 text-13 font-semibold text-ink">الأسئلة الشائعة</h2>
          <p className="mb-12 text-11.5 leading-note text-muted">
            الترتيبُ ترتيبُ الصفوف هنا. وحذفُ سؤالٍ يفرّغ حقلَيه ثم يُحفظ.
          </p>
          <div className="grid gap-12">
            {faq.map((row, index) => (
              <div key={index} className="rounded-12 border border-line p-12">
                <Field
                  label={`السؤال ${digits(index + 1)}`}
                  name={`faq_q_${index}`}
                  value={row.q}
                  onChange={(event) => {
                    const next = [...faq];
                    next[index] = { ...next[index], q: event.target.value };
                    setFaq(next);
                    setDone("");
                  }}
                />
                <div className="mt-8">
                  <Field
                    label="الجواب"
                    name={`faq_a_${index}`}
                    value={row.a}
                    onChange={(event) => {
                      const next = [...faq];
                      next[index] = { ...next[index], a: event.target.value };
                      setFaq(next);
                      setDone("");
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-10">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setFaq([...faq, { q: "", a: "" }])}
            >
              أضِف سؤالاً
            </Button>
          </div>
        </section>

        {/* ── السياسات ────────────────────────────────────────────── */}
        <section className="rounded-14 border border-line bg-surface p-16">
          <h2 className="mb-4 text-13 font-semibold text-ink">السياسات على الويب</h2>
          <p className="mb-12 text-11.5 leading-note text-muted">
            <b>مطفأٌ حتى تُراجَع النصوص</b>. وإشعالُه يعرض النسخةَ المنشورةَ في
            «السياسات والشروط» على <span dir="ltr">/privacy</span> و
            <span dir="ltr">/terms</span>. <b>ووثيقةٌ غيرُ منشورةٍ لا تظهر ولو
            أُشعل</b> — مفتاحان لا واحد.
          </p>
          <Checkbox
            checked={boolOf("policies_public")}
            onChange={(next) => edit("policies_public", next)}
          >
            اعرض السياسات والشروط على الموقع
          </Checkbox>
        </section>

        {/* ── يُقرأ ولا يُكتب ─────────────────────────────────────── */}
        <section className="rounded-14 border border-line bg-surface p-16">
          <h2 className="mb-4 text-13 font-semibold text-ink">يُقرأ ولا يُكتب هنا</h2>
          <p className="text-11.5 leading-note text-muted">
            نسبةُ العمولة التي تعرضها الصفحة:{" "}
            <b className="text-ink">{digits(site.commission_percent)}%</b> — بيتُها{" "}
            <b>شاشةُ الإعدادات</b>، وشاشتان تكتبان قاعدةَ مالٍ واحدةً حالان يمكن
            أن تختلفا.
          </p>
          <p className="mt-6 text-11.5 leading-note text-muted">
            آخر تعديل: {moment(site.updated_at)}
          </p>
        </section>

        <div className="flex justify-end">
          <Button onClick={save} disabled={busy}>
            {busy ? "يُحفظ…" : "احفظ"}
          </Button>
        </div>
      </div>
    </Shell>
  );
}
