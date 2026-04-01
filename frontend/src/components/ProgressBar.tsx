export interface ChapterModule {
  id: string;
  title: string;
  state: 'done' | 'active' | 'upcoming';
}

interface Props {
  progress: number; // 0-100
  currentIndex: number;
  total: number;
  modules?: ChapterModule[];
  currentModuleTitle?: string;
}

export function ProgressBar({
  progress,
  currentIndex,
  total,
  modules = [],
  currentModuleTitle,
}: Props) {
  return (
    <div className="flex flex-col gap-2">
      {/* Chapter label row */}
      <div className="flex items-baseline">
        <span className="text-[13px] font-bold tracking-[-0.01em] text-[var(--color-ink)]">
          {currentModuleTitle ?? `Question ${currentIndex + 1} of ${total}`}
        </span>
      </div>

      {/* Segmented chapter track - one block per chapter */}
      {modules.length > 0 ? (
        <div className="flex gap-[3px]">
          {modules.map((mod) => (
            <div
              key={mod.id}
              title={mod.title}
              className="h-[5px] flex-1 rounded-full transition-all duration-400"
              style={{
                backgroundColor:
                  mod.state === 'done'
                    ? '#7765f4'
                    : mod.state === 'active'
                      ? '#d7f068'
                      : 'rgba(255,255,255,0.55)',
                boxShadow:
                  mod.state === 'active'
                    ? '0 0 6px rgba(215,240,104,0.55)'
                    : 'none',
              }}
            />
          ))}
        </div>
      ) : (
        /* Fallback plain bar when no module data */
        <div className="h-[5px] overflow-hidden rounded-full bg-white/70">
          <div
            className="h-full rounded-full bg-[linear-gradient(90deg,#7765f4_0%,#d7f068_100%)] transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
}
