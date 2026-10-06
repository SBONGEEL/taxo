/** الأماكن المحفوظة — TAXO 2.0 «R24» (`design/t2-new/rider/R24-places.dc.html` · `R24b-…` · `R24c-…`)، **في المظهرين
 *  والنسائيّ** — لوحةٌ جديدةٌ من عائلة R15 (`FUTURE-FEATURES` بند 1).
 *
 * قائمةٌ بأماكنه وزرُّ إضافةٍ وتعديلٌ لكل صف. و**الإحداثيات تأتي من الرئيسية
 * لا من هنا**: اختيارُ نقطةٍ يحتاج خريطةً، وخريطةٌ ثانية في هذه الصفحة تعني
 * مكوّنَ خريطةٍ ثالثاً في التطبيق. فالإضافةُ تحفظ **الوجهة الأخيرة** أو
 * تُعدَّل نقطتُها من الرئيسية لاحقاً — والاسمُ والأيقونة يُحرَّران هنا.
 *
 * **ولا حذفَ بلا تأكيد**: مكانٌ يُحذف بضغطةٍ واحدة يُحذف بالخطأ، وإعادتُه
 * تعني تحديدَ نقطةٍ على خريطةٍ من جديد.
 *
 * **والمنطقُ هو هو حرفاً** (`POST`/`PATCH`/`DELETE /me/places` ثمّ إعادةُ القراءة من `PlacesProvider`)؛ **وما تغيّر طبقةُ
 * العرض**: صفوفٌ في بطاقة بمربّع أيقونةٍ بالجمر الخافت، والنموذجُ بحقل الهوية واختيارِ R03.
 */

import { useId, useState } from "react";

import { ApiError } from "@/api/client";
import { createPlace, deletePlace, updatePlace } from "@/api/endpoints";
import type { PlaceIcon, SavedPlace } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { usePlaces, type RecentDestination } from "@/lib/places";
import { BlankT2, NoteT2, SubHeadT2 } from "@/screens/t2/KitT2";
import { AuthBlock, AuthInput, Icon } from "@/taxo2";

import "@/screens/t2/t2.css";
import "@/screens/t2/account.css";

const ICONS: { value: PlaceIcon; label: string; icon: string }[] = [
  { value: "home", label: "المنزل", icon: "home" },
  { value: "work", label: "العمل", icon: "work" },
  { value: "star", label: "مكان", icon: "star" },
];

/** أيقونةُ المكان — و**المجهولُ نجمة** لا فراغ: نوعٌ جديد في الخلفية يظهر بشكلٍ محايد بدل أن يختفي الصف. */
function markOf(icon: string): string {
  return (ICONS.find((option) => option.value === icon) ?? ICONS[2]).icon;
}

