'use client';

import { useRouter } from 'next/navigation';
import { clearStoredHealthData, getPrivacyContext } from '@/src/lib/privacy';

export function ExitAssessmentButton({
  className = '',
  label = 'Exit',
}: {
  className?: string;
  label?: string;
}) {
  const router = useRouter();

  const handleExit = async () => {
    const privacy = getPrivacyContext();

    try {
      if (privacy) {
        await fetch('/api/privacy/exit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ privacy }),
        });
      }
    } catch {
      // Local clearance is the priority even if the server call fails.
    } finally {
      clearStoredHealthData();
      router.replace('/start');
    }
  };

  return (
    <button type="button" onClick={handleExit} className={className}>
      {label}
    </button>
  );
}
