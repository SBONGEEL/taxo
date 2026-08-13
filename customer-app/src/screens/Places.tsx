/** الأماكن المحفوظة — الصفحة الكاملة (`FUTURE-FEATURES` بند 1).
 *
 * قائمةٌ بأماكنه وزرُّ إضافةٍ وتعديلٌ لكل صف. و**الإحداثيات تأتي من الرئيسية
 * لا من هنا**: اختيارُ نقطةٍ يحتاج خريطةً، وخريطةٌ ثانية في هذه الصفحة تعني
 * مكوّنَ خريطةٍ ثالثاً في التطبيق. فالإضافةُ تحفظ **الوجهة الأخيرة** أو
 * تُعدَّل نقطتُها من الرئيسية لاحقاً — والاسمُ والأيقونة يُحرَّران هنا.
 *
 * **ولا حذفَ بلا تأكيد**: مكانٌ يُحذف بضغطةٍ واحدة يُحذف بالخطأ، وإعادتُه
 * تعني تحديدَ نقطةٍ على خريطةٍ من جديد.
 */

import { House, Briefcase, MapPin, Star, Trash2 } from "lucide-react";
import { useState } from "react";

import { ApiError } from "@/api/client";
import { createPlace, deletePlace, updatePlace } from "@/api/endpoints";
import type { PlaceIcon, SavedPlace } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, EmptyState } from "@/components/ui/Feedback";
import { Screen } from "@/components/ui/Screen";
import { Stagger, StaggerItem } from "@/components/ui/Motion";
import { usePlaces, type RecentDestination } from "@/lib/places";
import { cn } from "@/lib/utils";

const ICONS: { value: PlaceIcon; label: string; Mark: typeof House }[] = [
  { value: "home", label: "المنزل", Mark: House },
  { value: "work", label: "العمل", Mark: Briefcase },
  { value: "star", label: "مكان", Mark: Star },
];

function Mark({ icon }: { icon: string }) {
  const found = ICONS.find((option) => option.value === icon) ?? ICONS[2];
  return <found.Mark className="size-20 shrink-0 text-brand" />;
}

export function PlacesScreen() {
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
    <Screen title="الأماكن المحفوظة" back="/account" nav>
      <div className="space-y-16">
        <ErrorNote message={error} />

        {places.length === 0 ? (
          <EmptyState
            title="لا أماكن محفوظة بعد"
            hint="احفظ وجهةً من رحلاتك الأخيرة أدناه، فتصير ضغطةً واحدة في المرة القادمة"
          />
        ) : (
          <Stagger className="space-y-8">
            {places.map((place) => (
              <StaggerItem key={place.id} className="card p-16">
                {editing?.id === place.id ? (
                  <PlaceForm
                    initial={place}
                    busy={busy}
                    onCancel={() => setEditing(null)}
                    onSave={(label, icon) =>
                      void run(() => updatePlace(place.id, { label, icon }))
                    }
                  />
                ) : (
                  <div className="flex items-center gap-12">
                    <Mark icon={place.icon} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-ink">{place.label}</p>
                      <p className="truncate text-14 text-muted">
                        {place.address ?? "نقطة على الخريطة"}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setEditing(place)}
                      className="text-14 font-medium text-ink underline"
                    >
                      تعديل
                    </button>
                    <ConfirmDelete
                      busy={busy}
                      onConfirm={() => void run(() => deletePlace(place.id))}
                    />
                  </div>
                )}
              </StaggerItem>
            ))}
          </Stagger>
        )}

        {/* الإضافةُ من الوجهات الأخيرة: نقطةٌ سبق أن ذهب إليها — فلا حاجة
            إلى خريطةٍ ثانية في هذه الصفحة */}
        {recents.length > 0 ? (
          <section>
            <p className="mb-8 text-12 text-muted">احفظ من وجهاتك الأخيرة</p>
            {naming ? (
              /* **الاسمُ يُسأل قبل الحفظ لا بعده**: عنوانٌ كاملٌ اسماً
                 («شارع … ، عمّان، الأردن») لا يُقرأ اختصاراً على الرئيسية،
                 وحفظُ مكانين بلا اسمٍ يصطدم بقيد التفرّد */
              <div className="card mb-8 p-16">
                <p className="mb-10 truncate text-14 text-muted">
                  {naming.address}
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

            <Stagger className="space-y-8">
              {/* المزوّدُ يُخرج المحفوظَ من «الأخيرة» أصلاً — فلا تصفيةَ هنا */}
              {recents.map((recent) => (
                  <StaggerItem key={recent.key} className="card flex items-center gap-12 p-16">
                    <MapPin className="size-20 shrink-0 text-muted" />
                    <span className="min-w-0 flex-1 truncate text-14 text-ink">
                      {recent.address}
                    </span>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => setNaming(recent)}
                      className="text-14 font-medium text-brand underline disabled:opacity-50"
                    >
                      احفظ
                    </button>
                  </StaggerItem>
              ))}
            </Stagger>
          </section>
        ) : null}
      </div>
    </Screen>
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
  const [label, setLabel] = useState(initial.label);
  const [icon, setIcon] = useState<PlaceIcon>(
    (ICONS.find((option) => option.value === initial.icon)?.value ?? "star") as PlaceIcon,
  );

  return (
    <div className="space-y-12">
      <input
        className="field"
        value={label}
        maxLength={60}
        onChange={(event) => setLabel(event.target.value)}
        placeholder="اسم المكان"
      />
      <div className="grid grid-cols-3 gap-8">
        {ICONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setIcon(option.value)}
            className={cn(
              "flex items-center justify-center gap-6 rounded-12 border p-10 text-14",
              option.value === icon
                ? "border-brand bg-brand-soft text-ink"
                : "border-line text-muted",
            )}
          >
            <option.Mark className="size-16" />
            {option.label}
          </button>
        ))}
      </div>
      <div className="flex gap-8">
        <Button
          size="md"
          className="flex-1"
          loading={busy}
          disabled={label.trim().length === 0}
          onClick={() => onSave(label.trim(), icon)}
        >
          حفظ
        </Button>
        <Button size="md" variant="ghost" className="flex-1" onClick={onCancel}>
          إلغاء
        </Button>
      </div>
    </div>
  );
}

/** ضغطتان لا واحدة — والثانيةُ تقول «تأكيد» صراحةً. */
function ConfirmDelete({
  busy,
  onConfirm,
}: {
  busy: boolean;
  onConfirm: () => void;
}) {
  const [armed, setArmed] = useState(false);

  if (!armed) {
    return (
      <button
        type="button"
        aria-label="حذف"
        onClick={() => setArmed(true)}
        className="text-danger"
      >
        <Trash2 className="size-18" />
      </button>
    );
  }
  return (
    <span className="flex items-center gap-8">
      <button
        type="button"
        disabled={busy}
        onClick={onConfirm}
        className="text-14 font-medium text-danger underline disabled:opacity-50"
      >
        تأكيد
      </button>
      <button
        type="button"
        onClick={() => setArmed(false)}
        className="text-14 text-muted"
      >
        تراجع
      </button>
    </span>
  );
}
