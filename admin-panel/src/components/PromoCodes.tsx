/** جدولُ رموز الخصم — SPEC القسم 6.6/13، المرحلة 12-ز.
 *
 * يسكن أسفلَ «الإشعارات الجماعية» لأن القسمَ في القسم 13 واحد: «العروض
 * والحملات». وهما شيئان مختلفان في نفس الصفحة، فلكلٍّ عنوانُه.
 *
 * **وثلاثةُ أرقامٍ لا رقم**: `budget_total` سقفُ الحملة، و`spent` ما دُفع فعلاً
 * (دفعاتُ `promo` المؤكَّدة)، و`committed` ما دُفع **ومعه ما وُعد به في رحلاتٍ
 * جارية** — وهو ما يُقاس به السقف. **ويُعرض `committed` كما هو ولو تجاوز
 * السقف**: السقفُ يمنع تطبيقاً جديداً لا رحلةً تحمل الرمز، ورقمٌ مقصوصٌ عنده
 * يجعل المشرفَ يظنه صارماً فيفاجئه تقريرُ الكلفة.
 *
 * **وجملةُ «تتحمّلها الشركة» نصٌّ لا عمود** (شرطُ المالك): القيمةُ واحدةٌ لا
 * تحتمل غيرها اليوم، وعمودٌ بقيمةٍ واحدةٍ ممكنة هو نفسُ ما حُذف من جدول
 * البقشيش. ويومَ يظهر متحمّلٌ ثانٍ يصير الحقلُ عموداً وهذه الجملةُ قيمتَه.
 *
 * **ولا حذفَ لرمزٍ استُعمل**: الخلفيةُ ترفضه (`409`)، والشاشةُ لا تعرض الزرَّ
 * أصلاً — فالمشرفُ يقرأ «أطفئه» قبل أن يجرّب لا بعده.
 */

import { Ban, TicketPercent, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  createPromoCode,
  deletePromoCode,
  listPromoCodes,
  updatePromoCode,
} from "@/api/endpoints";
import type { CountryCode, PromoCode } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field, Select } from "@/components/ui/Field";
import { EmptyNote, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Modal } from "@/components/ui/Modal";
import { currencyLabel, day, money } from "@/lib/format";
import { useCountry } from "@/lib/country";
import { useSession } from "@/lib/session";
import { arabicDigits, cn } from "@/lib/utils";

const TYPE_LABEL: Record<PromoCode["discount_type"], string> = {
  percent: "نسبة",
  fixed: "مبلغ ثابت",
};

/** **رمزُ العملة لا تسميتُها**: `money()` هي التي تحوّل الرمزَ إلى «د.أ»
 *  (`format.ts`)، فتمريرُ التسمية إليها يجعلها تبحث عن «د.أ» في جدول الرموز
 *  فلا تجدها — فتُطبع المبالغُ **بلا عملةٍ أصلاً**. وهو ما وقع فعلاً حتى
 *  قُرئ عقدُ الدالة. والتسميةُ وحدها تُطلب صريحةً حيث يلزم نصُّها. */
function codeOf(country: CountryCode): "JOD" | "LYD" {
  return country === "JO" ? "JOD" : "LYD";
}

function labelOf(country: CountryCode): string {
  return currencyLabel(codeOf(country));
}

/** قيمةُ الخصم كما تُقرأ: «٥٠٪ حتى ٢ د.أ» أو «١ د.أ». */
function describe(row: PromoCode, country: CountryCode): string {
  if (row.discount_type === "percent") {
    const cap = row.max_discount
      ? ` حتى ${money(row.max_discount, codeOf(country))}`
      : " حتى كامل الأجرة";
    // **بلا أصفار النقدية**: النسبةُ تأتي `NUMERIC(12,3)` أي «50.000»، وطبعُها
    // كما هي يقرأ «٥٠.٠٠٠٪». وهي نسبةٌ لا مبلغ، فتُقصّ أصفارُها الزائدة
    const percent = row.discount_value.replace(/\.?0+$/, "");
    return `${arabicDigits(percent)}٪${cap}`;
  }
  return money(row.discount_value, codeOf(country));
}

