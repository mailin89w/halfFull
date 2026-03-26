'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import type { jsPDF as JsPDFType } from 'jspdf';
import { useAssessment } from '@/src/hooks/useAssessment';
import { ExitAssessmentButton } from '@/src/components/ExitAssessmentButton';
import {
  ML_THRESHOLD,
} from '@/src/lib/mlConfig';
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
  readStoredBayesianDetails,
  readStoredBayesianScores,
  readStoredConfirmedConditions,
  readStoredDeepResult,
  readStoredMLScores,
} from '@/src/lib/medgemma';
import {
  createPrivacyConsentRecord,
  PRIVACY_STORAGE_KEY,
  readPrivacyConsent,
  storePrivacyConsent,
} from '@/src/lib/privacy';
import type { DeepMedGemmaResult, DoctorKit } from '@/src/lib/medgemma';
import { EnergySpectrum } from '@/src/components/results/EnergySpectrum';
import { DiagnosisCard } from '@/src/components/results/DiagnosisCard';

export default function ResultsPage() {
  const { answers, hydrated, reset } = useAssessment();
  const [deep, setDeep] = useState<DeepMedGemmaResult | null>(null);
  const [expandedDoctors, setExpandedDoctors] = useState<number[]>([]);
  const [profileStatus, setProfileStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [profileError, setProfileError] = useState<string | null>(null);
  const toggleDoctor = (i: number) =>
    setExpandedDoctors((prev) => prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]);

  const { currentPct, projectedPct, summaryLine, doctors } = computeResults(answers);

  // Use ML diagnoses when available (from /api/score run on /processing page),
  // falling back to rule-based diagnoses from computeResults.
  const mlScores = hydrated ? readStoredMLScores() : null;
  const bayesianDetails = hydrated ? readStoredBayesianDetails() : null;
  const bayesianScores = hydrated ? readStoredBayesianScores() : null;
  const confirmedConditions = hydrated ? (readStoredConfirmedConditions() ?? []) : [];
  const diagnoses = mlScores
    ? buildDiagnosesFromML(mlScores)
    : computeResults(answers).diagnoses;
  const biomarkers = extractBiomarkerSnapshot(answers);

  // Load deep analysis result from session storage (written by /processing)
  useEffect(() => {
    if (!hydrated) return;
    const stored = readStoredDeepResult();
    setDeep(stored);
    if (readPrivacyConsent()) {
      setProfileStatus('saved');
    }
  }, [hydrated]);

  // ── Doctor kit content: AI-generated if available, rule-based as fallback ──
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
        suggestedTests: diagnoses[index]?.tests.slice(0, 3).map((test) => test.name) ?? ['Review first-line fatigue workup'],
      }));

  const doctorKits: DoctorKit[] =
    deep?.doctorKits && deep.doctorKits.length > 0
      ? deep.doctorKits
      : recommendedDoctors.map((doctor, index) => ({
        specialty: doctor.specialty,
        openingSummary: index === 0 && deep?.doctorKitSummary
          ? deep.doctorKitSummary
          : `I would like to discuss the main drivers of my fatigue and whether ${diagnoses[index]?.title.toLowerCase() ?? 'these patterns'} could explain them.`,
        concerningSymptoms: doctor.symptomsToDiscuss,
        recommendedTests: doctor.suggestedTests,
        discussionPoints: [...(deep?.doctorKitQuestions ?? []), ...(deep?.doctorKitArguments ?? [])].slice(0, 4),
      }));

  const doctorKitOpener = doctorKits[0]?.openingSummary ?? deep?.doctorKitSummary ?? null;

  const combinedSummary = [
    deep?.personalizedSummary,
    confirmedConditions.length > 0
      ? `Already confirmed conditions to mention: ${confirmedConditions
        .map((c) => ({
          anemia: 'anaemia',
          iron_deficiency: 'iron deficiency',
          thyroid: 'thyroid dysfunction',
          kidney: 'kidney disease',
          sleep_disorder: 'sleep disorder',
          liver: 'liver disease',
          prediabetes: 'prediabetes',
          hepatitis_bc: 'hepatitis B/C',
          hepatitis: 'hepatitis',
          perimenopause: 'perimenopause',
        }[c] ?? c))
        .join(', ')}. Use these as part of the bigger fatigue picture when you speak with a doctor.`
      : null,
  ].filter(Boolean).join(' ');

  const coachingTips = deep?.coachingTips ?? [];
  const aiLabel = deep?.meta?.label ?? 'Structured local report';
  const isFallbackContent = deep?.meta?.fallback ?? true;
  const knnLabSignals = deep?.knnSignals?.lab_signals ?? [];

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

  const urgentDiagnoses = diagnoses.filter((diagnosis) => diagnosisMeta[diagnosis.id]?.urgency.level === 'urgent');

  const diagnosisReasoning = Object.fromEntries(
    diagnoses.map((diagnosis) => {
      const clusterMatch = knnLabSignals.find((signal) =>
        signal.lab.toLowerCase().includes(diagnosis.id.replace('_', ' ')) ||
        diagnosis.tests.some((test) => signal.lab.toLowerCase().includes(test.name.toLowerCase().split(' ')[0]))
      );

      const clusterSummary = clusterMatch
        ? `Cluster: ${Math.round(clusterMatch.neighbour_pct)}% of neighbours flagged ${clusterMatch.lab.toLowerCase()}`
        : 'Cluster: no strong neighbour lab support available';

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
          clusterSummary,
          synthesisSummary,
        },
      ] as const;
    })
  );

  const saveProfile = async () => {
    if (profileStatus === 'saving' || profileStatus === 'saved') return;

    setProfileStatus('saving');
    setProfileError(null);

    const privacy = createPrivacyConsentRecord();
    storePrivacyConsent(privacy);

    try {
      const response = await fetch('/api/privacy/consent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          privacy,
          source: 'results_profile_prompt',
          snapshot: {
            answers,
            mlScores: mlScores ?? {},
            confirmedConditions,
            deepResult: deep,
          },
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({ error: 'Could not save your profile.' }));
        throw new Error((data as { error?: string }).error ?? 'Could not save your profile.');
      }

      setProfileStatus('saved');
    } catch (error) {
      window.localStorage.removeItem(PRIVACY_STORAGE_KEY);
      setProfileStatus('error');
      setProfileError(error instanceof Error ? error.message : 'Could not save your profile.');
    }
  };

  // ── Export helpers ───────────────────────────────────────────────────────
  const downloadDoctorKit = async (doctorIndex?: number) => {
    // Dynamically import jsPDF so it only loads client-side when needed
    const { jsPDF } = await import('jspdf');
    const doc: JsPDFType = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });

    const PAGE_W = 210;
    const MARGIN = 18;
    const CONTENT_W = PAGE_W - MARGIN * 2;
    let y = 20;

    const ACCENT = '#7765f4' as const;
    const INK = '#09090f' as const;
    const SOFT = '#6b7ba4' as const;

    // ── helper: wrapped text with automatic page breaks ─────────────────
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
        if (y > 272) { doc.addPage(); y = 20; }
        doc.text(line, MARGIN + indent, y);
        y += lineH;
      });
    };

    const addSectionHeader = (title: string) => {
      y += 4;
      if (y > 272) { doc.addPage(); y = 20; }
      doc.setFillColor(245, 245, 250);
      doc.roundedRect(MARGIN, y - 4, CONTENT_W, 9, 2, 2, 'F');
      addText(title.toUpperCase(), { size: 8, color: SOFT, bold: true, lineH: 6 });
      y += 2;
    };

    const addBullet = (text: string, num?: number) => {
      const prefix = num !== undefined ? `${num}.  ` : '•  ';
      if (y > 272) { doc.addPage(); y = 20; }
      doc.setFontSize(10);
      doc.setTextColor(INK);
      doc.setFont('helvetica', 'normal');
      const prefixW = doc.getTextWidth(prefix);
      doc.text(prefix, MARGIN + 2, y);
      const lines = doc.splitTextToSize(text, CONTENT_W - 2 - prefixW);
      lines.forEach((line: string, i: number) => {
        if (i > 0 && y > 272) { doc.addPage(); y = 20; }
        if (i > 0) doc.text(line, MARGIN + 2 + prefixW, y);
        else doc.text(line, MARGIN + 2 + prefixW, y);
        y += 5.5;
      });
    };

    // ── Header bar ───────────────────────────────────────────────────────
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

    // ── Title ────────────────────────────────────────────────────────────
    addText('Your Energy Report', { size: 22, bold: true, lineH: 10 });
    addText(summaryLine, { size: 10, color: SOFT, lineH: 6 });
    y += 4;

    // ── Opening statement ────────────────────────────────────────────────
    if (doctorKitOpener) {
      addSectionHeader('How to open the appointment');
      // Tinted box
      doc.setFillColor(119, 101, 244, 0.06);
      doc.setFillColor(240, 238, 253);
      const openerLines = doc.splitTextToSize(`"${doctorKitOpener}"`, CONTENT_W - 8);
      const boxH = openerLines.length * 5.5 + 8;
      if (y + boxH > 272) { doc.addPage(); y = 20; }
      doc.roundedRect(MARGIN, y - 2, CONTENT_W, boxH, 3, 3, 'F');
      doc.setDrawColor(ACCENT);
      doc.setLineWidth(0.8);
      doc.line(MARGIN, y - 2, MARGIN, y - 2 + boxH);
      doc.setLineWidth(0.2);
      addText(`"${doctorKitOpener}"`, { size: 10, color: '#4a3fa0', indent: 5, lineH: 5.5 });
      y += 4;
    }

    // ── Flagged areas ────────────────────────────────────────────────────
    addSectionHeader('Flagged areas');
    diagnoses.slice(0, 5).forEach((d) => {
      addBullet(`${d.title} — ${d.signal} signal`);
    });
    y += 2;

    // ── Next steps ───────────────────────────────────────────────────────
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

    const kitsToExport = doctorIndex !== undefined
      ? doctorKits.filter((_, i) => i === doctorIndex)
      : doctorKits;
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
    const filename = doctorIndex !== undefined && doctorKits[doctorIndex]
      ? `halffull-${doctorKits[doctorIndex].specialty.toLowerCase().replace(/\s+/g, '-')}-kit.pdf`
      : 'halffull-doctor-kit.pdf';

    // ── Footer ───────────────────────────────────────────────────────────
    const pageCount = (doc as unknown as { internal: { getNumberOfPages: () => number } }).internal.getNumberOfPages();
    for (let p = 1; p <= pageCount; p++) {
      doc.setPage(p);
      doc.setFontSize(8);
      doc.setTextColor(SOFT);
      doc.setFont('helvetica', 'normal');
      doc.text(
        'For educational use only · Not a substitute for medical advice · halffull.app',
        PAGE_W / 2, 290, { align: 'center' }
      );
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
        summaryLine,
        '',
        ...(doctorKitOpener ? ['Opening statement:', doctorKitOpener, ''] : []),
        'Concerning patterns:',
        ...diagnoses.slice(0, 4).map((d) => `- ${d.title}`),
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
      {/* Sticky header */}
      <header className="sticky top-0 z-10 border-b border-white/30 bg-[rgba(184,194,228,0.82)] px-5 pt-6 pb-4 backdrop-blur-sm">
        <div className="mx-auto flex max-w-lg items-center justify-between">
          <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink)]">HalfFull</span>
          <div className="flex items-center gap-3">
            <Link
              href="/assessment"
              className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--color-ink-soft)] transition-colors"
            >
              Review
            </Link>
            <ExitAssessmentButton
              className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--color-ink-soft)] transition-colors"
            />
          </div>
        </div>
      </header>

      <main className="flex-1 px-5 py-4 pb-10">
        <div className="max-w-lg mx-auto flex flex-col gap-5">

          {/* ── Hero ──────────────────────────────────────────────────────── */}
          <section className="relative overflow-hidden rounded-[2rem] bg-[var(--color-card)] px-5 py-6 shadow-[0_14px_30px_rgba(86,98,145,0.14)]">
            <div className="mb-3">
              <div>
                <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--color-ink-soft)]">
                  Assessment complete
                </p>
                <h1 className="editorial-display text-[clamp(2.7rem,10vw,4.8rem)] leading-[0.9] text-[var(--color-ink)]">
                  YOUR
                  <br />
                  ENERGY
                  <br />
                  REPORT
                </h1>
              </div>
            </div>
            <p className="max-w-[16rem] text-sm leading-6 text-[var(--color-ink-soft)]">
              {summaryLine}
            </p>
            <div className="mt-6 inline-flex rounded-full bg-[var(--color-lime)] px-4 py-3 text-sm font-bold text-[var(--color-ink)]">
              Scroll for the flagged patterns
            </div>
          </section>

          <section className="section-card border-[var(--color-lime)] px-5 py-5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="pill-tag bg-[var(--color-lime)] text-[var(--color-ink)]">
                Save this report
              </span>
              {profileStatus === 'saved' && (
                <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-soft)]">
                  Profile ready
                </span>
              )}
            </div>
            <h2 className="mt-3 text-2xl font-bold tracking-[-0.04em] text-[var(--color-ink)]">
              Want us to remember this for next time?
            </h2>
            <p className="mt-2 text-sm leading-6 text-[var(--color-ink-soft)]">
              If you consent, we’ll save this report under an anonymous profile so next time you can come back with new labs and compare what changed.
            </p>
            <div className="mt-4 flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={saveProfile}
                disabled={profileStatus === 'saving' || profileStatus === 'saved'}
                className="rounded-full bg-[#09090f] px-5 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {profileStatus === 'saved'
                  ? 'Profile saved'
                  : profileStatus === 'saving'
                    ? 'Saving...'
                    : 'Consent and save'}
              </button>
              <p className="flex items-center text-xs leading-5 text-[var(--color-ink-soft)]">
                Optional. If you skip this, your data stays only in this browser session.
              </p>
            </div>
            {profileError && (
              <p className="mt-3 text-sm text-[#b34343]">{profileError}</p>
            )}
          </section>

          {urgentDiagnoses.length > 0 && (
            <section className="rounded-[1.8rem] border border-[rgba(214,72,72,0.2)] bg-[rgba(214,72,72,0.07)] px-5 py-5 shadow-[0_12px_28px_rgba(214,72,72,0.08)]">
              <div className="flex flex-wrap items-center gap-2">
                <span className="pill-tag bg-[rgba(214,72,72,0.12)] text-[#8f2222]">
                  Prompt medical follow-up
                </span>
              </div>
              <h2 className="mt-3 text-2xl font-bold tracking-[-0.04em] text-[var(--color-ink)]">
                One or more findings should be checked urgently
              </h2>
              <p className="mt-2 text-sm leading-6 text-[var(--color-ink-soft)]">
                Based on the current probabilities and biomarker flags, please contact your doctor promptly about {urgentDiagnoses.map((diagnosis) => diagnosis.title).join(', ')}.
              </p>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                <a
                  href="tel:"
                  className="rounded-full bg-[#8f2222] px-5 py-3 text-center text-sm font-bold text-white"
                >
                  Call your doctor now
                </a>
                <button
                  type="button"
                  onClick={emailDoctorKit}
                  className="rounded-full border border-[rgba(214,72,72,0.24)] bg-white px-5 py-3 text-sm font-bold text-[#8f2222]"
                >
                  Email this report
                </button>
              </div>
            </section>
          )}

          {isFallbackContent && (
            <div className="section-card border-[var(--color-lime)] px-5 py-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="pill-tag bg-[var(--color-lime)] text-[var(--color-ink)]">
                  {aiLabel}
                </span>
              </div>
              <p className="text-sm leading-6 text-[var(--color-ink-soft)]">
                This report text was generated from demo or local fallback logic so the app stays usable even when live MedGemma is unavailable.
              </p>
            </div>
          )}

          {/* ── MedGemma personalised summary ─────────────────────────────── */}
          {combinedSummary ? (
            <div className="section-card border-[var(--color-lime)] px-5 py-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="pill-tag bg-[var(--color-lime)] text-[var(--color-ink)]">
                  Your results · MedGemma
                </span>
              </div>
              {deep?.summaryPoints && deep.summaryPoints.length > 0 ? (
                <ul className="mt-1 space-y-2">
                  {deep.summaryPoints.map((point, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm leading-6 text-[var(--color-ink)]">
                      <span className="mt-[3px] h-2 w-2 shrink-0 rounded-full bg-[var(--color-lime)]" />
                      {point}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm leading-6 text-[var(--color-ink)]">{combinedSummary}</p>
              )}
            </div>
          ) : (
            <div className="section-card flex flex-col gap-2 px-5 py-4">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--color-ink-soft)]">
                  AI insights · MedGemma
                </span>
                <span className="inline-block h-3 w-3 rounded-full bg-[var(--color-lime)] animate-pulse" />
              </div>
              <div className="h-3 w-full rounded-full bg-[var(--color-card-muted)] animate-pulse" />
              <div className="h-3 w-4/5 rounded-full bg-[var(--color-card-muted)] animate-pulse" />
              <div className="h-3 w-3/5 rounded-full bg-[var(--color-card-muted)] animate-pulse" />
            </div>
          )}

          {/* ── Energy spectrum ───────────────────────────────────────────── */}
          <EnergySpectrum currentPct={currentPct} projectedPct={projectedPct} />

          {/* ── Diagnosis cards ───────────────────────────────────────────── */}
          <div className="flex flex-col gap-3">
            <div>
              <h2 className="text-2xl font-bold tracking-[-0.04em] text-[var(--color-ink)]">
                Areas worth checking
              </h2>
              <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
                Tap each to see recommended tests and recovery outlook.
              </p>
            </div>
            {diagnoses.map((d, i) => (
              <DiagnosisCard
                key={d.id}
                diagnosis={d}
                rank={i + 1}
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
            ))}
          </div>

          {/* ── Next steps + doctor cards ─────────────────────────────────── */}
          {(deep?.nextSteps || recommendedDoctors.length > 0) && (
            <div className="section-card border-[var(--color-lime)] bg-[rgba(215,240,104,0.18)] px-5 py-4">
              <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-ink)]">
                Next steps · talk to a doctor
              </h3>
              {deep?.nextSteps && (
                <p className="mt-2 text-sm leading-6 text-[var(--color-ink)]">{deep.nextSteps}</p>
              )}
              {recommendedDoctors.length > 0 && (
                <div className="mt-4 space-y-3">
                  {recommendedDoctors.map((doctor, index) => {
                    const kit = doctorKits[index];
                    const isOpen = expandedDoctors.includes(index);
                    const priorityLabel =
                      doctor.priority === 'start_here' ? 'Start here'
                      : doctor.priority === 'consider_next' ? 'Consider next'
                      : 'Specialist option';
                    return (
                      <div key={`${doctor.specialty}-${index}`} className="overflow-hidden rounded-[1.2rem] bg-white/85 shadow-[0_6px_18px_rgba(86,98,145,0.1)]">
                        {/* collapsed header — always visible */}
                        <button
                          type="button"
                          onClick={() => toggleDoctor(index)}
                          className="flex w-full items-center gap-3 px-4 py-3 text-left"
                        >
                          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--color-ink)] text-sm font-bold text-white">
                            {index + 1}
                          </span>
                          <span className="text-lg shrink-0">🩺</span>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-bold text-sm text-[var(--color-ink)]">{doctor.specialty}</span>
                              <span className="rounded-full bg-[var(--color-lime)] px-2 py-0.5 text-[10px] font-bold text-[var(--color-ink)]">
                                {priorityLabel}
                              </span>
                            </div>
                            <p className="mt-0.5 text-xs leading-5 text-[var(--color-ink-soft)] line-clamp-2">
                              {doctor.reason}
                            </p>
                          </div>
                          <span className="shrink-0 text-lg font-bold text-[var(--color-ink-soft)]">
                            {isOpen ? '−' : '+'}
                          </span>
                        </button>

                        {/* expanded kit */}
                        {isOpen && kit && (
                          <div className="border-t border-[rgba(119,101,244,0.15)] px-4 pb-4 pt-3 space-y-4">
                            {kit.whatToSay && (
                              <div className="rounded-[1rem] border border-[rgba(119,101,244,0.3)] bg-[rgba(119,101,244,0.06)] px-3 py-3">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-soft)]">What to say</p>
                                <p className="mt-2 text-sm italic leading-6 text-[var(--color-ink)]">&ldquo;{kit.whatToSay}&rdquo;</p>
                              </div>
                            )}
                            {kit.openingSummary && !kit.whatToSay && (
                              <p className="text-sm leading-6 text-[var(--color-ink)]">{kit.openingSummary}</p>
                            )}
                            {kit.concerningSymptoms.length > 0 && (
                              <div>
                                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-soft)] mb-2">Symptoms to raise</p>
                                <div className="space-y-1">
                                  {kit.concerningSymptoms.map((s, si) => (
                                    <p key={si} className="text-sm leading-6 text-[var(--color-ink)]">• {s}</p>
                                  ))}
                                </div>
                              </div>
                            )}
                            {kit.recommendedTests.length > 0 && (
                              <div>
                                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-soft)] mb-2">Tests to request</p>
                                <div className="space-y-1">
                                  {kit.recommendedTests.map((t, ti) => (
                                    <p key={ti} className="text-sm leading-6 text-[var(--color-ink)]">• {t}</p>
                                  ))}
                                </div>
                              </div>
                            )}
                            {kit.discussionPoints.length > 0 && (
                              <div>
                                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-soft)] mb-2">Questions &amp; evidence</p>
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
                                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-soft)] mb-2">Bring to the appointment</p>
                                <div className="space-y-1">
                                  {kit.bringToAppointment.map((item, ii) => (
                                    <p key={ii} className="text-sm leading-6 text-[var(--color-ink)]">• {item}</p>
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

          {/* ── Coaching tips (MedGemma) ──────────────────────────────────── */}
          {coachingTips.length > 0 && (
            <div className="section-card px-5 py-5">
              <div className="mb-3 flex items-center gap-2">
                <span className="pill-tag bg-[var(--color-lime)] text-[var(--color-ink)]">
                  Energy coaching · MedGemma
                </span>
              </div>
              <h3 className="mb-4 text-lg font-bold tracking-[-0.03em] text-[var(--color-ink)]">
                Personalised coaching tips
              </h3>
              <div className="space-y-3">
                {coachingTips.map((tip, i) => (
                  <div key={i} className="rounded-[1.2rem] bg-[var(--color-card)] px-4 py-4">
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <span className="rounded-full bg-[var(--color-accent-soft)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--color-ink)]">
                        {tip.category}
                      </span>
                      <span className="text-[10px] text-[var(--color-ink-soft)]">{tip.timeframe}</span>
                    </div>
                    <p className="text-sm leading-6 text-[var(--color-ink)]">{tip.tip}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Export full report ────────────────────────────────────────── */}
          {doctorKits.length > 0 && (
            <div className="rounded-[1.6rem] bg-[#09090f] px-5 py-5 text-white shadow-[0_14px_24px_rgba(9,9,15,0.18)]">
              <h4 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/65">
                Full report
              </h4>
              <p className="mt-2 text-sm leading-6 text-white/78">
                Download all doctor kits in one PDF, or send a clean appointment note by email.
              </p>
              <div className="mt-4 flex flex-col gap-3">
                <button
                  type="button"
                  onClick={() => downloadDoctorKit()}
                  className="w-full rounded-full bg-[var(--color-lime)] px-5 py-4 text-base font-bold text-[var(--color-ink)] shadow-[0_10px_24px_rgba(9,9,15,0.18)]"
                >
                  Download full PDF
                </button>
                <button
                  type="button"
                  onClick={emailDoctorKit}
                  className="w-full rounded-full border border-white/18 bg-white/8 px-5 py-4 text-base font-bold text-white"
                >
                  Send via email
                </button>
              </div>
            </div>
          )}

          {/* ── Footer actions ────────────────────────────────────────────── */}
          <div className="flex flex-col gap-3 pt-2">
            <Link
              href="/assessment"
              className="w-full rounded-full bg-[var(--color-lime)] px-5 py-4 text-center text-base font-bold text-[var(--color-ink)] shadow-[0_10px_24px_rgba(9,9,15,0.12)] transition-all active:scale-[0.98]"
            >
              Review your answers
            </Link>
            <button
              onClick={() => {
                reset();
                window.location.href = '/assessment';
              }}
              className="w-full rounded-full border border-[rgba(9,9,15,0.16)] bg-white/75 px-5 py-4 text-base font-bold text-[var(--color-ink)] transition-all"
            >
              Retake assessment
            </button>
          </div>

          <p className="pb-2 text-center text-[11px] leading-4 text-[var(--color-ink-soft)]">
            For educational use only. Not a substitute for medical advice.
            <br />
            Results are indicative only — always discuss with a qualified clinician.
          </p>
        </div>
      </main>
    </div>
  );
}
