/** **«أضف مكاناً» و«اقترح تصحيحاً»** (أمرُ المالك ٢٠٢٦-١١-١٨ السابع، المهمّة ٢-٣) — يصل طابورَ المراجعة في اللوحة،
 *  **ولا يظهر على الخريطة إلا بعد الموافقة** (ويُقال ذلك هنا للمستخدم). الموضعُ وسطُ الخريطة أو المكانُ الملموس. */
import { useState } from "react";

import { api } from "@/api/client";
import { tr } from "@/lib/i18n";
import { SheetModalT2 } from "@/screens/t2/MoneyT2";

const CATEGORIES: [string, string][] = [
  ["shop", "محلّ"], ["market", "سوق"], ["mall", "مركز تسوّق"], ["restaurant", "مطعم"], ["mosque", "مسجد"], ["hospital", "مستشفى"],
  ["clinic", "عيادة / صيدلية"], ["school", "مدرسة"], ["university", "جامعة"], ["hotel", "فندق"], ["government", "دائرة حكومية"],
  ["landmark", "معلم"], ["station", "محطة"], ["other", "غير ذلك"],
];

export interface SuggestTarget {
  kind: "add" | "fix";
  lat: number;
  lng: number;
  currentName?: string;
}

export function PlaceSuggestSheet({ target, onClose }: { target: SuggestTarget; onClose: () => void }) {
  const [name, setName] = useState(target.kind === "fix" ? target.currentName ?? "" : "");
  const [category, setCategory] = useState("shop");
  const [note, setNote] = useState("");
  const [state, setState] = useState<"edit" | "sending" | "sent" | "failed">("edit");

  async function send() {
    if (name.trim().length < 2) return;
    setState("sending");
    try {
      await api.post("/map/suggestions", {
        kind: target.kind,
        name_ar: name.trim(),
        category,
        lat: target.lat,
        lng: target.lng,
        current_name: target.currentName ?? null,
        note: note.trim() || null,
      });
      setState("sent");
    } catch {
      setState("failed");
    }
  }

  if (state === "sent") {
    return (
      <SheetModalT2 onClose={onClose}>
        <div className="t2-picker-title">{tr("وصل اقتراحك، شكراً")}</div>
        <p className="t2-sheet-note">{tr("يراجعه فريقُ TAXO، ويظهر على الخريطة بعد الموافقة.")}</p>
        <button type="button" className="t2-button primary" onClick={onClose}>
          {tr("تمّ")}
        </button>
      </SheetModalT2>
    );
  }
  return (
    <SheetModalT2 onClose={onClose}>
      <div className="t2-picker-title">{target.kind === "add" ? tr("أضف مكاناً") : tr("اقترح تصحيحاً")}</div>
      {target.kind === "fix" && target.currentName ? (
        <p className="t2-sheet-note">
          {tr("الاسمُ على الخريطة الآن:")} {target.currentName}
        </p>
      ) : (
        <p className="t2-sheet-note">{tr("المكانُ في وسط الخريطة. حرّك الخريطةَ قبل الفتح لتغييره.")}</p>
      )}
      <input
        className="t2-input"
        dir="auto"
        maxLength={80}
        value={name}
        placeholder={tr("الاسمُ الصحيح بالعربيّة")}
        onChange={(event) => setName(event.target.value)}
      />
      <div className="t2-suggest-cats" role="radiogroup" aria-label={tr("النوع")}>
        {CATEGORIES.map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={category === value}
            className={category === value ? "t2-sg-chip on" : "t2-sg-chip"}
            onClick={() => setCategory(value)}
          >
            {tr(label)}
          </button>
        ))}
      </div>
      <input
        className="t2-input"
        dir="auto"
        maxLength={300}
        value={note}
        placeholder={tr("ملاحظة (اختياري)")}
        onChange={(event) => setNote(event.target.value)}
      />
      {state === "failed" ? <p className="t2-sheet-note">{tr("تعذّر الإرسال، حاول ثانيةً")}</p> : null}
      <button type="button" className="t2-button primary" disabled={state === "sending" || name.trim().length < 2} onClick={() => void send()}>
        {tr("أرسل للمراجعة")}
      </button>
      <p className="t2-sheet-note">{tr("لا يظهر شيءٌ على الخريطة قبل موافقة فريق TAXO، ولا يظهر اسمُك.")}</p>
    </SheetModalT2>
  );
}
