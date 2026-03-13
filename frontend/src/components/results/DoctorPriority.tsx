import type { Doctor } from '@/src/lib/mockResults';

interface Props {
  doctors: Doctor[];
}

const BADGE_STYLES: Record<string, string> = {
  'Start here': 'bg-[var(--color-lime)] text-[var(--color-ink)]',
  'After initial labs': 'bg-[var(--color-accent-soft)] text-[var(--color-ink)]',
  'Specialist referral': 'bg-[rgba(158,169,211,0.25)] text-[var(--color-ink)]',
  'If GP flags sleep apnea': 'bg-[rgba(158,169,211,0.25)] text-[var(--color-ink)]',
  'If standard results normal': 'bg-[rgba(158,169,211,0.25)] text-[var(--color-ink)]',
};

function badgeStyle(badge: string): string {
  return BADGE_STYLES[badge] ?? 'bg-[rgba(158,169,211,0.25)] text-[var(--color-ink)]';
}

export function DoctorPriority({ doctors }: Props) {
  return (
    <div className="section-card flex flex-col gap-5 p-6">
      <div>
        <h2 className="text-2xl font-bold tracking-[-0.04em] text-[var(--color-ink)]">Who to see — in order</h2>
        <p className="mt-1 text-sm leading-6 text-[var(--color-ink-soft)]">
          Start with your GP. Bring your report and the test list above — one appointment can unlock most of the answers.
        </p>
      </div>

      <div className="relative flex flex-col gap-4">
        {doctors.map((doc, i) => (
          <div key={doc.specialty} className="flex items-start gap-4">
            <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[#09090f]">
              <span className="text-sm font-bold text-white">{i + 1}</span>
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-base">{doc.icon}</span>
                <span className="text-sm font-semibold text-[var(--color-ink)]">{doc.specialty}</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-semibold whitespace-nowrap ${badgeStyle(doc.badge)}`}
                >
                  {doc.badge}
                </span>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-[var(--color-ink-soft)]">{doc.reason}</p>
            </div>

            {i < doctors.length - 1 && (
              <div className="absolute ml-4 mt-9 h-4 w-px bg-[rgba(9,9,15,0.14)]" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
