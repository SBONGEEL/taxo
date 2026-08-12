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
import { Modal } from "@/components/ui/Modal";
import { Shell } from "@/components/Shell";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import {
  EmptyNote,
  ErrorNote,
  Spinner,
  SuccessNote,
} from "@/components/ui/Feedback";
import { useCountryConfig } from "@/lib/config";
import { useCountry } from "@/lib/country";
import { arabicDigits, cn } from "@/lib/utils";

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
  return `${at.toLocaleDateString("ar-EG", { day: "numeric", month: "long" })} ${at.toLocaleTimeString("ar-EG", { hour: "numeric", minute: "2-digit" })}`;
}

export function CampaignsScreen() {
  const { country } = useCountry();
  const countryConfig = useCountryConfig(country);

  const [rows, setRows] = useState<Campaign[] | null>(null);
  const [open, setOpen] = useState<Campaign | null>(null);
  const [deliveries, setDeliveries] = useState<Delivery[] | null>(null);
  const [composing, setComposing] = useState(false);
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

  const quiet =
    countryConfig?.quiet_hours_start && countryConfig.quiet_hours_end
      ? `${arabicDigits(countryConfig.quiet_hours_start)} – ${arabicDigits(countryConfig.quiet_hours_end)}`
      : null;

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
      {/* ما يحكم متى تصل الحملة فعلاً — بجانبها لا في صفحةٍ أخرى */}
      <div className="mb-14 flex flex-wrap items-center gap-12 rounded-14 border border-line bg-surface px-16 py-12 text-12 text-muted">
        <span className="font-semibold text-ink">ساعات الهدوء</span>
        {quiet ? (
          <>
            <span dir="ltr" className="font-bold text-ink">
              {quiet}
            </span>
            <span>{countryConfig?.quiet_hours_timezone}</span>
          </>
        ) : (
          <span>لم تُضبط بعد لهذه الدولة</span>
        )}
        <span className="leading-note">
          — حملةٌ تقع داخلها تُؤجَّل إلى النافذة التالية، ولا تُلغى ولا تُرسل
          ناقصة. والتقسيم بالدولة، فحملةٌ للسوقين تُرسل في كلٍّ منهما بنافذته.
        </span>
      </div>

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
              {arabicDigits(String(campaign.sent_count))}
            </span>
            <span className="flex justify-end gap-10">
              <button
                type="button"
                onClick={() => void showDeliveries(campaign)}
                className="text-11.5 font-semibold text-muted"
              >
                سجل الإرسال
              </button>
              {campaign.status === "draft" ||
              campaign.status === "scheduled" ? (
                <button
                  type="button"
                  onClick={() => void cancel(campaign)}
                  className="text-11.5 font-semibold text-danger"
                >
                  إلغاء
                </button>
              ) : null}
            </span>
          </div>
        ))}
      </div>

      {composing ? (
        <Composer
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
    </Shell>
  );
}

/** إنشاءُ حملة — بلا `segment`: ترفضها الخلفية اليوم برسالة صريحة. */
function Composer({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (message: string) => void;
}) {
  const { country } = useCountry();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [audience, setAudience] = useState<CampaignAudience>("all_drivers");
  const [scheduledAt, setScheduledAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await createCampaign({
        title: title.trim(),
        body: body.trim(),
        audience,
        country_code: audience === "by_country" ? country : null,
        // بلا موعدٍ تبقى مسودّة، وبموعدٍ تصير مجدولة (الخلفية تقرر)
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : null,
      });
      onCreated(
        scheduledAt ? "جُدولت الحملة" : "حُفظت مسودّة — تُرسل حين تُجدول",
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal onClose={onClose} title="حملة جديدة">
      <Field
        label="العنوان"
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
