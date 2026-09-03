interface BarDatum {
  label: string;
  value: number;
}

interface MiniBarChartProps {
  data: BarDatum[];
  height?: number;
  colorVar?: string; // e.g. "--chart-1"
}

/** Lightweight hand-rolled SVG bar chart — no charting library dependency. */
export function MiniBarChart({ data, height = 96, colorVar = "--chart-1" }: MiniBarChartProps) {
  const max = Math.max(1, ...data.map((d) => d.value));

  return (
    <div>
      <div className="flex items-end gap-2" style={{ height }}>
        {data.map((datum) => {
          const barHeight = Math.max(2, (datum.value / max) * height);
          return (
            <div key={datum.label} className="flex flex-1 flex-col items-center justify-end gap-1">
              <span className="text-[10px] tabular-nums text-muted-foreground">{datum.value}</span>
              <div
                className="w-full rounded-t-sm transition-all"
                style={{ height: barHeight, backgroundColor: `hsl(var(${colorVar}))` }}
                title={`${datum.label}: ${datum.value}`}
              />
            </div>
          );
        })}
      </div>
      <div className="mt-1.5 flex gap-2">
        {data.map((datum) => (
          <span key={datum.label} className="flex-1 truncate text-center text-[10px] text-muted-foreground">
            {datum.label}
          </span>
        ))}
      </div>
    </div>
  );
}
