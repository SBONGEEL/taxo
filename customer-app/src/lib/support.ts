/** **واتسابُ الدعم لدولة المستخدم** (البند ٨، ٢٠٢٦-١١-١٠) — من اللوحة (`support_settings`)، **و`null` بلا رقمٍ = لا زرّ**. */
import { useEffect, useState } from "react";

import { supportContacts } from "@/api/endpoints";
import type { CountryCode } from "@/api/types";

export function useSupportWhatsapp(country: CountryCode | null | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!country) return;
    let alive = true;
    supportContacts(country)
      .then((row) => {
        if (alive) setUrl(row.whatsapp_number ? `https://wa.me/${row.whatsapp_number}` : null);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [country]);
  return url;
}
