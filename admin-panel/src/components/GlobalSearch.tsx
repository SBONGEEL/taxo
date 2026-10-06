/** البحثُ العامُّ في رأس اللوحة — **يقفز ولا يعرض صفحةَ نتائج** (§39٫١٢٫٤).
 *
 * **الشرطُ بنصِّه**: «بحثٌ عامٌّ واحدٌ في رأس اللوحة يقفز إلى مستخدمٍ أو كبتنٍ
 * أو رحلةٍ أو مطالبةٍ بالرقم أو الاسم أو المرجع».
 *
 * ## ولا مكوّنَ درجٍ ثانٍ — **`Picker` هو البيت**
 *
 * الدرجُ هنا هو درجُ `Picker` حرفاً: حدُّ الحرفين، ومهلةُ ٢٥٠ملّي، وطرحُ جوابٍ
 * متأخّرٍ عن بحثٍ سابق، وسطران لكلِّ نتيجة. **ونسخةٌ ثانيةٌ منه كانت تفترق عنه
 * أوّلَ تعديل** (§39٫١٢٫٨).
 *
 * **و`value` تبقى `null` أبداً**: هذا ليس حقلَ نموذجٍ يحمل مختاراً — **الاختيارُ
 * فيه فعلٌ لا قيمة**، فيقفز ويترك الحقلَ كما كان.
 *
 * ## والوجهةُ تُقرأ من `kind` لا تُخمَّن من شكل المعرّف
 *
 * **أربعتُها UUID**، فمعرّفُ كبتنٍ ومعرّفُ حسابٍ لا يفترقان بالنظر —
 * **والخلطُ يفتح ملفَّ إنسانٍ آخر ولا يصيح شيء**. والخلفيةُ تقول الصنفَ في كلِّ
 * إصابة.
 */

import { useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";

import { globalSearch } from "@/api/endpoints";
import type { RideStatus, SearchHit } from "@/api/types";
import { Picker, type PickerOption } from "@/components/ui/Picker";
import { RIDE_STATUS_LABEL, SEARCH_KIND_LABEL } from "@/lib/labels";
import { Icon } from "@/taxo2";

/** أيقونةُ الصنف في سطر النتيجة — **زينةٌ بجانب الكلمة لا بدلاً منها**: الصنفُ مكتوبٌ في السطر الثاني كما كان. */
const KIND_ICON: Record<SearchHit["kind"], string> = {
  user: "person",
  driver: "badge",
  ride: "route",
  claim: "receipt_long",
};

/** السطرُ الثاني لكلِّ إصابة — **وكلُّ اسمٍ من السجلّ المركزيّ**.
 *
 * **العطبُ الذي أوجب هذه الدالّة أمسكته جولةُ متصفّحٍ لا عدٌّ من الشيفرة**
 * (٢٠٢٦-٠٩-٠٤): الرحلةُ كانت تُعرض «رحلة · completed» — **حالٌ خامٌ
 * بالإنجليزية على شاشةٍ عربية**، لأن الخلفيةَ ترسل `status.value` والواجهةُ
 * كانت تمرّره كما هو. و`RIDE_STATUS_LABEL` مبنيٌّ منذ زمنٍ في `labels.ts`،
 * **فلم ينقص إلا وصلُه**.
 */
function describe(hit: SearchHit): string {
  const kind = SEARCH_KIND_LABEL[hit.kind];
  if (hit.hint === null) return kind;
  const hint =
    hit.kind === "ride"
      ? (RIDE_STATUS_LABEL[hit.hint as RideStatus] ?? hit.hint)
      : hit.hint;
  // **القيمةُ معزولةٌ باتّجاهها** (`\u2066…\u2069`): رقمٌ يبدأ بـ«+» في سطرٍ عربيّ كان يُقرأ «962790000012+»
  return `${kind} · \u2066${hint}\u2069`;
}

export function GlobalSearch() {
  const navigate = useNavigate();
  /** **الإصاباتُ بمعرّفها** — `Picker` يردّ سطرَ عرضٍ، **والوجهةُ في `kind`**. */
  const hitsById = useRef(new Map<string, SearchHit>());

  const search = useCallback(async (query: string): Promise<PickerOption[]> => {
    const { hits } = await globalSearch(query);
    hitsById.current = new Map(hits.map((hit) => [hit.id, hit]));
    return hits.map((hit) => ({
      id: hit.id,
      // **معرّفُ الرحلة مقصوصٌ كما في سجلّها** (`Rides.tsx::shortId`): درجٌ
      // فيه خمسةُ معرّفاتٍ من ٣٦ خانةً لا يُقرأ، **والكاملُ يبقى في `id`**
      // فالقفزةُ تحمله سليماً.
      label: hit.kind === "ride" ? hit.id.slice(0, 8) : hit.label,
      // **الصنفُ في السطر الثاني لا في أيقونة**: «كبتن · 07…» يُقرأ بلا
      // مفتاحِ ألوانٍ يحفظه أحد، **والأسماءُ من السجلّ المركزيّ**
      hint: describe(hit),
      icon: KIND_ICON[hit.kind],
    }));
  }, []);

  function jump(option: PickerOption | null) {
    if (option === null) return;
    const hit = hitsById.current.get(option.id);
    if (hit === undefined) return;

    switch (hit.kind) {
      case "user":
        // **يُفتح بمعرّفه لا ببحثٍ عنه**: `GET /admin/users/{id}` بابٌ قائم،
        // **وحسابٌ خارج الصفحة الأولى كان لا يُفتح أبداً** لو اعتمدنا القائمة
        navigate(`/riders?open=${hit.id}`);
        break;
      case "driver":
        // **ومعه رقمُه في `q`**: لا بابَ يقرأ كبتناً واحداً بصفِّ القائمة،
        // **فيُضيَّق البحثُ برقمه** ثم يُفتح صفُّه بمعرّفه
        navigate(
          `/drivers?open=${hit.id}&q=${encodeURIComponent(hit.hint ?? "")}`,
        );
        break;
      case "ride":
        navigate(`/rides?open=${hit.id}&q=${hit.id}`);
        break;
      case "claim":
        navigate(
          `/finance?tab=topups&q=${encodeURIComponent(hit.label)}`,
        );
        break;
    }
  }

  return (
    // **حقلٌ واحدٌ بأيقونة البحث** — عرضُه ٤٠٠ في ترويسة الحاسوب، **وسطرٌ كاملٌ تحت ١٠٢٤** (الإطار `frame.css`)
    <div className="ad-search">
      <Icon name="search" className="ad-search-icon" />
      <Picker
        value={null}
        onPick={jump}
        search={search}
        placeholder="ابحث في اللوحة كلِّها — اسمٌ أو رقمٌ أو مرجع…"
        emptyText="لا حسابَ ولا كبتنَ ولا رحلةَ ولا مطالبةَ بهذا النصّ."
        ariaLabel="البحث العامّ"
      />
    </div>
  );
}
