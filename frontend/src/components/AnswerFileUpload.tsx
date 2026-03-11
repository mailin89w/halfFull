'use client';

import { useRef, useState } from 'react';

interface Props {
  value: string | undefined;
  onChange: (val: string) => void;
}

export function AnswerFileUpload({ value, onChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string>(value ?? '');
  const [dragging, setDragging] = useState(false);

  const handleFile = (file: File) => {
    setFileName(file.name);
    onChange(file.name);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={[
        'w-full border-2 border-dashed rounded-2xl p-8',
        'flex flex-col items-center gap-3 cursor-pointer transition-all',
        dragging || fileName
          ? 'border-[#EFB973] bg-[#EFB973]/5'
          : 'border-[#A2B6CB]/60 hover:border-[#EFB973] hover:bg-[#EFB973]/5',
      ].join(' ')}
    >
      {/* Upload icon */}
      <div className="w-12 h-12 rounded-full bg-[#A2B6CB]/20 flex items-center justify-center">
        <svg
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          className={fileName ? 'text-[#EFB973]' : 'text-[#A2B6CB]'}
        >
          <path
            d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <polyline
            points="17 8 12 3 7 8"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <line
            x1="12" y1="3" x2="12" y2="15"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      </div>

      {fileName ? (
        <>
          <p className="text-[#254662] font-medium text-sm">{fileName}</p>
          <p className="text-[#A2B6CB] text-xs">Tap to replace</p>
        </>
      ) : (
        <>
          <p className="text-[#254662] font-medium text-sm">Drag & drop or tap to upload</p>
          <p className="text-[#A2B6CB] text-xs">PDF, JPG, or PNG</p>
        </>
      )}

      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />
    </div>
  );
}
