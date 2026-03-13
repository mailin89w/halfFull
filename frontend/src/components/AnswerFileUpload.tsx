'use client';

import { useRef, useState, useEffect } from 'react';
import type { LabUploadAnswer } from '@/src/lib/types';

interface Props {
  value: LabUploadAnswer | undefined;
  onChange: (val: LabUploadAnswer) => void;
}

/** Reads a File as base64, returns just the data portion (no data URI prefix). */
function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(',')[1] ?? '');
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export function AnswerFileUpload({ value, onChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  // If a stale 'extracting' state was persisted from a previous session (page
  // reload mid-upload), the async fetch is gone and the UI is frozen.  Reset
  // it to 'error' on mount so the user can retry without clearing localStorage.
  useEffect(() => {
    if (value?.status === 'extracting') {
      onChange({
        ...value,
        status: 'error',
        errorMessage: 'Upload was interrupted — tap to try again.',
      });
    }
    // Run only on mount; intentionally omit deps to avoid infinite loop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFile = async (file: File) => {
    // 1. Immediate feedback — show "extracting" state
    onChange({ filename: file.name, extractedText: '', status: 'extracting' });

    try {
      const base64 = await fileToBase64(file);

      // 2. Send to /api/extract-labs
      const res = await fetch('/api/extract-labs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: file.name, base64, mimeType: file.type }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Network error' }));
        onChange({
          filename: file.name,
          extractedText: '',
          status: 'error',
          errorMessage: err.error ?? `Server error ${res.status}`,
        });
        return;
      }

      const { extractedText } = await res.json() as { extractedText: string };
      onChange({ filename: file.name, extractedText: extractedText ?? '', status: 'done' });
    } catch (err) {
      onChange({
        filename: file.name,
        extractedText: '',
        status: 'error',
        errorMessage: err instanceof Error ? err.message : String(err),
      });
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) void handleFile(file);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void handleFile(file);
    // Reset input so the same file can be re-uploaded after an error
    e.target.value = '';
  };

  const isExtracting = value?.status === 'extracting';
  const isDone = value?.status === 'done';
  const isError = value?.status === 'error';
  const hasFile = !!value?.filename;

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !isExtracting && inputRef.current?.click()}
      className={[
        'w-full rounded-[1.6rem] border border-dashed p-8',
        'flex flex-col items-center gap-3 transition-all',
        isExtracting ? 'cursor-wait' : 'cursor-pointer',
        dragging
          ? 'border-[var(--color-accent)] bg-[var(--color-accent-soft)]'
          : isDone
          ? 'border-[var(--color-lime)] bg-[rgba(215,240,104,0.08)]'
          : isError
          ? 'border-[rgba(239,100,100,0.5)] bg-[rgba(239,100,100,0.04)]'
          : hasFile
          ? 'border-[var(--color-accent)] bg-[var(--color-accent-soft)]'
          : 'border-[rgba(151,166,210,0.45)] bg-white',
      ].join(' ')}
    >
      {/* Icon area */}
      <div
        className={[
          'flex h-14 w-14 items-center justify-center rounded-full transition-colors',
          isDone
            ? 'bg-[var(--color-lime)]'
            : isError
            ? 'bg-[rgba(239,100,100,0.12)]'
            : isExtracting
            ? 'bg-[var(--color-accent-soft)]'
            : 'bg-[var(--color-lime)]',
        ].join(' ')}
      >
        {isExtracting ? (
          /* Spinner */
          <svg className="h-6 w-6 animate-spin text-[var(--color-accent)]" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        ) : isDone ? (
          /* Checkmark */
          <svg className="h-6 w-6 text-[var(--color-ink)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        ) : isError ? (
          /* Warning */
          <svg className="h-6 w-6 text-[rgba(200,60,60,0.9)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
        ) : (
          /* Upload arrow */
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="text-[var(--color-ink)]">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <polyline points="17 8 12 3 7 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <line x1="12" y1="3" x2="12" y2="15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        )}
      </div>

      {/* Status text */}
      {isExtracting && (
        <>
          <p className="text-sm font-semibold text-[var(--color-ink)]">{value.filename}</p>
          <p className="text-xs text-[var(--color-accent)]">Analyzing labs with MedGemma…</p>
        </>
      )}

      {isDone && (
        <>
          <p className="text-sm font-semibold text-[var(--color-ink)]">{value.filename}</p>
          <p className="text-xs font-medium text-[rgba(60,130,60,0.9)]">✓ Lab data extracted</p>
          <p className="text-[10px] text-[var(--color-ink-soft)]">Tap to replace</p>
        </>
      )}

      {isError && (
        <>
          <p className="text-sm font-semibold text-[var(--color-ink)]">{value.filename}</p>
          <p className="text-xs text-[rgba(200,60,60,0.9)]">
            {value.errorMessage ?? 'Could not extract labs'}
          </p>
          <p className="text-[10px] text-[var(--color-ink-soft)]">Tap to try again</p>
        </>
      )}

      {!hasFile && (
        <>
          <p className="text-sm font-medium text-[var(--color-ink)]">Drag and drop or tap to upload</p>
          <p className="text-xs text-[var(--color-ink-soft)]">PDF, JPG, or PNG — MedGemma will read your values</p>
        </>
      )}

      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png"
        className="hidden"
        onChange={handleInputChange}
      />
    </div>
  );
}
