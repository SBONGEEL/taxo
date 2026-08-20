/** الإشعارات الجماعية — SPEC القسم 13/9، وشكلُها من `DESIGN.md` §3.2/3.3.
 *
 * مساراتُها بُنيت في المرحلة 8 وواجهتُها هنا. وثلاثةُ أشياء تقولها الشاشة
 * لأنها تحكم ما يقع فعلاً:
 *
 * 1. **ساعاتُ الهدوء تُعرض بجانب الجدولة**، لأن حملةً تقع داخلها **تُؤجَّل**
 *    إلى النافذة التالية ولا تُرسل ولا تُلغى. من يجدول الثامنة ولا يعرف أن
 *    الهدوء حتى الثامنة يظن أن شيئاً تعطّل.
 * 2. **التقسيم بالدولة لا بالحملة**: حملةٌ لسوقين تُرسل في الأردن الآن وفي
 *    ليبيا بعد ساعة إن اختلفت نافذتاهما، وتبقى `scheduled` حتى تنتهي كل دولة
 *    في نطاقها. فالحالة «مجدولة» لا تعني «لم يصل أحد».
 * 3. **سجلُّ التسليم يعرض `skipped` كما يعرض `sent`**: هو ما يجعل احترام
 *    إطفاء إشعارات العروض **مُثبَتاً** لا مُدّعى — صفٌّ يقول «تُخطّي» لمن
 *    أطفأها. وهذه ليست تفصيلاً فنياً: الجهةُ التي تسأل «لماذا لم تصلني»
 *    تُجاب من هذا الجدول.
 *
 * **ولا قناةَ SMS هنا**: النموذج يعرض قناتين، والحملات تسير على FCM وحده
 * (`FUTURE-FEATURES.md` بند 14) — وخيارٌ لا يقع أسوأ من غيابه.
 *
 * **ورموزُ الخصم أسفلَها** (12-ز): القسم 13 يسمّي القسمَ «العروض والحملات»،
 * وهما شيئان في صفحةٍ واحدة فلكلٍّ عنوانُه — وجدولُ الرموز في مكوّنه
 * (`components/PromoCodes.tsx`) لا في هذا الملف: شاشةٌ تحمل جدولين ومنمذجَين
 * تصير ألفَ سطرٍ لا يقرؤها أحد.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  cancelCampaign,
  createCampaign,
  updateCampaign,
  listCampaigns,
  listDeliveries,
} from "@/api/endpoints";
import type {
  Campaign,
  CampaignAudience,
  CampaignStatus,
  Delivery,
} from "@/api/types";
import { PromoCodes } from "@/components/PromoCodes";
import { MissionsLevels } from "@/components/MissionsLevels";
import { useSession } from "@/lib/session";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { Referrals } from "@/components/Referrals";
import { Modal } from "@/components/ui/Modal";
import { QuietHours } from "@/components/QuietHours";
import { Shell } from "@/components/Shell";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import {
  EmptyNote,
  ErrorNote,
  Spinner,
  SuccessNote,
} from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { digits, cn,
  DISPLAY_LOCALE,
} from "@/lib/utils";

const AUDIENCE_LABEL: Record<CampaignAudience, string> = {
  all_riders: "كل الركّاب",
  all_drivers: "كل السائقين",
  by_country: "كل مستخدمي الدولة",
  segment: "شريحة (المرحلة 12)",
};

const STATUS_LABEL: Record<CampaignStatus, string> = {
  draft: "مسودة",
  scheduled: "مجدولة",
  sent: "أُرسلت",
  cancelled: "ملغاة",
};

const STATUS_TONE: Record<CampaignStatus, string> = {
  draft: "text-muted",
  scheduled: "text-warn",
  sent: "text-ok",
  cancelled: "text-danger",
};

const DELIVERY_LABEL: Record<Delivery["status"], string> = {
  sent: "وصلت",
  failed: "فشلت",
  skipped: "تُخطّيت",
};

/** «١٠ أغسطس ٩:٠٠ م» — بالعربية وبأرقامها. */
function when(iso: string | null): string {
  if (!iso) return "—";
  const at = new Date(iso);
  return `${digits(at.toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long" }))} ${digits(at.toLocaleTimeString(DISPLAY_LOCALE, { hour: "numeric", minute: "2-digit" }))}`;
}

