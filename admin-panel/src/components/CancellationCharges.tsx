/** رسومُ الإلغاء (`design/CANCELLATION-FEE.md` §3 و§6-أ و§10).
 *
 * **بابان لا ثالث لهما، وكلاهما يُغلق صفّاً بلا أن يحرّك مالاً:**
 *
 * - **الإعفاء** — وهو **بابُ الاعتراض بعد الحدث**: القياسُ آليٌّ لحظةَ الإلغاء
 *   كي لا يُحبس من يريد الإلغاءَ الآن خلف طابورٍ بشريّ، وهذا هو البابُ الذي
 *   وُعد به بعدها. من قال «الكبتن لم يتحرك» يُراجَع هنا.
 * - **الشطب** — حين لا يعود الراكبُ أبداً وكان مآلُ الدولة «تشطبه الإدارة».
 *
 * **ولا زرَّ «حصّله»**: التحصيلُ يقع في محفظة صاحبه — خصماً مع رحلةٍ أو لحظةَ
 * شحن. وزرٌّ هنا يعني كتابةَ مالٍ من بابٍ ثانٍ، وهو ما لا تفعله أيُّ شاشةٍ في
 * هذه اللوحة (قاعدةُ جدول السلف نفسُها).
 *
 * **ولا زرَّ «تتحمّلها الشركة»**: ذلك إعدادُ دولةٍ تطبّقه الدورة، لا قرارٌ
 * يُتخذ صفّاً صفّاً — وزرٌّ به يجعل الخسارةَ تقع بمزاج من يفتح الشاشة بينما
 * وُضع الإعدادُ ليقرّرها مرةً واحدةً بقاعدةٍ مكتوبة.
 *
 * **والحاملُ يُعرض باسمه لأنه يغيّر السؤال كلَّه**: صفٌّ له حاملٌ يعني أن
 * الراكب سدَّد نقداً وأن المطلوبَ تحويلٌ من يدِ كبتن — فمطالبةُ الراكب حينها
 * مطالبةٌ لمن دفع.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  listCancellationCharges,
  waiveCancellationCharge,
  writeOffCancellationCharge,
} from "@/api/endpoints";
import type { CancellationChargeRow } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Table, TableSearch } from "@/components/Table";
import { useCountry } from "@/lib/country";
import { CHARGE_STATUS_LABEL, CHARGE_STATUS_TONE } from "@/lib/labels";
import { NO_RESULTS, useSearch } from "@/lib/search";
import { day, money } from "@/lib/format";

// **من `lib/labels.ts`** — يقرؤهما الملفُّ الشخصيُّ أيضاً (§37)
const TONE = CHARGE_STATUS_TONE;
const LABEL = CHARGE_STATUS_LABEL;

export function CancellationCharges({
  onError,
}: {
  onError: (message: string) => void;
}) {
  const { country } = useCountry();
  const [rows, setRows] = useState<CancellationChargeRow[] | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const search = useSearch();

  const load = useCallback(() => {
    listCancellationCharges(country, undefined, search.term)
      .then(setRows)
      .catch((caught) =>
        onError(caught instanceof ApiError ? caught.message : "تعذّر التحميل"),
      );
  }, [country, search.term, onError]);

  useEffect(load, [load]);

  async function act(
    row: CancellationChargeRow,
    run: (id: string, reason: string) => Promise<unknown>,
    missing: string,
  ) {
    const reason = reasons[row.id]?.trim();
    if (!reason) {
      onError(missing);
      return;
    }
    setBusy(row.id);
    try {
      await run(row.id, reason);
      setReasons((current) => ({ ...current, [row.id]: "" }));
      load();
    } catch (caught) {
      onError(caught instanceof ApiError ? caught.message : "تعذّر التنفيذ");
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      {/* عمودُ الإجراء يحمل حقلاً وزرَّين، فيأخذ ضعفَ غيره: حقلُ سببٍ بعرض
          ستين بكسلاً يُكتب فيه سطرٌ لا يُقرأ منه شيء */}
      <Table
        toolbar={
          <TableSearch
            value={search.text}
            onChange={search.setText}
            placeholder="اسمُ أحد الطرفين أو رقمُه…"
          />
        }
        searching={search.searching}
        noResults={NO_RESULTS}
        columns="0.8fr 1.1fr 0.9fr 0.8fr 0.7fr 2.6fr"
        headers={["المبلغ", "على", "لصالح", "الحالة", "التاريخ", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{
          title: "لا رسوم إلغاء",
          hint: "يظهر هنا كل رسمٍ استُحقّ بعد قبول رحلةٍ ثم إلغائها.",
        }}
        render={(row) => (
          <>
            <span className="text-12 font-semibold text-ink">
              {money(row.amount, row.currency)}
            </span>
            <span className="text-12 text-ink">
              {/* **من عليه الآن**، لا من كان عليه: صفٌّ له حاملٌ سدَّده صاحبُه
                  نقداً، والمطلوبُ تحويلٌ من كبتنٍ — واسمُ الراكب هنا يوجّه
                  مطالبةً إلى من دفع */}
              {row.carrier_driver_id ? (
                <>
                  {row.carrier_name ?? "كبتن"}
                  <span className="block text-10.5 text-muted">
                    قبضه نقداً مع أجرة رحلة
                  </span>
                </>
              ) : (
                <>
                  {row.payer_name ?? "راكب"}
                  {row.payer_phone ? (
                    <span dir="ltr" className="block text-10.5 text-muted">
                      {row.payer_phone}
                    </span>
                  ) : null}
                </>
              )}
            </span>
            <span className="text-12 text-ink">
              {row.beneficiary_name ?? "كبتن"}
            </span>
            <span className="flex items-center gap-6">
              <Badge tone={TONE[row.status]}>{LABEL[row.status]}</Badge>
            </span>
            <span className="text-12 text-muted">{day(row.created_at)}</span>
            {row.status === "pending" ? (
              <div className="flex items-center gap-8">
                <Field
                  placeholder="السبب المكتوب"
                  value={reasons[row.id] ?? ""}
                  onChange={(event) =>
                    setReasons((current) => ({
                      ...current,
                      [row.id]: event.target.value,
                    }))
                  }
                />
                <Button
                  size="sm"
                  variant="secondary"
                  loading={busy === row.id}
                  onClick={() =>
                    void act(
                      row,
                      waiveCancellationCharge,
                      "سبب الإعفاء مطلوب — قرارٌ بلا سببٍ مكتوبٍ لا يُراجَع بعد شهر",
                    )
                  }
                >
                  إعفاء
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  loading={busy === row.id}
                  onClick={() =>
                    void act(
                      row,
                      writeOffCancellationCharge,
                      "سبب الشطب مطلوب — خسارةٌ بلا سببٍ مكتوبٍ لا يملكها أحد",
                    )
                  }
                >
                  شطب
                </Button>
              </div>
            ) : (
              <span className="text-11.5 text-muted">
                {row.waive_reason ?? row.writeoff_reason ?? "—"}
              </span>
            )}
          </>
        )}
      />

      <p className="mt-14 text-11.5 leading-note text-muted">
        الرسمُ <b className="text-ink">تعويضٌ للكبتن الذي تحرّك</b>، والمنصّةُ
        تنقله ولا تملكه. والإعفاءُ والشطبُ <b className="text-ink">لا يكتبان
        قيداً في الدفتر</b>: لم يتحرك مالٌ في محفظة أحد، وقيدٌ يقول «سُدِّد»
        يجعل الكشفَ يكذب على الطرفين. ومن قبض الرسمَ نقداً يظهر هنا حاملاً —
        فمطالبتُه هي المطالبة، لا مطالبةُ راكبٍ دفع.
      </p>
    </>
  );
}
