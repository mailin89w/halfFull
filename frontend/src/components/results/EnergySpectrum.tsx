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
    ? 'linear-gradient(to top, #1E3A52 0%, #4E7A9E 100%)'
    : 'linear-gradient(to top, #EFB973 0%, #C7D9A7 100%)';

  const scoreColor = isCurrent ? '#254662' : '#6A9A4A';

  return (
    <div className="flex-1 flex flex-col items-center gap-2.5">
      {/* Title */}
      <p className="text-[10px] font-semibold tracking-widest uppercase text-[#A2B6CB] text-center leading-tight">
        {title}
      </p>

      {/* Score */}
      <div className="flex items-baseline gap-0.5">
        <span className="text-4xl font-bold leading-none" style={{ color: scoreColor }}>
          {pct}
        </span>
        <span className="text-sm font-medium text-[#A2B6CB]">/100</span>
      </div>

      {/* Bar track */}
      <div
        className="w-full rounded-2xl overflow-hidden relative"
        style={{
          height: 200,
          backgroundColor: '#F0F4F8',
          boxShadow: 'inset 0 2px 8px rgba(37,70,98,0.08)',
        }}
      >
        {/* Subtle tick marks */}
        {[25, 50, 75].map((tick) => (
          <div
            key={tick}
            className="absolute left-2.5 right-2.5 border-t border-white/70"
            style={{ bottom: `${tick}%` }}
          />
        ))}

        {/* Fill */}
        <div
          className="absolute bottom-0 left-0 right-0"
          style={{
            height: `${pct}%`,
            background: fillGradient,
            transition: 'height 0.8s cubic-bezier(0.34, 1.2, 0.64, 1)',
          }}
        />
      </div>

      {/* Energy label */}
      <p className="text-xs font-semibold text-[#254662]">{energyLabel(pct)}</p>
    </div>
  );
}

export function EnergySpectrum({ currentPct, projectedPct }: Props) {
  const delta = projectedPct - currentPct;

  return (
    <div className="bg-white rounded-3xl p-6 shadow-[0_4px_24px_rgba(37,70,98,0.08)] flex flex-col gap-5">
      {/* Header */}
      <div>
        <h2 className="text-[#254662] font-semibold text-lg leading-snug">
          Your energy picture
        </h2>
        <p className="text-sm text-[#A2B6CB] mt-1 leading-relaxed">
          These patterns are recoverable. The right interventions move most people
          significantly — often within months.
        </p>
      </div>

      {/* Bars */}
      <div className="flex items-stretch gap-3">
        <EnergyBar pct={currentPct} title="Where you are" variant="current" />

        {/* Delta connector */}
        <div className="flex flex-col items-center justify-center gap-2 shrink-0 pb-6">
          <div
            className="px-2.5 py-1 rounded-full text-xs font-bold whitespace-nowrap"
            style={{
              backgroundColor: 'rgba(199,217,167,0.35)',
              color: '#4E7A3A',
            }}
          >
            +{delta} pts
          </div>
          <span className="text-[#A2B6CB] text-base leading-none">→</span>
        </div>

        <EnergyBar pct={projectedPct} title="Your potential" variant="projected" />
      </div>
    </div>
  );
}
