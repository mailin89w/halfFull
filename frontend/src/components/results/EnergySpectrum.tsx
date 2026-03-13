'use client';

interface Props {
  currentPct: number;   // 0–100
  projectedPct: number; // 0–100
}

function energyLabel(pct: number): string {
  if (pct < 25) return 'Depleted';
  if (pct < 45) return 'Low energy';
  if (pct < 60) return 'Moderate';
  if (pct < 75) return 'Good energy';
  return 'Thriving';
}

interface BarProps {
  pct: number;
  title: string;
  variant: 'current' | 'projected';
}

function EnergyBar({ pct, title, variant }: BarProps) {
  const isCurrent = variant === 'current';

  const fillGradient = isCurrent
    ? 'linear-gradient(to top, #7a68f4 0%, #9d92ff 100%)'
    : 'linear-gradient(to top, #09090f 0%, #343a65 100%)';

  const scoreColor = '#09090f';

  return (
    <div className="flex flex-1 flex-col items-center gap-2.5">
      <p className="text-center text-[10px] font-semibold uppercase leading-tight tracking-[0.18em] text-[var(--color-ink-soft)]">
        {title}
      </p>

      <div className="flex items-baseline gap-0.5">
        <span className="editorial-display text-5xl leading-none" style={{ color: scoreColor }}>
          {pct}
        </span>
        <span className="text-sm font-medium text-[var(--color-ink-soft)]">%</span>
      </div>

      <div
        className="relative w-full overflow-hidden rounded-[1.7rem]"
        style={{
          height: 200,
          backgroundColor: '#edf0f8',
          boxShadow: 'inset 0 2px 8px rgba(86,98,145,0.08)',
        }}
      >
        {[25, 50, 75].map((tick) => (
          <div
            key={tick}
            className="absolute left-3 right-3 border-t border-white/80"
            style={{ bottom: `${tick}%` }}
          />
        ))}

        <div
          className="absolute bottom-0 left-0 right-0"
          style={{
            height: `${pct}%`,
            background: fillGradient,
            transition: 'height 0.8s cubic-bezier(0.34, 1.2, 0.64, 1)',
          }}
        />
      </div>

      <p className="text-xs font-semibold text-[var(--color-ink)]">{energyLabel(pct)}</p>
    </div>
  );
}

export function EnergySpectrum({ currentPct, projectedPct }: Props) {
  const delta = projectedPct - currentPct;

  return (
    <div className="section-card flex flex-col gap-5 p-6">
      <div>
        <h2 className="text-2xl font-bold tracking-[-0.04em] text-[var(--color-ink)]">
          Your energy picture
        </h2>
        <p className="mt-1 text-sm leading-6 text-[var(--color-ink-soft)]">
          These patterns are recoverable. The right interventions move most people
          significantly — often within months.
        </p>
      </div>

      <div className="flex items-stretch gap-3">
        <EnergyBar pct={currentPct} title="Where you are" variant="current" />

        <div className="flex flex-col items-center justify-center gap-2 shrink-0 pb-6">
          <div className="rounded-full bg-[var(--color-lime)] px-3 py-1 text-xs font-bold whitespace-nowrap text-[var(--color-ink)]">
            +{delta} pts
          </div>
          <span className="text-base leading-none text-[var(--color-ink-soft)]">→</span>
        </div>

        <EnergyBar pct={projectedPct} title="Your potential" variant="projected" />
      </div>
    </div>
  );
}