export function PromoCodes({ onError }: { onError: (message: string) => void }) {
  const { country } = useCountry();
  const { isAdmin } = useSession();
  const [rows, setRows] = useState<PromoCode[] | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try {
      setRows(await listPromoCodes(country));
    } catch (caught) {
      onError(caught instanceof ApiError ? caught.message : "تعذّر قراءة الرموز");
    }
    // `onError` يتبدّل مرجعياً في كل تصيير — وربطُه هنا يعيد التحميل بلا داعٍ
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [country]);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(action: () => Promise<unknown>) {
    try {
      await action();
      await load();
    } catch (caught) {
      onError(caught instanceof ApiError ? caught.message : "تعذّر الإجراء");
    }
  }

  return (
    <section className="mt-16 rounded-16 border border-line bg-surface p-18">
      <div className="mb-4 flex items-start justify-between gap-12">
        <div>
          <h2 className="flex items-center gap-8 text-14 font-bold text-ink">
            <TicketPercent size={16} />
            رموز الخصم
          </h2>
          <p className="mt-4 text-11 leading-snug text-muted">
            <b className="text-ink">تتحمّلها الشركة</b> — الخصمُ لا يُنقص أرباح
            الكبتن ولا عمولتَه: يُقيَّد دفعةً على الرحلة باسم المنصة، فيقبض
            الكبتنُ أجرتَه كاملةً. والسقفُ يمنع تطبيقاً جديداً حين تنفد
            الميزانية، ولا يقطع رحلةً تحمل الرمز — فقد يتجاوزه «الملتزم» قليلاً.
          </p>
        </div>
        {isAdmin ? (
          <Button
            size="sm"
            className="w-auto flex-none px-14"
            onClick={() => setCreating(true)}
          >
            + رمز جديد
          </Button>
        ) : null}
      </div>

      {rows === null ? (
        <Spinner className="mx-auto my-24" />
      ) : rows.length === 0 ? (
        <EmptyNote
          title="لا رموز في هذا السوق"
          hint="الرمزُ حملةٌ بميزانية — يُنشأ هنا ويظهر للركّاب فور تفعيل مفتاح الكوبونات."
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-12.5">
            <thead className="text-11 text-muted">
              <tr className="border-b border-line">
                <th className="p-8 text-start">الرمز</th>
                <th className="p-8 text-start">الخصم</th>
                <th className="p-8 text-start">الميزانية</th>
                <th className="p-8 text-start">الملتزم / المدفوع</th>
                <th className="p-8 text-start">الاستعمال</th>
                <th className="p-8 text-start">حتى</th>
                <th className="p-8 text-start">الحالة</th>
                <th className="p-8" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const over = Number(row.committed) > Number(row.budget_total);
                return (
                  <tr key={row.id} className="border-b border-line last:border-0">
                    <td dir="ltr" className="p-8 font-bold text-ink">
                      {row.code}
                    </td>
                    <td className="p-8 text-ink">
                      {describe(row, row.country_code)}
                      <span className="ms-6 text-10.5 text-muted">
                        {TYPE_LABEL[row.discount_type]}
                      </span>
                    </td>
                    <td className="p-8 text-ink">
                      {money(row.budget_total, codeOf(row.country_code))}
                    </td>
                    <td className={cn("p-8", over ? "text-warn" : "text-ink")}>
                      {money(row.committed, codeOf(row.country_code))}
                      <span className="text-muted">
                        {" / "}
                        {money(row.spent, codeOf(row.country_code))}
                      </span>
                    </td>
                    <td className="p-8 text-ink">
                      {arabicDigits(String(row.used_count))}
                      <span className="text-muted">
                        {" · لكل راكب "}
                        {arabicDigits(String(row.per_user_limit))}
                      </span>
                    </td>
                    <td className="p-8 text-muted">
                      {row.valid_until ? day(row.valid_until) : "—"}
                    </td>
                    <td className="p-8">
                      <Badge tone={row.is_active ? "ok" : "muted"}>
                        {row.is_active ? "مفعّل" : "مطفأ"}
                      </Badge>
                    </td>
                    <td className="p-8">
                      {isAdmin ? (
                        <div className="flex justify-end gap-8">
                          <button
                            type="button"
                            title={row.is_active ? "أطفئه" : "أعد تفعيله"}
                            onClick={() =>
                              void act(() =>
                                updatePromoCode(row.id, {
                                  is_active: !row.is_active,
                                }),
                              )
                            }
                            className="text-muted hover:text-ink"
                          >
                            <Ban size={14} />
                          </button>
                          {/* الحذفُ لغير المستعمل وحده — والخلفيةُ ترفض غيره */}
                          {row.used_count === 0 ? (
                            <button
                              type="button"
                              title="احذفه"
                              onClick={() =>
                                void act(() => deletePromoCode(row.id))
                              }
                              className="text-muted hover:text-danger"
                            >
                              <Trash2 size={14} />
                            </button>
                          ) : null}
                        </div>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {creating ? (
        <NewPromoModal
          country={country}
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            void load();
          }}
          onError={onError}
        />
      ) : null}
    </section>
  );
}

function NewPromoModal({
  country,
  onClose,
  onCreated,
  onError,
}: {
  country: CountryCode;
  onClose: () => void;
  onCreated: () => void;
  onError: (message: string) => void;
}) {
  const [code, setCode] = useState("");
  const [type, setType] = useState<PromoCode["discount_type"]>("percent");
  const [value, setValue] = useState("");
  const [cap, setCap] = useState("");
  const [budget, setBudget] = useState("");
  const [perUser, setPerUser] = useState("1");
  const [until, setUntil] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const money = (raw: string) => raw.replace(/[^0-9.]/g, "");

  return (
    <Modal onClose={onClose} title="رمز خصم جديد">
      <Field
        label="الرمز"
        id="promo-code"
        dir="ltr"
        placeholder="WELCOME"
        value={code}
        // يُطبَّع في الخلفية أيضاً — وهذا كي يرى المشرف ما سيُخزَّن
        onChange={(event) => setCode(event.target.value.toUpperCase())}
      />

      <div className="mt-12 grid grid-cols-2 gap-10">
        <Select
          label="نوع الخصم"
          id="promo-type"
          value={type}
          onChange={(event) =>
            setType(event.target.value as PromoCode["discount_type"])
          }
        >
          <option value="percent">نسبة ٪</option>
          <option value="fixed">مبلغ ثابت</option>
        </Select>
        <Field
          label={type === "percent" ? "النسبة ٪" : `المبلغ (${labelOf(country)})`}
          id="promo-value"
          dir="ltr"
          inputMode="decimal"
          value={value}
          onChange={(event) => setValue(money(event.target.value))}
        />
      </div>

      {type === "percent" ? (
        <div className="mt-12">
          <Field
            label={`سقف الخصم (${labelOf(country)}) — اتركه فارغاً لكامل الأجرة`}
            id="promo-cap"
            dir="ltr"
            inputMode="decimal"
            value={cap}
            onChange={(event) => setCap(money(event.target.value))}
          />
          <p className="mt-6 text-11 leading-snug text-muted">
            بلا سقفٍ يبتلع كوبونُ ٥٠٪ رحلةً طويلة. واتركه فارغاً عن قصدٍ وحده —
            «الرحلة الأولى مجاناً» نسبةُ ١٠٠٪ بلا سقف.
          </p>
        </div>
      ) : null}

      <div className="mt-12 grid grid-cols-2 gap-10">
        <Field
          label={`ميزانية الحملة (${labelOf(country)})`}
          id="promo-budget"
          dir="ltr"
          inputMode="decimal"
          value={budget}
          onChange={(event) => setBudget(money(event.target.value))}
        />
        <Field
          label="حد الاستعمال لكل راكب"
          id="promo-per-user"
          dir="ltr"
          inputMode="numeric"
          value={perUser}
          onChange={(event) =>
            setPerUser(event.target.value.replace(/[^0-9]/g, ""))
          }
        />
      </div>

      <div className="mt-12">
        <Field
          label="ينتهي في (اختياري)"
          id="promo-until"
          type="date"
          dir="ltr"
          value={until}
          onChange={(event) => setUntil(event.target.value)}
        />
      </div>

      <div className="mt-14">
        <ErrorNote message={error} />
      </div>

      <Button
        className="mt-14"
        loading={busy}
        disabled={code.trim().length < 2 || !value || !budget}
        onClick={() => {
          setBusy(true);
          setError(null);
          createPromoCode({
            code: code.trim(),
            country_code: country,
            discount_type: type,
            discount_value: value,
            max_discount: type === "percent" && cap ? cap : null,
            budget_total: budget,
            per_user_limit: Number(perUser || "1"),
            // منتصفُ الليل بتوقيت الجهاز يكفي: الخلفيةُ تقارن لحظةً بلحظة
            valid_until: until ? `${until}T23:59:59` : null,
          })
            .then(onCreated)
            .catch((caught) => {
              const message =
                caught instanceof ApiError ? caught.message : "تعذّر الإنشاء";
              setError(message);
              onError(message);
            })
            .finally(() => setBusy(false));
        }}
      >
        أنشئ الرمز
      </Button>
    </Modal>
  );
}
