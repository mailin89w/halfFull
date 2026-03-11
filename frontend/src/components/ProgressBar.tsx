interface Props {
  progress: number; // 0–100
  currentIndex: number;
  total: number;
}

export function ProgressBar({ progress, currentIndex, total }: Props) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between text-xs text-[#A2B6CB] font-medium">
        <span>
          Question {currentIndex + 1} of {total}
        </span>
        <span>{Math.round(progress)}%</span>
      </div>
      <div className="h-1.5 bg-[#A2B6CB]/25 rounded-full overflow-hidden">
        <div
          className="h-full bg-[#EFB973] rounded-full transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
