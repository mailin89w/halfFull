interface Props {
  progress: number; // 0–100
  currentIndex: number;
  total: number;
}

export function ProgressBar({ progress, currentIndex, total }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-between text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--color-ink-soft)]">
        <span>
          Question {currentIndex + 1} of {total}
        </span>
        <span>{Math.round(progress)}%</span>
      </div>
      <div className="h-3 rounded-full bg-white/70 p-[3px] shadow-[inset_0_1px_2px_rgba(86,98,145,0.1)]">
        <div
          className="h-full rounded-full bg-[linear-gradient(90deg,#7765f4_0%,#d7f068_100%)] transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
