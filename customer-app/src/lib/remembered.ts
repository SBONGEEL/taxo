/** **الدخولُ المتذكَّر** (أمرُ المالك ٢٠٢٦-١١-٠٢، SPEC §60-ج) — رقمُ آخرِ من دخل ودولتُه، **فتفتح شاشةُ الدخول بعد الخروج عليهما**.
 *
 * **رقمٌ ودولةٌ لا غير — ولا كلمةَ مرورٍ بحال**، لا صريحةً ولا مشفَّرة. والرقمُ ليس سرّاً يفتح شيئاً: من يحمل الهاتفَ يراه في
 * شاشة الدخول كما كان صاحبُه يكتبه. **ويُمحى** بـ«الدخول بحساب آخر» وحدَه — لا بالخروج، فذاك هو ما يُتذكَّر له.
 */

import type { CountryCode } from "@/api/types";

const KEY = "taxo.remembered.login";

export interface RememberedLogin {
  /** بصيغته الدولية كما تعيده الخلفية (`+9627…`). */
  phone: string;
  country: CountryCode;
}

export function rememberLogin(value: RememberedLogin): void {
  try {
    localStorage.setItem(KEY, JSON.stringify({ phone: value.phone, country: value.country }));
  } catch {
    // مخزنٌ ممتلئٌ أو محظور: التذكّرُ راحةٌ لا شرط
  }
}

export function rememberedLogin(): RememberedLogin | null {
  try {
    const held = JSON.parse(localStorage.getItem(KEY) ?? "null") as Partial<RememberedLogin> | null;
    return held && typeof held.phone === "string" && typeof held.country === "string"
      ? { phone: held.phone, country: held.country as CountryCode }
      : null;
  } catch {
    return null;
  }
}

export function forgetRememberedLogin(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // لا شيءَ يُفعل: الغيابُ هو المقصود
  }
}
