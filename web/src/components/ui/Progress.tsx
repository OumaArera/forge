import { cn } from "@/lib/cn";

/**
 * A completion bar.
 *
 * `value` is a percentage. It is announced to assistive technology as a
 * progressbar with its real numbers, because a bare coloured strip conveys
 * nothing to a screen reader and this is the main signal of how a project is
 * going.
 */
export function Progress({
  value,
  label,
  tone = "brand",
  className,
  showValue,
}: {
  value: number;
  label?: string;
  tone?: "brand" | "ember" | "green";
  className?: string;
  showValue?: boolean;
}) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  const fill = {
    brand: "bg-brand-600",
    ember: "bg-ember-500",
    green: "bg-emerald-500",
  }[tone];

  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label ?? "Progress"}
        className="flex-1 h-2 rounded-full bg-sunken overflow-hidden"
      >
        <div
          className={cn("h-full rounded-full transition-[width] duration-500", fill)}
          style={{ width: `${clamped}%` }}
        />
      </div>
      {showValue ? (
        <span className="text-xs font-semibold text-muted tabular-nums shrink-0">
          {clamped}%
        </span>
      ) : null}
    </div>
  );
}

/**
 * A ring showing one number against a total.
 *
 * Used for the contribution summary, where the mockup has a donut. Drawn as
 * an SVG rather than pulled from a charting library: it is one arc, and a
 * charting dependency for one arc is 40 kB a student pays for on a metered
 * connection.
 */
export function ProgressRing({
  value,
  max,
  size = 104,
  label,
  sublabel,
}: {
  value: number;
  max: number;
  size?: number;
  label?: string;
  sublabel?: string;
}) {
  const stroke = 9;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const fraction = max > 0 ? Math.min(value / max, 1) : 0;

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
          className="stroke-sunken"
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - fraction)}
          className="stroke-brand-600 transition-[stroke-dashoffset] duration-700"
          fill="none"
        />
      </svg>
      <div className="absolute inset-0 grid place-content-center text-center">
        <span className="text-xl font-bold text-strong leading-none tabular-nums">
          {label ?? value}
        </span>
        {sublabel ? (
          <span className="text-[10px] text-muted mt-1">{sublabel}</span>
        ) : null}
      </div>
    </div>
  );
}
