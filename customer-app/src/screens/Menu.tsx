/** القائمة: مدخل بقية الشاشات (SPEC القسم 11.6–11.8). */

import { ChevronLeft, Clock, CreditCard, User, Wallet } from "lucide-react";
import { Link } from "react-router-dom";

import { Screen } from "@/components/ui/Screen";
import { useSession } from "@/lib/session";

const ITEMS = [
  { to: "/rides", icon: Clock, label: "رحلاتي", hint: "السجل والتفاصيل" },
  { to: "/wallet", icon: Wallet, label: "محفظتي", hint: "الرصيد والشحن والسجل" },
  { to: "/cards", icon: CreditCard, label: "بطاقاتي", hint: "الدفع بضغطة" },
  { to: "/profile", icon: User, label: "الملف الشخصي", hint: "بياناتك وإشعاراتك" },
];

export function MenuScreen() {
  const { user } = useSession();

  return (
    <Screen title="القائمة" back="/">
      <div className="space-y-4">
        <div className="card flex items-center gap-3 p-4">
          <div className="flex size-12 items-center justify-center rounded-full bg-brand/20 text-lg font-bold text-ink">
            {user?.name.slice(0, 1) ?? "?"}
          </div>
          <div className="min-w-0">
            <p className="truncate font-semibold text-ink">{user?.name}</p>
            <p dir="ltr" className="text-sm text-muted">
              {user?.phone}
            </p>
          </div>
        </div>

        <ul className="space-y-2">
          {ITEMS.map(({ to, icon: Icon, label, hint }) => (
            <li key={to}>
              <Link
                to={to}
                className="card flex items-center gap-3 p-4 transition hover:bg-line/20"
              >
                <Icon className="size-5 text-ink" />
                <span className="flex-1">
                  <span className="block font-medium text-ink">{label}</span>
                  <span className="block text-xs text-muted">{hint}</span>
                </span>
                <ChevronLeft className="size-4 text-muted" />
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </Screen>
  );
}
