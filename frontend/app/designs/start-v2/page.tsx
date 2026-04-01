'use client';

// Start Page — Design V2: Bold Dark Hero
// App color system · Archivo display · ink-colored hero card · lime CTA · editorial step numbers

import { useState } from 'react';

const INK       = '#09090f';
const INK_SOFT  = '#5f6783';
const ACCENT    = '#7765f4';
const LIME      = '#d7f068';
const CARD      = '#f8f8fb';
const MUTED     = '#eaedf8';
const STROKE    = '#c7cedf';
const DISPLAY   = 'Archivo, "Arial Narrow", sans-serif';
const BODY      = '"Space Grotesk", system-ui, sans-serif';
const BG        = 'linear-gradient(180deg, #bcc8e8 0%, #b4bfe1 100%)';

const faqs = [
  { q: 'What does HalfFull actually do?', a: 'HalfFull guides you through a short questionnaire and turns your answers into possible causes, clear priorities, and a summary you can bring to your doctor.' },
  { q: 'Does it give me a diagnosis?', a: 'No. It does not diagnose conditions. It helps you organize what may be worth discussing with a clinician.' },
  { q: 'How long does it take?', a: 'Most people finish in about 10 minutes.' },
  { q: 'Is it still useful if I do not have lab values?', a: 'Yes. It can still be useful based on symptoms and history alone.' },
  { q: 'Does this replace seeing a doctor?', a: 'No. It is meant to support a doctor visit, not replace one.' },
  { q: 'Is my data safe?', a: 'Your answers stay within the product experience needed to generate your results.' },
  { q: 'Is this medical advice?', a: 'No. HalfFull is an informational support tool.' },
  { q: 'Can HalfFull be wrong?', a: 'Yes. Use results as structured support for a conversation with your doctor.' },
];

function SplitWordmark() {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 0 }}>
      <span style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 18, color: INK_SOFT, letterSpacing: 0 }}>half</span>
      <span style={{ fontFamily: DISPLAY, fontWeight: 900, fontSize: 18, color: INK, letterSpacing: '-0.04em' }}>Full</span>
    </div>
  );
}

