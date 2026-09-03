interface DonutSegment {
  label: string;
  value: number;
  colorVar: string; // e.g. "--success"
}

interface MiniDonutProps {
  segments: DonutSegment[];
  size?: number;
  strokeWidth?: number;
  centerLabel?: string;
  centerValue?: string;
}

/**
 * Lightweight hand-rolled SVG donut chart — no charting library dependency.
 * Renders each segment as a stroke-dasharray arc; a screen-reader-only
 * table beneath the SVG carries the same data as accessible text.
 */
export function MiniDonut({ segments, size = 120, strokeWidth = 14, centerLabel, centerValue }: MiniDonutProps) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="flex items-center gap-4">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="hsl(var(--muted))"
            strokeWidth={strokeWidth}
          />
          {total > 0 &&
            segments.map((segment) => {
              if (segment.value <= 0) return null;
              const fraction = segment.value / total;
              const dash = fraction * circumference;
              const dashArray = `${dash} ${circumference - dash}`;
              const currentOffset = offset;
              offset += dash;
              return (
                <circle
                  key={segment.label}
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="none"
                  stroke={`hsl(var(${segment.colorVar}))`}
                  strokeWidth={strokeWidth}
                  strokeDasharray={dashArray}
                  strokeDashoffset={-currentOffset}
                  strokeLinecap="butt"
                />
              );
            })}
        </svg>
        {(centerLabel || centerValue) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            {centerValue && <span className="text-lg font-semibold tabular-nums">{centerValue}</span>}
            {centerLabel && <span className="text-[10px] text-muted-foreground">{centerLabel}</span>}
          </div>
        )}
      </div>
      <ul className="flex flex-1 flex-col gap-1.5">
        {segments.map((segment) => (
          <li key={segment.label} className="flex items-center justify-between gap-3 text-xs">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: `hsl(var(${segment.colorVar}))` }}
                aria-hidden="true"
              />
              {segment.label}
            </span>
            <span className="font-medium tabular-nums">{segment.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
