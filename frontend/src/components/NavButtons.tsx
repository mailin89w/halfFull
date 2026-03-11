interface Props {
  isFirst: boolean;
  isLast: boolean;
  canAdvance: boolean;
  onBack: () => void;
  onNext: () => void;
}

export function NavButtons({ isFirst, isLast, canAdvance, onBack, onNext }: Props) {
  return (
    <div className="flex gap-3">
      {!isFirst && (
        <button
          onClick={onBack}
          className={[
            'flex-1 py-4 rounded-2xl',
            'border-2 border-[#A2B6CB]/40',
            'text-[#254662] font-semibold text-base',
            'hover:border-[#254662]/30 transition-all active:scale-[0.98]',
          ].join(' ')}
        >
          ← Back
        </button>
      )}

      <button
        onClick={onNext}
        disabled={!canAdvance}
        className={[
          'flex-1 py-4 rounded-2xl font-semibold text-base transition-all',
          canAdvance
            ? 'bg-[#EFB973] text-[#254662] hover:bg-[#e8ae62] active:scale-[0.98] shadow-sm'
            : 'bg-[#A2B6CB]/20 text-[#A2B6CB] cursor-not-allowed',
        ].join(' ')}
      >
        {isLast ? 'See my results →' : 'Next →'}
      </button>
    </div>
  );
}
