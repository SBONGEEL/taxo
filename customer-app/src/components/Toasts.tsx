/** ما يصل والتطبيق مفتوح — يُعرض داخل الشاشة.
 *
 * الخلفية **لا ترسل Push لجهازٍ سوكته نشط** (SPEC القسم 10)، والمتصفح لا يعرض
 * ما يصل عبر `onMessage` والصفحةُ مفتوحة. فهذه هي القناة الوحيدة التي يرى بها
 * المستخدم الحدثَ وهو ينظر إلى الشاشة.
 */

import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";

import { useRide } from "@/lib/ride";

export function Toasts() {
  const { toasts, dismissToast } = useRide();

  return (
    <div className="pointer-events-none fixed inset-x-0 top-0 z-[60] mx-auto flex max-w-lg flex-col gap-8 px-16 pt-safe">
      <AnimatePresence initial={false}>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: -16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            className="pointer-events-auto flex items-start gap-8 rounded-12 border border-line bg-surface px-16 py-12 shadow-lg"
          >
            <div className="min-w-0 flex-1">
              <p className="font-medium text-ink">{toast.title}</p>
              {toast.body ? (
                <p className="mt-2 text-14 text-muted">{toast.body}</p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => dismissToast(toast.id)}
              className="pressable rounded-8 p-4 text-muted transition hover:bg-surface-2"
              aria-label="إغلاق"
            >
              <X className="size-16" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
