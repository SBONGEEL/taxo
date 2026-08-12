/** القائمة: مدخل بقية الشاشات (SPEC القسم 11.6–11.8). */

import { ChevronLeft, Clock, CreditCard, MapPin, User, Wallet } from "lucide-react";
import { Link } from "react-router-dom";

import { Screen } from "@/components/ui/Screen";
import { useSession } from "@/lib/session";

const ITEMS = [
  { to: "/rides", icon: Clock, label: "رحلاتي", hint: "السجل والتفاصيل" },
  { to: "/wallet", icon: Wallet, label: "محفظتي", hint: "الرصيد والشحن والسجل" },
  { to: "/places", icon: MapPin, label: "الأماكن المحفوظة", hint: "المنزل والعمل وغيرهما" },
  { to: "/cards", icon: CreditCard, label: "بطاقاتي", hint: "الدفع بضغطة" },
  { to: "/profile", icon: User, label: "الملف الشخصي", hint: "بياناتك وإشعاراتك" },
];

export function MenuScreen() {
  const { user } = useSession();

  return (
    <Screen title="القائمة" back="/">
      <div className="space-y-16">
        <div className="card flex items-center gap-12 p-16">
          <div className="flex size-48 items-center justify-center rounded-full bg-brand-soft text-18 font-bold text-ink">
            {user?.name.slice(0, 1) ?? "?"}
          </div>
          <div className="min-w-0">
            <p className="truncate font-semibold text-ink">{user?.name}</p>
            <p dir="ltr" className="text-14 text-muted">
              {user?.phone}
            </p>
          </div>
        </div>

        <ul className="space-y-8">
          {ITEMS.map(({ to, icon: Icon, label, hint }) => (
            <li key={to}>
              <Link
                to={to}
                className="card flex items-center gap-12 p-16 transition hover:bg-surface-2"
              >
                <Icon className="size-20 text-ink" />
                <span className="flex-1">
                  <span className="block font-medium text-ink">{label}</span>
                  <span className="block text-12 text-muted">{hint}</span>
                </span>
                <ChevronLeft className="size-16 text-muted" />
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </Screen>
  );
}