export function CampaignsScreen() {
  const { isAdmin } = useSession();
  const { country } = useCountry();

  const [rows, setRows] = useState<Campaign[] | null>(null);
  const [open, setOpen] = useState<Campaign | null>(null);
  const [deliveries, setDeliveries] = useState<Delivery[] | null>(null);
  // `true` إنشاءٌ جديد، وحملةٌ تعديلٌ لها، و`false` مغلق
  const [composing, setComposing] = useState<Campaign | boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(await listCampaigns());
  }, []);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الحملات",
      ),
    );
  }, [load]);

  async function showDeliveries(campaign: Campaign) {
    setOpen(campaign);
    setDeliveries(null);
    try {
      setDeliveries(await listDeliveries(campaign.id));
    } catch {
      setDeliveries([]);
    }
  }

  async function cancel(campaign: Campaign) {
    setError(null);
    setDone(null);
    try {
      await cancelCampaign(campaign.id);
      await load();
      setDone("أُلغيت الحملة — لن تُرسل");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الإلغاء");
    }
  }

  return (
    <Shell
      title="إشعارات جماعية"
      subtitle="حملاتٌ تصل عشرات الآلاف — كل كتابةٍ تدخل سجل التدقيق"
      actions={
        <Button size="sm" onClick={() => setComposing(true)}>
          + حملة جديدة
        </Button>
      }
    >
      {/* ما يحكم متى تصل الحملة فعلاً — بجانبها لا في صفحةٍ أخرى.
          **وكانت تُعرض ولا تُحرَّر**: `PUT /admin/campaigns/settings/{country}`
          مبنيٌّ ومصرَّحٌ به في `endpoints.ts` **ولا ينادِيه أحد** — ومنطقةُ
          الزمن فيه هي التي يُحسب بها «يومُ الدولة» في كلِّ تقرير. */}
      <QuietHours country={country} onError={setError} onSaved={setDone} />

      <ErrorNote message={error} />
      <SuccessNote message={done} />

      <div className="mt-12 overflow-hidden rounded-16 border border-line bg-surface">
        <div className="grid grid-cols-[2fr_1fr_1fr_1fr_0.8fr_auto] gap-10 bg-surface-2 px-18 py-10 text-11 font-semibold text-muted">
          <span>العنوان</span>
          <span>الجمهور</span>
          <span>الجدولة</span>
          <span>الحالة</span>
          <span>وصلت</span>
          <span />
        </div>

        {rows === null ? (
          <div className="p-24">
            <Spinner className="mx-auto" />
          </div>
        ) : rows.length === 0 ? (
          <EmptyNote
            title="لا حملات بعد"
            hint="أنشئ حملةً وجدولها — وسجلُّ من وصله يظهر هنا بعد الإرسال."
          />
        ) : null}

        {(rows ?? []).map((campaign) => (
          <div
            key={campaign.id}
            className="grid grid-cols-[2fr_1fr_1fr_1fr_0.8fr_auto] items-center gap-10 border-t border-line px-18 py-12 text-12.5"
          >
            <div className="min-w-0">
              <div className="truncate font-semibold text-ink">
                {campaign.title}
              </div>
              <div className="truncate text-11 text-muted">{campaign.body}</div>
            </div>
            <span className="text-ink">
              {AUDIENCE_LABEL[campaign.audience]}
              {campaign.country_code ? ` · ${campaign.country_code}` : ""}
            </span>
            <span className="text-muted">{when(campaign.scheduled_at)}</span>
            <span className={cn("font-bold", STATUS_TONE[campaign.status])}>
              {STATUS_LABEL[campaign.status]}
            </span>
            <span className="font-semibold text-ink">
              {digits(String(campaign.sent_count))}
            </span>
            <span className="flex justify-end gap-10">
              <button
                type="button"
                onClick={() => void showDeliveries(campaign)}
                className="text-11.5 font-semibold text-muted"
              >
                سجل الإرسال
              </button>
              {/* **والتعديلُ لما لم ينطلق وحدَه**: `campaigns.update` ترفض
                  ما ليس `draft` أو `scheduled` بـ٤٠٩، وزرٌّ يعمل ثم يرتدّ
                  يعلّم المشرفَ إعادةَ المحاولة بدل أن يقول له إن الباب أُغلق */}
              {campaign.status === "draft" ||
              campaign.status === "scheduled" ? (
                <>
                  {isAdmin ? (
                    <button
                      type="button"
                      onClick={() => setComposing(campaign)}
                      className="text-11.5 font-semibold text-accent-ink"
                    >
                      تعديل
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => void cancel(campaign)}
                    className="text-11.5 font-semibold text-danger"
                  >
                    إلغاء
                  </button>
                </>
              ) : null}
            </span>
          </div>
        ))}
      </div>

      {composing ? (
        <Composer
          editing={typeof composing === "boolean" ? null : composing}
          onClose={() => setComposing(false)}
          onCreated={(message) => {
            setComposing(false);
            setDone(message);
            void load();
          }}
        />
      ) : null}

      {open ? (
        <DeliveriesModal
          campaign={open}
          deliveries={deliveries}
          onClose={() => setOpen(null)}
        />
      ) : null}

      <PromoCodes onError={setError} />

      {/* الإحالاتُ هنا لا في «السائقين»: هي وحملاتُ الخصم شيءٌ واحد — عرضٌ
          تتحمّله الشركة، ومجموعُ كلفته يُقرأ في مكانٍ واحد */}
      <Referrals onError={setError} />

      {/* المهامُّ والمستوياتُ هنا لا في «السائقين»: هي — كالإحالة والكوبون —
          **أداةُ تحفيزٍ تتحمّلها الشركة**، وقراءتُها بجانب كلفتها في مكانٍ
          واحد. والفرقُ أن ثمنَها ليس مالاً بل **أمتاراً في ترتيب التوزيع** */}
      <MissionsLevels onError={setError} isAdmin={isAdmin} />
    </Shell>
  );
}

