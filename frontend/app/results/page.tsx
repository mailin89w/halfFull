'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { jsPDF as JsPDFType } from 'jspdf';
import { useAssessment } from '@/src/hooks/useAssessment';
import { ML_THRESHOLD } from '@/src/lib/mlConfig';
import {
  computeConfidence,
  computeUrgency,
  extractBiomarkerSnapshot,
  type ConfidenceAssessment,
  type UrgencyAssessment,
} from '@/src/lib/clinicalSignals';
import { computeResults, buildDiagnosesFromML } from '@/src/lib/mockResults';
import {
  getInsightForDiagnosis,
  readStoredBayesianScores,
  readStoredBayesianDetails,
  readStoredDeepResult,
  readStoredMLScores,
} from '@/src/lib/medgemma';
import { ENABLE_KNN_LAYER } from '@/src/lib/featureFlags';
import type { DeepMedGemmaResult, DoctorKit } from '@/src/lib/medgemma';
import { DiagnosisCard } from '@/src/components/results/DiagnosisCard';

function doctorEmojiForSpecialty(specialty: string): string {
  if (specialty === 'Sleep Specialist') return '😴';
  if (specialty === 'Endocrinologist') return '🦋';
  if (specialty === 'Long COVID / ME·CFS Clinic') return '🦠';
  if (specialty === 'Functional Medicine or Psychiatry') return '🧠';
  return '🩺';
}

