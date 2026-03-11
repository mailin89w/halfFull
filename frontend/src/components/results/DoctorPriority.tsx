import type { Doctor } from '@/src/lib/mockResults';

interface Props {
  doctors: Doctor[];
}

const BADGE_STYLES: Record<string, string> = {
  'Start here': 'bg-[#EFB973]/20 text-[#254662]',
  'After initial labs': 'bg-[#EFD17B]/25 text-[#254662]',
  'Specialist referral': 'bg-[#EBC7BB]/30 text-[#254662]',
  'If GP flags sleep apnea': 'bg-[#A2B6CB]/20 text-[#254662]',
  'If standard results normal': 'bg-[#A2B6CB]/20 text-[#254662]',
};

function badgeStyle(badge: string): string {
  return BADGE_STYLES[badge] ?? 'bg-[#A2B6CB]/20 text-[#254662]';
}

export function DoctorPriority({ doctors }: Props) {
  return (
    <div className="bg-white rounded-3xl p-6 shadow-[0_4px_24px_rgba(37,70,98,0.08)] flex flex-col gap-5">
      <div>
        <h2 className="text-[#254662] font-semibold text-lg">Who to see — in order</h2>
        <p className="text-sm text-[#A2B6CB] mt-1">
          Start with your GP. Bring your report and the test list above — one appointment can unlock most of the answers.
        </p>
      </div>

      <div className="flex flex-col gap-4">
        {doctors.map((doc, i) => (
          <div key={doc.specialty} className="flex items-start gap-4">
            {/* Priority number */}
            <div className="w-8 h-8 rounded-full bg-[#EFB973] flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-[#254662] font-bold text-sm">{i + 1}</span>
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-base">{doc.icon}</span>
                <span className="font-semibold text-[#254662] text-sm">{doc.specialty}</span>
                <span
                  className={`text-[10px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${badgeStyle(doc.badge)}`}
                >
                  {doc.badge}
                </span>
              </div>
              <p className="text-xs text-[#A2B6CB] mt-1.5 leading-relaxed">{doc.reason}</p>
            </div>

            {/* Connector line (not on last item) */}
            {i < doctors.length - 1 && (
              <div className="absolute ml-4 mt-9 w-px h-4 bg-[#EFB973]/30" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
