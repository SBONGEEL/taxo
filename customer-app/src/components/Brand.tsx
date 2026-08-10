import { cn } from "@/lib/utils";

/** اسم التطبيق كما يفرضه SPEC القسم 1: **TAXO** في كل الواجهات. */
export function Brand({
  subtitle,
  className,
}: {
  subtitle?: string;
  className?: string;
}) {
  return (
    <div className={cn("space-y-2 text-center", className)}>
      <div className="mx-auto flex size-16 items-center justify-center rounded-2xl bg-brand">
        <span className="text-2xl font-bold tracking-tight text-brand-ink">T</span>
      </div>
      <h1 className="text-3xl font-bold tracking-tight text-ink">TAXO</h1>
      {subtitle ? <p className="text-sm text-muted">{subtitle}</p> : null}
    </div>
  );
}
