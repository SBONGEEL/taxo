/** **فتحُ إيصال PDF** (SPEC §٨٨/٢) — الرابطُ قصيرُ العمر من الخلفية يُفتح في المتصفّح فيُنزَّل الملفّ؛ **ولا ملفَّ يُكتب في التطبيق**. */

import { AppLauncher } from "@capacitor/app-launcher";

export async function openReceiptUrl(url: string): Promise<void> {
  try {
    await AppLauncher.openUrl({ url });
  } catch {
    // **غلافٌ بلا `AppLauncher`** (المتصفّح) — نافذةٌ جديدة
    window.open(url, "_blank", "noopener");
  }
}