export default function ResultsPage() {
  const router = useRouter();
  const { answers, hydrated } = useAssessment();
  const [deep, setDeep] = useState<DeepMedGemmaResult | null>(null);
  const [expandedDoctors, setExpandedDoctors] = useState<number[]>([]);

  const toggleDoctor = (i: number) =>
    setExpandedDoctors((prev) => (prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]));

  const { summaryLine, doctors } = computeResults(answers);

  const mlScores = hydrated ? readStoredMLScores() : null;
  const bayesianDetails = hydrated ? readStoredBayesianDetails() : null;
  const bayesianScores = hydrated ? readStoredBayesianScores() : null;
  const effectiveScores = bayesianScores ?? mlScores;
  const diagnoses = effectiveScores ? buildDiagnosesFromML(effectiveScores) : computeResults(answers).diagnoses;
  const biomarkers = extractBiomarkerSnapshot(answers);

  const mlRanButEmpty = effectiveScores !== null && diagnoses.length === 0;
  const maxScore = effectiveScores ? Math.max(0, ...Object.values(effectiveScores)) : 0;
  const isLikelyHealthy = mlRanButEmpty && maxScore < 0.2;

  const effectiveSummaryLine = mlRanButEmpty
    ? isLikelyHealthy
      ? 'No concerning energy patterns found - your profile looks reassuring.'
      : 'Your assessment shows some low-level signals, but nothing points to a specific cause.'
    : summaryLine;

  const [lastAiError, setLastAiError] = useState<string | null>(null);

  useEffect(() => {
    if (!hydrated) return;
    const stored = readStoredDeepResult();
    if (!stored && Object.keys(answers).length > 0) {
      router.replace('/processing');
      return;
    }
    setDeep(stored);
    const err = window.sessionStorage.getItem('halffull_last_ai_error');
    if (err) setLastAiError(err);
  }, [answers, hydrated, router]);

  const recommendedDoctors =
    deep?.recommendedDoctors && deep.recommendedDoctors.length > 0
      ? deep.recommendedDoctors
      : doctors.slice(0, 3).map((doctor, index) => ({
          specialty: doctor.specialty,
          priority: index === 0 ? 'start_here' : index === 1 ? 'consider_next' : 'specialist_if_needed',
          reason: doctor.reason,
          symptomsToDiscuss: diagnoses[index]
            ? [diagnoses[index].description.split('. ')[0], 'Fatigue affecting normal daily function']
            : ['Fatigue affecting normal daily function'],
          suggestedTests:
            diagnoses[index]?.tests.slice(0, 3).map((test) => test.name) ?? ['Review first-line fatigue workup'],
        }));

  const doctorKits: DoctorKit[] =
    deep?.doctorKits && deep.doctorKits.length > 0
      ? deep.doctorKits
      : recommendedDoctors.map((doctor, index) => ({
          specialty: doctor.specialty,
          openingSummary:
            index === 0 && deep?.doctorKitSummary
              ? deep.doctorKitSummary
              : `I would like to discuss the main drivers of my fatigue and whether ${
                  diagnoses[index]?.title.toLowerCase() ?? 'these patterns'
                } could explain them.`,
          concerningSymptoms: doctor.symptomsToDiscuss,
          recommendedTests: doctor.suggestedTests,
          discussionPoints: [...(deep?.doctorKitQuestions ?? []), ...(deep?.doctorKitArguments ?? [])].slice(0, 4),
        }));

  const doctorKitOpener = doctorKits[0]?.openingSummary ?? deep?.doctorKitSummary ?? null;

  const aiLabel = deep?.meta?.label ?? 'Structured local report';
  const isFallbackContent = deep?.meta?.fallback ?? true;
  const knnLabSignals = ENABLE_KNN_LAYER ? deep?.knnSignals?.lab_signals ?? [] : [];
  const highlightedConditionCount = diagnoses.length;
  const heroSubline = `We analyzed your answers across 12 fatigue-related conditions - most are unlikely, but ${highlightedConditionCount} ${
    highlightedConditionCount === 1 ? 'is' : 'are'
  } worth a closer look.`;

  const diagnosisMeta = Object.fromEntries(
    diagnoses.map((diagnosis) => {
      const mlScore = mlScores?.[diagnosis.id] ?? 0;
      const posteriorScore = bayesianScores?.[diagnosis.id] ?? mlScore;
      const confidence = computeConfidence({
        conditionId: diagnosis.id,
        mlScore,
        posteriorScore,
        labSignals: knnLabSignals,
      });
      const urgency = computeUrgency({
        conditionId: diagnosis.id,
        posteriorScore,
        biomarkers,
      });

      return [diagnosis.id, { confidence, urgency }] as const;
    })
  ) as Record<string, { confidence: ConfidenceAssessment; urgency: UrgencyAssessment }>;

  const diagnosisReasoning = Object.fromEntries(
    diagnoses.map((diagnosis) => {
      const synthesisSummary = getInsightForDiagnosis(deep, diagnosis.id)
        ? `Synthesis: ${getInsightForDiagnosis(deep, diagnosis.id)}`
        : deep?.personalizedSummary
          ? 'Synthesis: reflected in the MedGemma report narrative'
          : 'Synthesis: local report layer';

      return [
        diagnosis.id,
        {
          mlScore: mlScores?.[diagnosis.id],
          threshold: ML_THRESHOLD,
          bayesian: bayesianDetails?.[diagnosis.id] ?? null,
          synthesisSummary,
        },
      ] as const;
    })
  );

  const downloadDoctorKit = async (doctorIndex?: number) => {
    const { jsPDF } = await import('jspdf');
    const doc: JsPDFType = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });

    const PAGE_W = 210;
    const MARGIN = 18;
    const CONTENT_W = PAGE_W - MARGIN * 2;
    let y = 20;

    const ACCENT = '#7765f4' as const;
    const INK = '#09090f' as const;
    const SOFT = '#6b7ba4' as const;

    const addText = (
      text: string,
      opts: { size?: number; color?: string; bold?: boolean; indent?: number; lineH?: number }
    ) => {
      const { size = 10, color = INK, bold = false, indent = 0, lineH = 5.5 } = opts;
      doc.setFontSize(size);
      doc.setTextColor(color);
      doc.setFont('helvetica', bold ? 'bold' : 'normal');
      const lines = doc.splitTextToSize(text, CONTENT_W - indent);
      lines.forEach((line: string) => {
        if (y > 272) {
          doc.addPage();
          y = 20;
        }
        doc.text(line, MARGIN + indent, y);
        y += lineH;
      });
    };

    const addSectionHeader = (title: string) => {
      y += 4;
      if (y > 272) {
        doc.addPage();
        y = 20;
      }
      doc.setFillColor(245, 245, 250);
      doc.roundedRect(MARGIN, y - 4, CONTENT_W, 9, 2, 2, 'F');
      addText(title.toUpperCase(), { size: 8, color: SOFT, bold: true, lineH: 6 });
      y += 2;
    };

    const addBullet = (text: string, num?: number) => {
      const prefix = num !== undefined ? `${num}.  ` : '-  ';
      if (y > 272) {
        doc.addPage();
        y = 20;
      }
      doc.setFontSize(10);
      doc.setTextColor(INK);
      doc.setFont('helvetica', 'normal');
      const prefixW = doc.getTextWidth(prefix);
      doc.text(prefix, MARGIN + 2, y);
      const lines = doc.splitTextToSize(text, CONTENT_W - 2 - prefixW);
      lines.forEach((line: string) => {
        if (y > 272) {
          doc.addPage();
          y = 20;
        }
        doc.text(line, MARGIN + 2 + prefixW, y);
        y += 5.5;
      });
    };

    doc.setFillColor(119, 101, 244);
    doc.rect(0, 0, PAGE_W, 14, 'F');
    doc.setFontSize(11);
    doc.setTextColor('#ffffff');
    doc.setFont('helvetica', 'bold');
    doc.text('HALFFULL', MARGIN, 9.5);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(9);
    doc.text('Doctor Visit Kit', PAGE_W - MARGIN, 9.5, { align: 'right' });
    y = 26;

    addText('Your Energy Report', { size: 22, bold: true, lineH: 10 });
    addText(effectiveSummaryLine, { size: 10, color: SOFT, lineH: 6 });
    y += 4;

    if (doctorIndex === undefined) {
      if (doctorKitOpener) {
        addSectionHeader('How to open the appointment');
        doc.setFillColor(240, 238, 253);
        const openerLines = doc.splitTextToSize(`"${doctorKitOpener}"`, CONTENT_W - 8);
        const boxH = openerLines.length * 5.5 + 8;
        if (y + boxH > 272) {
          doc.addPage();
          y = 20;
        }
        doc.roundedRect(MARGIN, y - 2, CONTENT_W, boxH, 3, 3, 'F');
        doc.setDrawColor(ACCENT);
        doc.setLineWidth(0.8);
        doc.line(MARGIN, y - 2, MARGIN, y - 2 + boxH);
        doc.setLineWidth(0.2);
        addText(`"${doctorKitOpener}"`, { size: 10, color: '#4a3fa0', indent: 5, lineH: 5.5 });
        y += 4;
      }

      addSectionHeader('Flagged areas');
      if (diagnoses.length > 0) {
        diagnoses.slice(0, 5).forEach((d) => {
          addBullet(d.title);
        });
      } else {
        addText(
          isLikelyHealthy
            ? 'No concerning patterns detected. Your profile showed no strong signals above the assessment threshold.'
            : 'No specific cause identified. Low-level signals were present but did not reach a confident finding after clarification.',
          { size: 10, indent: 2 }
        );
      }
      y += 2;

      if (deep?.nextSteps) {
        addSectionHeader('Next steps - talk to a doctor');
        addText(deep.nextSteps, { size: 10, indent: 2 });
        y += 2;
      }

      if (recommendedDoctors.length > 0) {
        addSectionHeader('Recommended doctors');
        recommendedDoctors.forEach((doctor, index) => {
          addBullet(`${doctor.specialty}: ${doctor.reason}`, index + 1);
        });
        y += 2;
      }
    }

    const kitsToExport = doctorIndex !== undefined ? doctorKits.filter((_, i) => i === doctorIndex) : doctorKits;
    if (kitsToExport.length > 0) {
      kitsToExport.forEach((kit) => {
        addSectionHeader(`${kit.specialty} doctor kit`);
        addText(kit.openingSummary, { size: 10, indent: 2 });
        if (kit.whatToSay) {
          addText('What to say:', { size: 9, bold: true, indent: 2 });
          addText(`"${kit.whatToSay}"`, { size: 10, color: '#4a3fa0', indent: 5 });
        }
        addText('Concerning symptoms:', { size: 9, bold: true, indent: 2 });
        kit.concerningSymptoms.forEach((item) => addBullet(item));
        addText('Tests worth discussing:', { size: 9, bold: true, indent: 2 });
        kit.recommendedTests.forEach((item) => addBullet(item));
        addText('Questions and evidence to bring:', { size: 9, bold: true, indent: 2 });
        kit.discussionPoints.forEach((item, index) => addBullet(item, index + 1));
        if (kit.bringToAppointment && kit.bringToAppointment.length > 0) {
          addText('Bring to the appointment:', { size: 9, bold: true, indent: 2 });
          kit.bringToAppointment.forEach((item) => addBullet(item));
        }
        y += 2;
      });
    }

    const filename =
      doctorIndex !== undefined && doctorKits[doctorIndex]
        ? `halffull-${doctorKits[doctorIndex].specialty.toLowerCase().replace(/\s+/g, '-')}-kit.pdf`
        : 'halffull-doctor-kit.pdf';

    const pageCount = (doc as unknown as { internal: { getNumberOfPages: () => number } }).internal.getNumberOfPages();
    for (let p = 1; p <= pageCount; p++) {
      doc.setPage(p);
      doc.setFontSize(8);
      doc.setTextColor(SOFT);
      doc.setFont('helvetica', 'normal');
      doc.text('For educational use only - Not a substitute for medical advice - halffull.app', PAGE_W / 2, 290, {
        align: 'center',
      });
      doc.text(`${p} / ${pageCount}`, PAGE_W - MARGIN, 290, { align: 'right' });
    }

    doc.save(filename);
  };

  const emailDoctorKit = () => {
    const subject = encodeURIComponent('HalfFull doctor visit kit');
    const body = encodeURIComponent(
      [
        'Here is my HalfFull summary for our appointment.',
        '',
        effectiveSummaryLine,
        '',
        ...(doctorKitOpener ? ['Opening statement:', doctorKitOpener, ''] : []),
        'Concerning patterns:',
        ...(diagnoses.length > 0
          ? diagnoses.slice(0, 4).map((d) => `- ${d.title}`)
          : [isLikelyHealthy ? '- No concerning patterns detected' : '- No specific cause identified']),
        '',
        'Next steps:',
        ...(deep?.nextSteps ? [deep.nextSteps, ''] : []),
        'Recommended doctors:',
        ...recommendedDoctors.map((doctor) => `- ${doctor.specialty}: ${doctor.reason}`),
        '',
        ...doctorKits.flatMap((kit) => [
          `${kit.specialty} doctor kit:`,
          ...kit.concerningSymptoms.map((item) => `- Symptom: ${item}`),
          ...kit.recommendedTests.map((item) => `- Test: ${item}`),
          ...kit.discussionPoints.map((item) => `- Discussion point: ${item}`),
          '',
        ]),
      ].join('\n')
    );
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  };

  if (!hydrated) {
    return (
      <div className="phone-frame flex items-center justify-center">
        <p className="text-sm text-[var(--color-ink-soft)]">Loading...</p>
      </div>
    );
  }

  return (
    <div className="phone-frame flex flex-col">
      <header className="sticky top-0 z-10 border-b border-white/30 bg-[rgba(184,194,228,0.82)] px-5 pt-6 pb-4 backdrop-blur-sm">
        <div className="mx-auto flex max-w-lg items-center justify-between">
          <Link
            href="/start"
            style={{ fontFamily: 'Archivo, sans-serif', letterSpacing: '-0.02em', textTransform: 'none', fontSize: 16, lineHeight: 1 }}
          >
            <span style={{ fontWeight: 400, color: 'var(--color-ink-soft)' }}>half</span>
            <span style={{ fontWeight: 900, color: 'var(--color-ink)' }}>Full</span>
          </Link>
          <Link
            href="/assessment"
            className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--color-ink-soft)] transition-colors"
          >
            Review
          </Link>
        </div>
      </header>

      <main className="flex-1 px-5 py-4 pb-10">
        <div className="mx-auto flex max-w-lg flex-col gap-5">
          <section className="relative overflow-hidden rounded-[2rem] bg-[var(--color-card)] px-5 py-6 shadow-[0_14px_30px_rgba(86,98,145,0.14)]">
            <div className="mb-3">
              <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink-soft)]">
                Assessment complete
              </p>
              <h1 className="editorial-display text-[clamp(2rem,8.2vw,3.2rem)] leading-[0.96] text-[var(--color-ink)]">
                What your
                <br />
                answers reveal
              </h1>
            </div>
            <p className="max-w-[26rem] text-sm leading-6 text-[var(--color-ink-soft)]">{heroSubline}</p>
          </section>

          {isFallbackContent && (
            <div>
              <div className="mb-2">
                <span className="pill-tag bg-[var(--color-lime)] text-[var(--color-ink)]">{aiLabel}</span>
              </div>
              <p className="text-sm text-[var(--color-ink-soft)]">
                This report text was generated from demo or local fallback logic so the app stays usable even when live
                MedGemma is unavailable.
              </p>
              {lastAiError && <p className="mt-2 break-all text-xs font-mono text-red-500">Error: {lastAiError}</p>}
            </div>
          )}

          <div className="flex flex-col gap-3">
            <div>
              <h2 className="text-2xl font-bold tracking-[-0.04em] text-[var(--color-ink)]">
                {diagnoses.length > 0 ? 'Conditions worth checking' : isLikelyHealthy ? 'Looking good' : 'Pattern unclear'}
              </h2>
              <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
                {diagnoses.length > 0
                  ? 'Tap each to see recommended tests and doctor-ready details.'
                  : isLikelyHealthy
                    ? 'Your answers show no strong signals pointing to an underlying energy issue.'
                    : "Your answers show some fatigue signals, but they don't point clearly to a specific cause."}
              </p>
            </div>

            {diagnoses.length > 0 ? (
              diagnoses.map((d) => (
                <DiagnosisCard
                  key={d.id}
                  diagnosis={d}
                  personalNote={getInsightForDiagnosis(deep, d.id)}
                  confidence={{
                    tier: diagnosisMeta[d.id]?.confidence.tier ?? 'low',
                    summary: diagnosisMeta[d.id]?.confidence.summary ?? 'Limited evidence available.',
                  }}
                  urgency={{
                    level: diagnosisMeta[d.id]?.urgency.level ?? 'routine',
                    summary: diagnosisMeta[d.id]?.urgency.reasons[0] ?? 'Routine follow-up is appropriate.',
                  }}
                  reasoningTrace={diagnosisReasoning[d.id]}
                />
              ))
            ) : mlRanButEmpty ? (
              <div className="rounded-[1.6rem] bg-[var(--color-card)] px-5 py-6 shadow-[0_14px_30px_rgba(86,98,145,0.1)]">
                {isLikelyHealthy ? (
                  <>
                    <p className="mb-3 text-4xl">✅</p>
                    <h3 className="mb-2 text-lg font-bold tracking-[-0.03em] text-[var(--color-ink)]">
                      No concerning patterns detected
                    </h3>
                    <p className="text-sm leading-6 text-[var(--color-ink-soft)]">
                      Based on your answers, none of the 11 health models identified a likely underlying cause for
                      fatigue. This is a reassuring result.
                    </p>
                    <p className="mt-3 text-sm leading-6 text-[var(--color-ink-soft)]">
                      If you do experience fatigue in daily life, a routine check-up with your GP is still a sensible
                      step - some causes only become visible through blood tests.
                    </p>
                  </>
                ) : (
                  <>
                    <p className="mb-3 text-4xl">🔍</p>
                    <h3 className="mb-2 text-lg font-bold tracking-[-0.03em] text-[var(--color-ink)]">
                      No specific cause identified
                    </h3>
                    <p className="text-sm leading-6 text-[var(--color-ink-soft)]">
                      Your answers contain some energy-related signals, but after the full assessment - including
                      clarification questions - none of the 11 models reached the threshold for a confident finding.
                    </p>
                    <p className="mt-3 text-sm leading-6 text-[var(--color-ink-soft)]">
                      This can happen when fatigue has multiple small contributing factors, or when key lab values would
                      be needed to confirm a pattern. A GP visit with targeted bloodwork is the recommended next step.
                    </p>
                  </>
                )}
              </div>
            ) : null}
          </div>

          {(deep?.nextSteps || recommendedDoctors.length > 0) && (
            <div className="flex flex-col gap-3">
              <div>
                <h2 className="text-2xl font-bold tracking-[-0.04em] text-[var(--color-ink)]">
                  Next steps - Talk to a doctor
                </h2>
                {deep?.nextSteps && (
                  <p className="mt-1 text-sm text-[var(--color-ink-soft)]">{deep.nextSteps}</p>
                )}
              </div>
              {recommendedDoctors.length > 0 && (
                <div className="space-y-3">
                  {recommendedDoctors.map((doctor, index) => {
                    const kit = doctorKits[index];
                    const isOpen = expandedDoctors.includes(index);
                    const priorityLabel =
                      doctor.priority === 'start_here'
                        ? 'Start here'
                        : doctor.priority === 'consider_next'
                          ? 'Consider next'
                          : 'Specialist option';

                    return (
                      <div
                        key={`${doctor.specialty}-${index}`}
                        className="overflow-hidden rounded-[1.8rem] border border-[rgba(151,166,210,0.25)] bg-[var(--color-card)]"
                      >
                        <button
                          type="button"
                          onClick={() => toggleDoctor(index)}
                          className="flex w-full items-center gap-4 px-5 py-4 text-left"
                        >
                          <span className="shrink-0 text-[2rem] leading-none">
                            {doctorEmojiForSpecialty(doctor.specialty)}
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="card-title text-[1.05rem] font-black tracking-[-0.03em] text-[var(--color-ink)]">
                                {doctor.specialty}
                              </span>
                              <span className="rounded-full bg-[var(--color-lime)] px-2 py-0.5 text-[10px] font-bold text-[var(--color-ink)]">
                                {priorityLabel}
                              </span>
                            </div>
                            <p className="mt-0.5 line-clamp-2 text-xs leading-5 text-[var(--color-ink-soft)]">
                              {doctor.reason}
                            </p>
                          </div>
                          <svg
                            width="18"
                            height="18"
                            viewBox="0 0 18 18"
                            fill="none"
                            className={`shrink-0 text-[var(--color-ink-soft)] transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
                          >
                            <path
                              d="M4.5 6.75L9 11.25L13.5 6.75"
                              stroke="currentColor"
                              strokeWidth="1.5"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            />
                          </svg>
                        </button>

                        {isOpen && kit && (
                          <div className="space-y-4 border-t border-[rgba(119,101,244,0.15)] bg-[var(--color-card)] px-5 pb-6 pt-4">
                            {kit.whatToSay && (
                              <div className="rounded-[1rem] border border-[rgba(119,101,244,0.3)] bg-[rgba(119,101,244,0.06)] px-3 py-3">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-soft)]">
                                  What to say
                                </p>
                                <p className="mt-2 text-sm italic leading-6 text-[var(--color-ink)]">
                                  &ldquo;{kit.whatToSay}&rdquo;
                                </p>
                              </div>
                            )}
                            {kit.openingSummary && !kit.whatToSay && (
                              <p className="text-sm leading-6 text-[var(--color-ink)]">{kit.openingSummary}</p>
                            )}
                            {kit.concerningSymptoms.length > 0 && (
                              <div>
                                <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-soft)]">
                                  Symptoms to raise
                                </p>
                                <div className="space-y-1">
                                  {kit.concerningSymptoms.map((s, si) => (
                                    <p key={si} className="text-sm leading-6 text-[var(--color-ink)]">
                                      • {s}
                                    </p>
                                  ))}
                                </div>
                              </div>
                            )}
                            {kit.recommendedTests.length > 0 && (
                              <div>
                                <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-soft)]">
                                  Tests to request
                                </p>
                                <div className="space-y-1">
                                  {kit.recommendedTests.map((t, ti) => (
                                    <p key={ti} className="text-sm leading-6 text-[var(--color-ink)]">
                                      • {t}
                                    </p>
                                  ))}
                                </div>
                              </div>
                            )}
                            {kit.discussionPoints.length > 0 && (
                              <div>
                                <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-soft)]">
                                  Questions &amp; evidence
                                </p>
                                <div className="space-y-2">
                                  {kit.discussionPoints.map((pt, pi) => (
                                    <div key={pi} className="rounded-[1rem] bg-[rgba(119,101,244,0.06)] px-3 py-3">
                                      <p className="text-sm leading-6 text-[var(--color-ink)]">{pt}</p>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                            {kit.bringToAppointment && kit.bringToAppointment.length > 0 && (
                              <div>
                                <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-soft)]">
                                  Bring to the appointment
                                </p>
                                <div className="space-y-1">
                                  {kit.bringToAppointment.map((item, ii) => (
                                    <p key={ii} className="text-sm leading-6 text-[var(--color-ink)]">
                                      • {item}
                                    </p>
                                  ))}
                                </div>
                              </div>
                            )}
                            <button
                              type="button"
                              onClick={() => downloadDoctorKit(index)}
                              className="mt-1 w-full rounded-full bg-[var(--color-ink)] px-4 py-3 text-sm font-bold text-white"
                            >
                              Download {doctor.specialty} kit (PDF)
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {ENABLE_KNN_LAYER && knnLabSignals.length > 0 && (
            <div className="section-card px-5 py-4">
              <div className="mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-ink)]">
                  For people similar to you, it&apos;s worth checking
                </h3>
                <p className="mt-1 text-xs leading-5 text-[var(--color-ink-soft)]">
                  In {deep?.knnSignals?.k_neighbours ?? knnLabSignals.length} people from our database with a similar
                  fatigue pattern, these lab markers were more commonly abnormal.
                </p>
              </div>
              <div className="space-y-2">
                {knnLabSignals.slice(0, 6).map((signal, i) => (
                  <div key={i} className="flex items-start gap-3 rounded-[1rem] bg-[rgba(119,101,244,0.06)] px-3 py-3">
                    <span
                      className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                        signal.direction === 'high'
                          ? 'bg-[rgba(235,98,60,0.12)] text-[#b84a25]'
                          : 'bg-[rgba(74,102,196,0.12)] text-[#3a5db5]'
                      }`}
                    >
                      {signal.direction}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-[var(--color-ink)]">{signal.lab}</p>
                      <p className="text-xs text-[var(--color-ink-soft)]">
                        {Math.round(signal.neighbour_pct)}% of similar people
                        {signal.lift != null ? ` - ${signal.lift.toFixed(1)}x more common than average` : ''}
                      </p>
                      {signal.context && (
                        <p className="mt-0.5 text-xs leading-5 text-[var(--color-ink-soft)]">{signal.context}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-col gap-3 pt-2">
            <button
              type="button"
              onClick={emailDoctorKit}
              className="w-full rounded-full bg-[var(--color-ink)] px-5 py-4 text-center text-base font-bold text-white shadow-[0_10px_24px_rgba(9,9,15,0.12)] transition-all active:scale-[0.98]"
            >
              Email this report
            </button>
            <Link
              href="/create-account"
              className="w-full rounded-full bg-[var(--color-lime)] px-5 py-4 text-center text-base font-bold text-[var(--color-ink)] shadow-[0_10px_24px_rgba(9,9,15,0.12)] transition-all active:scale-[0.98]"
            >
              Save report
            </Link>
            <p className="text-center text-xs leading-5 text-[var(--color-ink-soft)]">
              Optional. If you skip this, your data stays only in this browser session. If you save the report, we
              store your responses so you can come back to them later.
            </p>
          </div>

          <p className="pb-2 text-center text-[11px] leading-4 text-[var(--color-ink-soft)]">
            For educational use only. Not a substitute for medical advice.
            <br />
            Results are indicative only - always discuss with a qualified clinician.
          </p>
        </div>
      </main>
    </div>
  );
}