export function PlacesScreen() {
  const goBack = useGoBack("/account");
  const { places, recents, refresh } = usePlaces();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<SavedPlace | null>(null);
  const [naming, setNaming] = useState<RecentDestination | null>(null);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await refresh();
      setEditing(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="t2 t2-page pb-nav">
      <SubHeadT2 title="الأماكن المحفوظة" onBack={goBack} />

      {error ? (
        <NoteT2 tone="danger" lead>
          {error}
        </NoteT2>
      ) : null}

      {places.length === 0 ? (
        <BlankT2
          icon="bookmark"
          title="لا أماكن محفوظة بعد"
          hint="احفظ وجهةً من رحلاتك الأخيرة أدناه، فتصير ضغطةً واحدة في المرة القادمة"
        />
      ) : (
        <div className="t2-list">
          {places.map((place) =>
            editing?.id === place.id ? (
              <div key={place.id} className="t2-plc form">
                <PlaceForm
                  initial={place}
                  busy={busy}
                  onCancel={() => setEditing(null)}
                  onSave={(label, icon) => void run(() => updatePlace(place.id, { label, icon }))}
                />
              </div>
            ) : (
              <div key={place.id} className="t2-plc">
                <span className="t2-plc-mark">
                  <Icon name={markOf(place.icon)} fill />
                </span>
                <div className="t2-plc-main">
                  <p className="t2-plc-label">{place.label}</p>
                  <p className="t2-plc-addr">{place.address ?? "نقطة على الخريطة"}</p>
                </div>
                <button type="button" className="t2-tlink" onClick={() => setEditing(place)}>
                  تعديل
                </button>
                <ConfirmDelete busy={busy} onConfirm={() => void run(() => deletePlace(place.id))} />
              </div>
            ),
          )}
        </div>
      )}

      {/* الإضافةُ من الوجهات الأخيرة: نقطةٌ سبق أن ذهب إليها — فلا حاجة
          إلى خريطةٍ ثانية في هذه الصفحة */}
      {recents.length > 0 ? (
        <section>
          <div className="t2-section">احفظ من وجهاتك الأخيرة</div>
          {naming ? (
            /* **الاسمُ يُسأل قبل الحفظ لا بعده**: عنوانٌ كاملٌ اسماً
               («شارع … ، عمّان، الأردن») لا يُقرأ اختصاراً على الرئيسية،
               وحفظُ مكانين بلا اسمٍ يصطدم بقيد التفرّد */
            <div className="t2-list t2-plc-naming">
              <p className="t2-plc-naming-addr">
                <Icon name="location_on" />
                <span>{naming.address}</span>
              </p>
              <PlaceForm
                initial={{ label: "", icon: "star" }}
                busy={busy}
                onCancel={() => setNaming(null)}
                onSave={(label, icon) =>
                  void run(async () => {
                    await createPlace({
                      label,
                      lat: naming.point.lat,
                      lng: naming.point.lng,
                      address: naming.address,
                      icon,
                    });
                    setNaming(null);
                  })
                }
              />
            </div>
          ) : null}

          {/* المزوّدُ يُخرج المحفوظَ من «الأخيرة» أصلاً — فلا تصفيةَ هنا */}
          <div className="t2-list">
            {recents.map((recent) => (
              <div key={recent.key} className="t2-recent">
                <Icon name="location_on" />
                <span className="t2-recent-addr">{recent.address}</span>
                <button type="button" className="t2-tlink accent" disabled={busy} onClick={() => setNaming(recent)}>
                  احفظ
                </button>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function PlaceForm({
  initial,
  busy,
  onSave,
  onCancel,
}: {
  /** اسمٌ وأيقونة لا غير — النموذجُ نفسه للتعديل وللتسمية قبل الحفظ. */
  initial: { label: string; icon: string };
  busy: boolean;
  onSave: (label: string, icon: PlaceIcon) => void;
  onCancel: () => void;
}) {
  const id = useId();
  const [label, setLabel] = useState(initial.label);
  const [icon, setIcon] = useState<PlaceIcon>(
    (ICONS.find((option) => option.value === initial.icon)?.value ?? "star") as PlaceIcon,
  );

  return (
    <div className="t2-plc-form">
      <AuthBlock label="اسم المكان" htmlFor={id}>
        <AuthInput id={id} value={label} maxLength={60} onChange={(event) => setLabel(event.target.value)} />
      </AuthBlock>
      {/* **اختيارُ R03 بأيقونة كلِّ خيار** — الأيقونةُ هي ما يُختار هنا */}
      <div className="t2-auth-choice" role="group" aria-label="أيقونة المكان">
        {ICONS.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={option.value === icon}
            onClick={() => setIcon(option.value)}
          >
            <Icon name={option.icon} />
            <span>{option.label}</span>
          </button>
        ))}
      </div>
      <div className="t2-idcard-row">
        <button
          type="button"
          className="t2-cbtn ink grow"
          disabled={busy || label.trim().length === 0}
          aria-busy={busy}
          onClick={() => onSave(label.trim(), icon)}
        >
          حفظ
        </button>
        <button type="button" className="t2-cbtn soft grow" onClick={onCancel}>
          إلغاء
        </button>
      </div>
    </div>
  );
}

/** ضغطتان لا واحدة — والثانيةُ تقول «تأكيد» صراحةً. */
function ConfirmDelete({ busy, onConfirm }: { busy: boolean; onConfirm: () => void }) {
  const [armed, setArmed] = useState(false);

  if (!armed) {
    return (
      <button type="button" aria-label="حذف" className="t2-ibtn destroy" onClick={() => setArmed(true)}>
        <Icon name="delete" />
      </button>
    );
  }
  return (
    <span className="t2-plc-confirm">
      <button type="button" className="t2-tlink destroy" disabled={busy} onClick={onConfirm}>
        تأكيد
      </button>
      <button type="button" className="t2-tlink muted" onClick={() => setArmed(false)}>
        تراجع
      </button>
    </span>
  );
}