export default function StartDesignV2() {
  const [faqOpen, setFaqOpen] = useState(false);
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <div style={{ background: BG, minHeight: '100vh', fontFamily: BODY, maxWidth: 430, margin: '0 auto', position: 'relative' }}>

      {/* FAQ overlay */}
      {faqOpen && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, maxWidth: 430, margin: '0 auto' }}>
          <div onClick={() => setFaqOpen(false)} style={{ position: 'absolute', inset: 0, background: 'rgba(9,9,15,0.4)', backdropFilter: 'blur(6px)' }} />
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: CARD, borderRadius: '28px 28px 0 0', padding: '28px 20px 48px', maxHeight: '80vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <span style={{ fontFamily: BODY, fontSize: 11, fontWeight: 700, color: ACCENT, textTransform: 'uppercase', letterSpacing: 2.5 }}>FAQ</span>
              <button onClick={() => setFaqOpen(false)} style={{ background: MUTED, border: 'none', borderRadius: '50%', width: 32, height: 32, cursor: 'pointer', fontSize: 18, color: INK }}>×</button>
            </div>
            {faqs.map((item, i) => (
              <div key={i} style={{ borderBottom: `1px solid ${STROKE}`, padding: '13px 0' }}>
                <button onClick={() => setOpenIndex(openIndex === i ? null : i)} style={{ background: 'none', border: 'none', cursor: 'pointer', width: '100%', textAlign: 'left', display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                  <span style={{ fontFamily: BODY, fontSize: 14, fontWeight: 600, color: INK, lineHeight: 1.4 }}>{item.q}</span>
                  <span style={{ color: ACCENT, flexShrink: 0, fontWeight: 700, marginTop: 2 }}>{openIndex === i ? '−' : '+'}</span>
                </button>
                {openIndex === i && <p style={{ fontFamily: BODY, fontSize: 13, color: INK_SOFT, lineHeight: 1.65, marginTop: 10 }}>{item.a}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Header */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '22px 20px 16px' }}>
        <SplitWordmark />
        <button onClick={() => setFaqOpen(true)} style={{ background: 'rgba(9,9,15,0.1)', border: `1px solid rgba(9,9,15,0.16)`, borderRadius: 100, width: 36, height: 36, cursor: 'pointer', fontFamily: BODY, fontSize: 14, color: INK, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700 }}>
          ?
        </button>
      </header>

      <div style={{ padding: '0 16px 52px' }}>

        {/* Hero — ink-dark card */}
        <div style={{ marginBottom: 12, padding: '32px 24px 28px', backgroundColor: INK, borderRadius: 28 }}>
          <p style={{ fontFamily: BODY, fontSize: 10, fontWeight: 700, color: ACCENT, textTransform: 'uppercase', letterSpacing: 2.5, marginBottom: 16 }}>
            Low-energy assessment
          </p>
          <h1 style={{ fontFamily: DISPLAY, fontWeight: 900, fontSize: 42, lineHeight: 1.0, color: '#ffffff', letterSpacing: '-0.05em', wordSpacing: '0.2em', marginBottom: 18 }}>
            Finally<br />understand<br />your fatigue
          </h1>
          <p style={{ fontFamily: BODY, fontSize: 15, color: 'rgba(255,255,255,0.54)', lineHeight: 1.65, marginBottom: 26, maxWidth: 260 }}>
            Tired of not being taken seriously? Get clarity before your next doctor visit.
          </p>

          {/* How it works — large editorial step numbers */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 4, marginBottom: 26 }}>
            {[
              { num: '01', pre: 'Take the', verb: 'quiz', desc: 'Answer questions about your symptoms.', accent: ACCENT },
              { num: '02', pre: 'Pattern', verb: 'analysis', desc: 'Matched against medical survey data.', accent: '#b09ef8' },
              { num: '03', pre: 'Get your', verb: 'results', desc: 'Up to 3 possible causes explained.', accent: LIME },
            ].map((s, i) => (
              <div key={i} style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontFamily: DISPLAY, fontSize: 30, fontWeight: 900, color: s.accent, lineHeight: 1, letterSpacing: '-0.06em', marginBottom: 6, opacity: 0.9 }}>{s.num}</span>
                <p style={{ fontFamily: BODY, fontSize: 11, fontWeight: 700, color: 'rgba(255,255,255,0.88)', lineHeight: 1.35, marginBottom: 4 }}>
                  {s.pre} <span style={{ color: s.accent }}>{s.verb}</span>
                </p>
                <p style={{ fontFamily: BODY, fontSize: 10, color: 'rgba(255,255,255,0.38)', lineHeight: 1.5, margin: 0 }}>{s.desc}</p>
              </div>
            ))}
          </div>

          <a href="/chapters" style={{ display: 'block', backgroundColor: LIME, color: INK, textAlign: 'center', borderRadius: 100, padding: '16px 24px', fontFamily: BODY, fontSize: 15, fontWeight: 800, textDecoration: 'none', letterSpacing: -0.2 }}>
            Start the fatigue quiz
          </a>
        </div>

        {/* What you get */}
        <div style={{ marginBottom: 12, backgroundColor: CARD, borderRadius: 28, padding: '22px 24px', border: `1px solid rgba(199,206,223,0.4)`, boxShadow: '0 12px 30px rgba(86,98,145,0.1)' }}>
          <p style={{ fontFamily: BODY, fontSize: 10, fontWeight: 700, color: INK_SOFT, textTransform: 'uppercase', letterSpacing: 2.5, marginBottom: 16 }}>What you get</p>
          {['List of most probable causes', 'Clear next steps to look into', 'Doctor-ready summary of your situation'].map((item, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: i < 2 ? 13 : 0 }}>
              <span style={{ fontSize: 13, color: ACCENT, fontWeight: 900, flexShrink: 0, marginTop: 3 }}>✓</span>
              <p style={{ fontFamily: BODY, fontSize: 14, fontWeight: 600, color: INK, lineHeight: 1.5, margin: 0 }}>{item}</p>
            </div>
          ))}
        </div>

        {/* Comparison */}
        <div style={{ marginBottom: 12, backgroundColor: CARD, borderRadius: 28, padding: '22px 24px', border: `1px solid rgba(199,206,223,0.4)`, boxShadow: '0 12px 30px rgba(86,98,145,0.1)' }}>
          <p style={{ fontFamily: BODY, fontSize: 10, fontWeight: 700, color: INK_SOFT, textTransform: 'uppercase', letterSpacing: 2.5, marginBottom: 16 }}>Built for fatigue</p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
            <div style={{ fontFamily: BODY, fontSize: 11, fontWeight: 700, color: INK, textTransform: 'uppercase', letterSpacing: 1, paddingBottom: 9, borderBottom: `1px solid ${STROKE}`, textAlign: 'center' }}>HalfFull</div>
            <div style={{ fontFamily: BODY, fontSize: 11, fontWeight: 700, color: INK_SOFT, textTransform: 'uppercase', letterSpacing: 1, paddingBottom: 9, borderBottom: `1px solid ${STROKE}`, textAlign: 'center' }}>Generic AI</div>
            {[['Structured symptom input','One vague prompt'],['Built for fatigue specifically','General health advice'],['Clear priorities','Long, unfocused answers'],['Helps you prepare for a doctor','Not actionable']].map(([a, b], i, arr) => (
              <>
                <div key={`a${i}`} style={{ fontFamily: BODY, fontSize: 13, color: INK, fontWeight: 500, padding: '10px 8px 10px 0', borderBottom: i < arr.length - 1 ? `1px solid ${MUTED}` : 'none' }}>{a}</div>
                <div key={`b${i}`} style={{ fontFamily: BODY, fontSize: 13, color: INK_SOFT, padding: '10px 0 10px 8px', borderBottom: i < arr.length - 1 ? `1px solid ${MUTED}` : 'none', borderLeft: `1px solid ${STROKE}` }}>{b}</div>
              </>
            ))}
          </div>
        </div>

        {/* Disclaimer */}
        <p style={{ fontFamily: BODY, fontSize: 12, color: INK_SOFT, lineHeight: 1.7, textAlign: 'center', padding: '8px 8px 0' }}>
          Based on clinical research · Used by 14,000+ people<br />
          HalfFull does not provide medical diagnoses or treatment.
        </p>
      </div>
    </div>
  );
}
