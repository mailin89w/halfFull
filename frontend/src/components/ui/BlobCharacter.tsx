interface Props {
  className?: string;
  accent?: 'purple' | 'lime';
  mood?: 'joyful' | 'gentle';
}

export function BlobCharacter({ className, accent = 'purple', mood = 'joyful' }: Props) {
  const accentColor = accent === 'lime' ? '#d7f068' : '#7765f4';
  const gentle = mood === 'gentle';

  return (
    <svg
      viewBox="0 0 180 160"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M88 23c18 0 31 11 38 27 8 2 16 9 18 22 2 14-5 24-17 27 0 24-14 43-40 43-21 0-38-14-44-35-15 0-27-10-27-25 0-16 12-27 27-29 4-18 19-30 45-30Z"
        fill="#08080D"
      />
      <path
        d="M59 146c15-12 46-12 62 0"
        stroke="#9ea9d3"
        strokeWidth="4"
        strokeLinecap="round"
      />
      <path
        d={gentle ? 'M49 87c-12 7-20 17-23 29' : 'M49 83c-15 6-24 16-28 31'}
        stroke="#08080D"
        strokeWidth="6"
        strokeLinecap="round"
      />
      <path
        d={gentle ? 'M132 89c12 7 19 17 22 30' : 'M132 85c15 6 23 17 27 32'}
        stroke="#08080D"
        strokeWidth="6"
        strokeLinecap="round"
      />
      <path
        d={gentle ? 'M56 117c1 13-2 23-9 29' : 'M56 117c2 15-1 25-10 31'}
        stroke="#08080D"
        strokeWidth="6"
        strokeLinecap="round"
      />
      <path
        d={gentle ? 'M121 117c-1 13 2 23 9 29' : 'M121 117c-2 15 1 25 10 31'}
        stroke="#08080D"
        strokeWidth="6"
        strokeLinecap="round"
      />
      <circle cx="74" cy="69" r="5" fill="#fff" />
      <circle cx="103" cy="69" r="5" fill="#fff" />
      {gentle ? (
        <>
          <path d="M71 71c2-4 6-4 8 0" stroke="#08080D" strokeWidth="2.8" strokeLinecap="round" />
          <path d="M100 71c2-4 6-4 8 0" stroke="#08080D" strokeWidth="2.8" strokeLinecap="round" />
        </>
      ) : (
        <>
          <circle cx="75" cy="70" r="2.5" fill="#08080D" />
          <circle cx="104" cy="70" r="2.5" fill="#08080D" />
        </>
      )}
      <path
        d={gentle ? 'M75 92c8 5 18 5 26 0' : 'M73 91c10 8 22 8 32 0'}
        stroke="#fff"
        strokeWidth={gentle ? 3.2 : 4}
        strokeLinecap="round"
      />
      <path
        d="M33 35l7-13 7 13 13 5-13 5-7 13-7-13-13-5 13-5Z"
        fill={accentColor}
      />
    </svg>
  );
}
