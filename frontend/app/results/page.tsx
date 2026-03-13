'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import type { jsPDF as JsPDFType } from 'jspdf';
import { useAssessment } from '@/src/hooks/useAssessment';
import { computeResults } from '@/src/lib/mockResults';
import {
  getInsightForDiagnosis,
  readStoredDeepResult,
} from '@/src/lib/medgemma';
import type { DeepMedGemmaResult } from '@/src/lib/medgemma';
import { EnergySpectrum } from '@/src/components/results/EnergySpectrum';
import { DiagnosisCard } from '@/src/components/results/DiagnosisCard';
import { DoctorPriority } from '@/src/components/results/DoctorPriority';
import { BlobCharacter } from '@/src/components/ui/BlobCharacter';

export default function ResultsPage() {
  const { answers, hydrated, reset } = useAssessment();
  const [deep, setDeep] = useState<DeepMedGemmaResult | null>(null);
  const [doctorKitOpen, setDoctorKitOpen] = useState(false);

  const { currentPct, projectedPct, summaryLine, diagnoses, doctors } =
    computeResults(answers);

  // Load deep analysis result from session storage (written by /processing)
  useEffect(() => {
    if (!hydrated) return;
    const stored = readStoredDeepResult();
    setDeep(stored);
  }, [hydrated]);

  // ── Doctor kit content: AI-generated if available, rule-based as fallback ──
  const concerningSummary = diagnoses
    .slice(0, 4)
    .map((d) => `${d.title}: ${d.description}`)
    .join(' ');

  const doctorKitOpener = deep?.doctorKitSummary ?? null;

  const doctorQuestions =
    deep?.doctorKitQuestions ??
    diagnoses.slice(0, 3).map((d) => {
      const leadTest = d.tests[0]?.name;
      return leadTest
        ? `Could ${d.title.toLowerCase()} explain this pattern, and should we check ${leadTest}?`
        : `Could ${d.title.toLowerCase()} explain this pattern?`;
    });

  const doctorArguments =
    deep?.doctorKitArguments ??
    diagnoses
      .flatMap((d) =>
        d.tests.filter((t) => t.mustRequest).map((t) => ({
          diagnosis: d.title,
          test: t.name,
          note: t.note,
        }))
      )
      .slice(0, 4)
      .map(
        (item) =>
          `Because ${item.diagnosis.toLowerCase()} is flagged, ask for ${item.test}${item.note ? ` — ${item.note}` : '.'}`
      );

  const coachingTips = deep?.coachingTips ?? [];

  // ── Export helpers ───────────────────────────────────────────────────────
  const downloadDoctorKit = async () => {
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

    // ── Questions for the doctor ─────────────────────────────────────────
    addSectionHeader('Questions for the doctor');
    doctorQuestions.forEach((q, i) => addBullet(q, i + 1));
    y += 2;

    // ── Arguments for tests ──────────────────────────────────────────────
    addSectionHeader('Arguments for requesting additional tests');
    doctorArguments.forEach((a, i) => addBullet(a, i + 1));
    y += 2;

    // ── MedGemma next steps ──────────────────────────────────────────────
    if (deep?.nextSteps) {
      addSectionHeader('Personalised next steps');
      addText(deep.nextSteps, { size: 10, indent: 2 });
      y += 2;
    }

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

    doc.save('halffull-doctor-kit.pdf');
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
        'Questions:',
        ...doctorQuestions.map((q) => `- ${q}`),
        '',
        'Test requests:',
        ...doctorArguments.map((a) => `- ${a}`),
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
          <Link
            href="/assessment"
            className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--color-ink-soft)] transition-colors"
          >
            Review
          </Link>
        </div>
      </header>

      <main className="flex-1 px-5 py-4 pb-10">
        <div className="max-w-lg mx-auto flex flex-col gap-5">

          {/* ── Hero ──────────────────────────────────────────────────────── */}
          <section className="relative overflow-hidden rounded-[2rem] bg-[var(--color-card)] px-5 py-6 shadow-[0_14px_30px_rgba(86,98,145,0.14)]">
            <div className="mb-3 flex items-start justify-between gap-4">
              <div className="pointer-events-none absolute right-8 top-[5.4rem] z-10">
                <BlobCharacter className="h-14 w-14" accent="lime" mood="gentle" />
              </div>
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

          {/* ── MedGemma personalised summary ─────────────────────────────── */}
          {deep?.personalizedSummary ? (
            <div className="section-card border-[var(--color-lime)] px-5 py-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="pill-tag bg-[var(--color-lime)] text-[var(--color-ink)]">
                  Personalised insight · MedGemma
                </span>
              </div>
              <p className="text-sm leading-6 text-[var(--color-ink)]">
                {deep.personalizedSummary}
              </p>
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
              />
            ))}
          </div>

          {/* ── MedGemma next steps ───────────────────────────────────────── */}
          {deep?.nextSteps && (
            <div className="section-card border-[var(--color-lime)] bg-[rgba(215,240,104,0.18)] px-5 py-4">
              <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-ink)]">
                Your personalised next steps
              </h3>
              <p className="mt-2 text-sm leading-6 text-[var(--color-ink)]">{deep.nextSteps}</p>
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

          {/* ── Doctor priority ───────────────────────────────────────────── */}
          <DoctorPriority doctors={doctors} />

          {/* ── Doctor visit kit ──────────────────────────────────────────── */}
          <div className="overflow-hidden rounded-[2rem] border border-[rgba(119,101,244,0.35)] bg-[linear-gradient(180deg,rgba(119,101,244,0.2)_0%,rgba(215,240,104,0.28)_100%)] shadow-[0_22px_44px_rgba(86,98,145,0.22)]">
            <button
              type="button"
              onClick={() => setDoctorKitOpen((v) => !v)}
              className="flex w-full items-center justify-between px-5 py-5 text-left"
            >
              <div>
                <span className="pill-tag mb-3 bg-[var(--color-lime)] text-[var(--color-ink)]">
                  {deep?.doctorKitSummary ? 'AI-powered · MedGemma' : 'Core appointment prep'}
                </span>
                <h3 className="text-[1.9rem] font-bold tracking-[-0.05em] text-[var(--color-ink)]">
                  Doctor visit kit
                </h3>
                <p className="mt-1 max-w-[18rem] text-sm leading-6 text-[rgba(9,9,15,0.65)]">
                  Bring one clean brief into the appointment: symptom summary, discussion prompts, and reasons to ask for deeper testing.
                </p>
              </div>
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white/70 text-xl font-bold text-[var(--color-ink)] shadow-[0_8px_18px_rgba(86,98,145,0.12)]">
                {doctorKitOpen ? '−' : '+'}
              </span>
            </button>

            {doctorKitOpen && (
              <div className="border-t border-[rgba(119,101,244,0.22)] bg-[rgba(248,248,251,0.96)] px-5 py-5">
                <div className="space-y-4">

                  {/* Opening statement (AI-generated) */}
                  {doctorKitOpener && (
                    <div className="rounded-[1.4rem] border border-[rgba(119,101,244,0.3)] bg-[rgba(119,101,244,0.06)] px-4 py-4">
                      <h4 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-ink-soft)]">
                        How to open the appointment
                      </h4>
                      <p className="mt-2 text-sm italic leading-6 text-[var(--color-ink)]">
                        &ldquo;{doctorKitOpener}&rdquo;
                      </p>
                    </div>
                  )}

                  {/* Concerning symptoms */}
                  <div className="rounded-[1.4rem] bg-white px-4 py-4 shadow-[0_10px_20px_rgba(86,98,145,0.08)]">
                    <h4 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-ink-soft)]">
                      Concerning symptoms gathered in the assessment
                    </h4>
                    <p className="mt-2 text-sm leading-6 text-[var(--color-ink)]">
                      {concerningSummary}
                    </p>
                  </div>

                  {/* Questions for the doctor */}
                  <div className="rounded-[1.4rem] bg-white px-4 py-4 shadow-[0_10px_20px_rgba(86,98,145,0.08)]">
                    <h4 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-ink-soft)]">
                      Questions for the doctor
                    </h4>
                    <div className="mt-3 space-y-3">
                      {doctorQuestions.map((question, index) => (
                        <div key={index} className="flex gap-3">
                          <span className="mt-1 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-[var(--color-accent-soft)] text-[10px] font-bold text-[var(--color-ink)]">
                            {index + 1}
                          </span>
                          <p className="text-sm leading-6 text-[var(--color-ink)]">{question}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Arguments for tests */}
                  <div className="rounded-[1.4rem] bg-white px-4 py-4 shadow-[0_10px_20px_rgba(86,98,145,0.08)]">
                    <h4 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-ink-soft)]">
                      Convincing arguments for additional tests
                    </h4>
                    <div className="mt-3 space-y-3">
                      {doctorArguments.map((argument, index) => (
                        <div key={index} className="rounded-[1rem] bg-[rgba(119,101,244,0.06)] px-3 py-3">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-soft)]">
                            Test argument {index + 1}
                          </p>
                          <p className="mt-1 text-sm leading-6 text-[var(--color-ink)]">{argument}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Export actions */}
                  <div className="rounded-[1.4rem] bg-[#09090f] px-4 py-4 text-white shadow-[0_14px_24px_rgba(9,9,15,0.18)]">
                    <h4 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/65">
                      Share this report
                    </h4>
                    <p className="mt-2 text-sm leading-6 text-white/78">
                      Export a polished summary for printing or send a clean appointment note by email.
                    </p>
                    <div className="mt-4 flex flex-col gap-3">
                      <button
                        type="button"
                        onClick={downloadDoctorKit}
                        className="w-full rounded-full bg-[var(--color-lime)] px-5 py-4 text-base font-bold text-[var(--color-ink)] shadow-[0_10px_24px_rgba(9,9,15,0.18)]"
                      >
                        Download PDF summary
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
                </div>
              </div>
            )}
          </div>

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