/** إنشاءُ حملة — بلا `segment`: ترفضها الخلفية اليوم برسالة صريحة. */
/** مؤلِّفُ الحملة — **وهو المحرِّرُ نفسُه حين يُسلَّم حملةً قائمة**.
 *
 * وحملةٌ مجدولةٌ لا تُعدَّل تعني **حذفاً وإعادةَ إنشاء**: يفقد المشرفُ نصَّه
 * وجدولتَه ليصلح حرفاً. والبابُ مبنيٌّ في الخلفية منذ المرحلة ٨ ومصرَّحٌ به في
 * `endpoints.ts` **ولا ينادِيه أحد**.
 *
 * **وما انطلق لا يُعدَّل**: `campaigns.update` ترفض ما ليس `draft` أو
 * `scheduled` — فالشاشةُ لا تعرض الزرَّ أصلاً على `sent` أو `cancelled`، لأن
 * زرّاً يعمل ثم يرتدّ يعلّم المشرفَ إعادةَ المحاولة.
 */
function Composer({
  editing,
  onClose,
  onCreated,
}: {
  /** حملةٌ قائمة ⇒ تحرير، و`null` ⇒ إنشاء. */
  editing: Campaign | null;
  onClose: () => void;
  onCreated: (message: string) => void;
}) {
  const { country } = useCountry();
  const [title, setTitle] = useState(editing?.title ?? "");
  const [body, setBody] = useState(editing?.body ?? "");
  const [audience, setAudience] = useState<CampaignAudience>(
    editing?.audience ?? "all_drivers",
  );
  // **قيمةُ `datetime-local` بلا منطقة**: تُقتطع الثانيةُ والمنطقةُ من ISO
  const [scheduledAt, setScheduledAt] = useState(
    editing?.scheduled_at ? editing.scheduled_at.slice(0, 16) : "",
  );
  const [busy, setBusy] = useState(false);
  const form = useFormError();
  const error = form.message;
  const setError = form.setMessage;

  async function submit() {
    setBusy(true);
    setError(null);
    const payload = {
      title: title.trim(),
      body: body.trim(),
      audience,
      country_code: audience === "by_country" ? country : null,
      // بلا موعدٍ تبقى مسودّة، وبموعدٍ تصير مجدولة (الخلفية تقرر)
      scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : null,
    };
    try {
      if (editing) await updateCampaign(editing.id, payload);
      else await createCampaign(payload);
      onCreated(
        editing
          ? "حُفظ التعديل"
          : scheduledAt
            ? "جُدولت الحملة"
            : "حُفظت مسودّة — تُرسل حين تُجدول",
      );
    } catch (caught) {
      form.capture(caught, "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <FormErrors value={form.field}>
    <Modal onClose={onClose} title={editing ? "تعديلُ حملة" : "حملة جديدة"}>
      <Field
        label="العنوان"
        name="title"
        value={title}
        maxLength={120}
        onChange={(event) => setTitle(event.target.value)}
      />
      <div className="mt-14">
        <label className="label" htmlFor="body">
          النص
        </label>
        <textarea
          id="body"
          name="body"
          rows={3}
          maxLength={500}
          className="fld"
          value={body}
          onChange={(event) => setBody(event.target.value)}
        />
      </div>

      <div className="mt-14">
        <span className="label">الجمهور</span>
        <div className="flex flex-wrap gap-8">
          {(["all_drivers", "all_riders", "by_country"] as const).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setAudience(key)}
              className={cn(
                "rounded-12 border px-14 py-10 text-12.5",
                audience === key
                  ? "border-ink font-semibold text-ink"
                  : "border-line text-muted",
              )}
            >
              {AUDIENCE_LABEL[key]}
              {key === "by_country" ? ` · ${country}` : ""}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-14">
        <label className="label" htmlFor="scheduled">
          الجدولة
        </label>
        <input
          id="scheduled"
          type="datetime-local"
          className="fld"
          value={scheduledAt}
          onChange={(event) => setScheduledAt(event.target.value)}
        />
        <p className="mt-6 text-11 leading-note text-muted">
          اتركه فارغاً لتبقى مسودّة. والموعدُ داخل ساعات الهدوء يؤجّل الإرسال
          إلى النافذة التالية — لا يُلغيه.
        </p>
      </div>

      <ErrorNote message={error} />

      <div className="mt-18 flex gap-10">
        <Button
          className="flex-1"
          size="md"
          loading={busy}
          disabled={title.trim().length < 2 || body.trim().length < 2}
          onClick={() => void submit()}
        >
          {scheduledAt ? "جدولة" : "حفظ مسودّة"}
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
    </Modal>
    </FormErrors>
  );
}

function DeliveriesModal({
  campaign,
  deliveries,
  onClose,
}: {
  campaign: Campaign;
  deliveries: Delivery[] | null;
  onClose: () => void;
}) {
  return (
    <Modal onClose={onClose} title={`سجل الإرسال — ${campaign.title}`}>
      {deliveries === null ? (
        <Spinner className="mx-auto" />
      ) : deliveries.length === 0 ? (
        <EmptyNote
          title="لم تُرسل بعد"
          hint="يظهر هنا من وصله الإشعار ومن تُخطّي ولماذا، بعد أول دورة إرسال."
        />
      ) : (
        <ul className="scr max-h-[46vh] divide-y divide-line">
          {deliveries.map((delivery) => (
            <li
              key={delivery.id}
              className="flex items-center justify-between py-11 text-12.5"
            >
              <span dir="ltr" className="text-muted">
                {delivery.user_id.slice(0, 8)}
              </span>
              <span
                className={cn(
                  "font-semibold",
                  delivery.status === "sent"
                    ? "text-ok"
                    : delivery.status === "failed"
                      ? "text-danger"
                      : "text-muted",
                )}
              >
                {DELIVERY_LABEL[delivery.status]}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-14 text-11 leading-note text-muted">
        «تُخطّيت» ليست فشلاً: أطفأ صاحبها إشعارات العروض، أو لا جهاز مسجَّل له —
        وهذا الصفُّ هو ما يجعل احترام الإطفاء مُثبتاً لا مُدّعى.
      </p>
    </Modal>
  );
}

/** نافذةٌ بنمط `DESIGN.md` §3.5 — تعتيمٌ وسطُ الشاشة ولوحٌ بنصف قطر 20. */
