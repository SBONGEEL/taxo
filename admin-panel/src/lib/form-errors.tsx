/** خطأُ الحقل في اللوحة — SPEC القسم ١٧.٧.
 *
 * **الوسمُ بالاسم لا بخريطةٍ تُكتب في كل شاشة.** الخلفيةُ ترجع `field` باسمِه في
 * المخطط، والحقلُ يعلن `name` بذلك الاسم — فيجد الخطأُ حقلَه وحدَه. وخريطةٌ
 * `{حقلُ الخلفية → حقلُ الشاشة}` في كل شاشةٍ تفترق عن شاشتها أوّلَ تعديل، وشاشةُ
 * الإعدادات وحدَها فيها ثمانيةٌ وثلاثون حقلاً.
 *
 * **ولا يُخترع نصّ**: ما يُعرض تحت الحقل هو `message` كما كتبته الخلفية.
 *
 * **وحقلٌ بلا `name` لا يُوسَم ولا يُكذَب عليه**: يبقى الخطأُ في شريط النموذج كما
 * كان. فوسمُ حقلٍ بالتخمين أسوأُ من لا وسم — حدٌّ أحمرُ على الحقل الخطأ يرسل
 * صاحبَه يصحّح ما ليس معطوباً.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

import { ApiError } from "@/api/client";

interface FieldError {
  field: string;
  message: string;
}

const FormErrorContext = createContext<FieldError | null>(null);

export function FormErrors({
  value,
  children,
}: {
  value: FieldError | null;
  children: ReactNode;
}) {
  return (
    <FormErrorContext.Provider value={value}>
      {children}
    </FormErrorContext.Provider>
  );
}

/** رسالةُ هذا الحقل إن كان هو المرفوض — يقرؤها `Field` بنفسه. */
export function useFieldError(name: string | undefined): string | null {
  const current = useContext(FormErrorContext);
  if (!name || !current || current.field !== name) return null;
  return current.message;
}

/** حالةُ الخطأ لشاشةٍ واحدة: نصٌّ عام + حقلٌ مرفوض.
 *
 * **والنصُّ العامُّ يُعرض دائماً**، ويُضاف الوسمُ حين تسمّي الخلفيةُ حقلاً:
 * إخفاءُ الشريط عند وجود حقلٍ يترك من مرّر الشاشةَ بسرعةٍ بلا أثرٍ ظاهر، وشاشةُ
 * اللوحة طويلةٌ قد يكون الحقلُ خارج المرأى.
 */
export function useFormError() {
  const [message, setMessage] = useState<string | null>(null);
  const [field, setField] = useState<FieldError | null>(null);

  const capture = useCallback((caught: unknown, fallback: string) => {
    if (caught instanceof ApiError) {
      setMessage(caught.message);
      const name = caught.field("field");
      if (name) {
        setField({ field: name, message: caught.message });
        document
          .querySelector<HTMLElement>(`[name="${name}"]`)
          ?.focus({ preventScroll: false });
      } else {
        setField(null);
      }
      return;
    }
    setMessage(fallback);
    setField(null);
  }, []);

  const clear = useCallback(() => {
    setMessage(null);
    setField(null);
  }, []);

  return useMemo(
    () => ({ message, field, capture, clear, setMessage }),
    [message, field, capture, clear],
  );
}
