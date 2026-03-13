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
            'flex-1 rounded-full border px-5 py-4',
            'border-[rgba(9,9,15,0.16)] bg-white/75',
            'text-[var(--color-ink)] font-bold text-base',
            'transition-all active:scale-[0.98]',
          ].join(' ')}
        >
          Back
        </button>
      )}

      <button
        onClick={onNext}
        disabled={!canAdvance}
        className={[
          'flex-1 rounded-full px-5 py-4 font-bold text-base transition-all',
          canAdvance
            ? 'bg-[#09090f] text-white active:scale-[0.98] shadow-[0_10px_24px_rgba(9,9,15,0.22)]'
            : 'bg-white/50 text-[rgba(9,9,15,0.34)] cursor-not-allowed',
        ].join(' ')}
      >
        {isLast ? 'See my results' : 'Next'}
      </button>
    </div>
  );
}
