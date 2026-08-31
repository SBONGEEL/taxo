/** حملةُ تأكيد الأرقام — **تُبنى ولا تُطلق** (قرارُ المالك 2026-08-31).
 *
 * ## ثلاثةُ أشياءَ في هذه الشاشة مقصودة
 *
 * **١) العددُ يُقرأ قبل الضغط لا بعده.** `scope_size` هو **كم حساباً تشمله
 * الحملةُ الآن** — ويُعرض على الزرِّ نفسِه. **ورقمٌ يُكتشف بعد الإطلاق ليس
 * قراراً**: من ضغط لا يستطيع أن يستردّ رسالةً أُرسلت.
 *
 * **٢) ولا زرَّ تجميدٍ ولا فكّ.** التجمّدُ والاستئنافُ **آليّان بلا مشرف**:
 * تسقط قناةُ السوق فتتجمّد، وتعود فتستأنف **بما بقي من المهل**. **وفكُّ
 * إيقافِ الحساب بتأكيد الرقم وحدَه** — وزرٌّ يفكّ بلا تأكيدٍ يُفرِّغ الحملةَ
 * من معناها، ومن ضغطه مرّةً سيضغطه لكلِّ من اشتكى.
 *
 * **٣) والإطلاقُ يستأذن مرّتين.** ليس تنميقاً: **هذه الشاشةُ ترسل إشعاراتٍ
 * إلى ناسٍ حقيقيين وتوقف حساباتِهم بعد أربعةَ عشرَ يوماً**، وضغطةٌ واحدةٌ
 * بالخطأ لا تُستردّ.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  cancelVerificationCampaign,
  createVerificationCampaign,
  listVerificationCampaigns,
  startVerificationCampaign,
} from "@/api/endpoints";
import type { CountryCode, VerificationCampaignRow } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { Table } from "@/components/Table";
import { day } from "@/lib/format";

const TONE: Record<
  VerificationCampaignRow["status"],
  Parameters<typeof Badge>[0]["tone"]
> = {
  draft: "muted",
  running: "ok",
  paused: "warn",
  done: "muted",
  cancelled: "muted",
};

const LABEL: Record<VerificationCampaignRow["status"], string> = {
  draft: "مسوّدة",
  running: "تعمل",
  paused: "متجمّدة",
  done: "انتهت",
  cancelled: "أُلغيت",
};

export function VerificationCampaign({
  country,
  onError,
}: {
  country: CountryCode;
  onError: (message: string) => void;
}) {
  const [rows, setRows] = useState<VerificationCampaignRow[]>([]);
  const [days, setDays] = useState(14);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<VerificationCampaignRow | null>(
    null,
  );

  const fail = useCallback(
    (caught: unknown, fallback: string) =>
      onError(caught instanceof ApiError ? caught.message : fallback),
    [onError],
  );

  const load = useCallback(() => {
    listVerificationCampaigns()
      .then(setRows)
      .catch((caught) => fail(caught, "تعذّر التحميل"));
  }, [fail]);

  useEffect(load, [load]);

  const mine = rows.filter((row) => row.country_code === country);

  return (
    <section className="card mt-16 p-16">
      <h2 className="mb-4 text-15 font-bold text-ink">حملة تأكيد الأرقام</h2>
      <p className="mb-12 text-12 leading-note text-muted">
        تُمهل كلَّ حسابٍ رقمه غير مؤكَّد في هذا السوق — راكباً كان أو كبتناً —
        وتُرسل له ثلاثة تذكيرات، ثم يُوقَف حسابه آلياً حتى يؤكّد. والفكّ
        بتأكيد الرقم وحده، فوراً وبلا مشرف. وتتجمّد آلياً إن سقطت قناة التحقق
        في السوق وتستأنف بما بقي من المهل — فلا تجري مهلة على من لا يستطيع أن
        يستقبل رمزاً. والمحفظة لا تُمسّ، ويُمدَّد اشتراك الكبتن بأيام إيقافه.
      </p>

      <Table
        columns="0.8fr 0.7fr 0.7fr 0.7fr 0.7fr 0.9fr 1.4fr"
        headers={[
          "الحال",
          "المهلة",
          "تشملهم الآن",
          "مسجَّلون",
          "موقوفون",
          "أكّدوا",
          "",
        ]}
        rows={mine}
        keyOf={(row) => row.id}
        empty={{
          title: "لا حملة",
          hint: "لم تُنشأ حملةٌ لهذا السوق بعد.",
        }}
        render={(row) => (
          <>
            <span className="flex items-center gap-6">
              <Badge tone={TONE[row.status]}>{LABEL[row.status]}</Badge>
            </span>
            <span className="text-12 text-muted">{row.deadline_days} يوماً</span>
            <span className="text-12 text-ink">{row.scope_size}</span>
            <span className="text-12 text-muted">{row.enrolled}</span>
            <span className="text-12 text-muted">{row.suspended}</span>
            <span className="text-12 text-muted">{row.resolved}</span>
            <div className="flex items-center gap-8">
              {row.started_at ? (
                <span className="text-11 text-muted">
                  أُطلقت {day(row.started_at)}
                </span>
              ) : null}
              {row.status === "draft" ? (
                <Button size="sm" onClick={() => setConfirming(row)}>
                  أطلقها
                </Button>
              ) : null}
              {row.status === "running" || row.status === "paused" ? (
                <Button
                  size="sm"
                  variant="danger"
                  loading={busy === row.id}
                  onClick={() => {
                    setBusy(row.id);
                    cancelVerificationCampaign(row.id)
                      .then(load)
                      .catch((caught) => fail(caught, "تعذّر الإلغاء"))
                      .finally(() => setBusy(null));
                  }}
                >
                  ألغِها
                </Button>
              ) : null}
            </div>
          </>
        )}
      />

      <div className="mt-14 flex items-end gap-8 border-t border-line pt-14">
        <Field
          name="deadline_days"
          label="المهلة بالأيام"
          type="number"
          value={days}
          onChange={(event) => setDays(Number(event.target.value))}
        />
        <Button
          size="sm"
          variant="secondary"
          disabled={mine.some((row) =>
            ["draft", "running", "paused"].includes(row.status),
          )}
          onClick={() => {
            createVerificationCampaign({
              country_code: country,
              deadline_days: days,
            })
              .then(load)
              .catch((caught) => fail(caught, "تعذّر الإنشاء"));
          }}
        >
          أنشئ مسوّدة
        </Button>
        <p className="text-11 leading-note text-muted">
          تُنشأ مسوّدةً ولا تُطلق — ولا تُرسل رسالة واحدة قبل ضغطة «أطلقها».
        </p>
      </div>

      {confirming ? (
        <Modal title="إطلاق الحملة" onClose={() => setConfirming(null)}>
          <p className="text-13 leading-note text-ink">
            ستشمل <b>{confirming.scope_size}</b> حساباً في هذا السوق. تصلهم
            ثلاثة تذكيرات خلال {confirming.deadline_days} يوماً، ثم يُوقَف من
            لم يؤكّد رقمه.
          </p>
          <p className="mt-10 text-12 leading-note text-muted">
            وهذه رسائل تصل ناساً حقيقيين ولا تُستردّ. والإيقاف يمنع الرحلات
            والمحفظة، ويُفكّ فور تأكيد الرقم.
          </p>
          <div className="mt-16 flex gap-8">
            <Button
              loading={busy === confirming.id}
              onClick={() => {
                setBusy(confirming.id);
                startVerificationCampaign(confirming.id)
                  .then(() => {
                    setConfirming(null);
                    load();
                  })
                  .catch((caught) => fail(caught, "تعذّر الإطلاق"))
                  .finally(() => setBusy(null));
              }}
            >
              نعم، أطلقها الآن
            </Button>
            <Button variant="ghost" onClick={() => setConfirming(null)}>
              تراجع
            </Button>
          </div>
        </Modal>
      ) : null}
    </section>
  );
}
