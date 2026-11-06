/** **أفي سوق الكبتن صرفٌ عبر كليك؟** (٢٠٢٦-١١-٠٦) — حقلُ «حساب CliQ للسحب» كان يظهر لكبتن الجزائر، وكليك أردنيٌّ لا يعرفه
 * بنكُه. **ومرآةُ `withdrawals.METHODS_BY_COUNTRY` في الخلفية** — جدولٌ مفتاحُه `CountryCode` فيُجبر المترجمُ اكتمالَه يومَ
 * يُضاف سوق. **ولا يُقرأ من `/wallet/me`**: الكبتنُ في التسجيل لم تُفتح محفظتُه بعد. */

import type { CountryCode } from "@/api/types";

const CLIQ_PAYOUT: Record<CountryCode, boolean> = { JO: true, LY: true, DZ: false };

export function hasCliqPayout(country: CountryCode | null | undefined): boolean {
  return country ? CLIQ_PAYOUT[country] : true;
}
