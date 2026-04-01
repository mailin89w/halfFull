'use client';

// Start Page — Design V3: Clinical Trust
// App color system · open layout (no hero card) · connected step tracker · trust-first · relieving

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
  { q: 'Is this medical advice?', a: 'No. HalfFull is an informational support tool. It does not provide medical advice, diagnosis, or treatment.' },
  { q: 'Can HalfFull be wrong?', a: 'Yes. Use results as structured support for a conversation with your doctor.' },
];

export default function StartDesignV3() {
  const [faqOpen, setFaqOpen] = useState(false);
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <div style={{ background: BG, minHeight: '100vh', fontFamily: BODY, maxWidth: 430, margin: '0 auto', position: 'relative' }}>

      {/* FAQ overlay */}
      {faqOpen && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, maxWidth: 430, margin: '0 auto' }}>
          <div onClick={() => setFaqOpen(false)} style={{ position: 'absolute', inset: 0, background: 'rgba(9,9,15,0.28)', backdropFilter: 'blur(4px)' }} />
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: CARD, borderRadius: '28px 28px 0 0', padding: '28px 20px 48px', maxHeight: '80vh', overflowY: 'auto', boxShadow: '0 -12px 48px rgba(86,98,145,0.14)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <span style={{ fontFamily: BODY, fontSize: 11, fontWeight: 700, color: ACCENT, textTransform: 'uppercase', letterSpacing: 2.5 }}>Frequently asked</span>
              <button onClick={() => setFaqOpen(false)} style={{ background: MUTED, border: 'none', borderRadius: '50%', width: 32, height: 32, cursor: 'pointer', fontSize: 16, color: INK }}>×</button>
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
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '22px 24px 0' }}>
        <span style={{ fontFamily: DISPLAY, fontWeight: 900, fontSize: 17, color: INK, letterSpacing: '-0.05em' }}>HalfFull</span>
        <button onClick={() => setFaqOpen(true)} style={{ background: 'rgba(255,255,255,0.55)', border: `1px solid rgba(199,206,223,0.6)`, borderRadius: 100, padding: '7px 18px', fontFamily: BODY, fontSize: 12, fontWeight: 700, color: INK_SOFT, cursor: 'pointer', letterSpacing: 0.3 }}>
          FAQ
        </button>
      </header>

      {/* Trust badge */}
      <div style={{ padding: '20px 24px 0', display: 'flex', justifyContent: 'center' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'rgba(255,255,255,0.55)', borderRadius: 100, padding: '6px 14px', border: `1px solid rgba(199,206,223,0.5)` }}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M6 1 L7.5 4.5 L11 5 L8.5 7.5 L9 11 L6 9.5 L3 11 L3.5 7.5 L1 5 L4.5 4.5 Z" fill={ACCENT} />
          </svg>
          <span style={{ fontFamily: BODY, fontSize: 11, fontWeight: 600, color: INK_SOFT }}>Clinical research · 14,000+ people · Trusted by Doctolib</span>
        </div>
      </div>

      {/* Open hero — text directly on background, no card */}
      <div style={{ padding: '28px 24px 24px' }}>
        <p style={{ fontFamily: BODY, fontSize: 11, fontWeight: 700, color: ACCENT, textTransform: 'uppercase', letterSpacing: 2.5, marginBottom: 12 }}>
          Low-energy assessment
        </p>
        <h1 style={{ fontFamily: DISPLAY, fontWeight: 900, fontSize: 38, lineHeight: 1.05, color: INK, letterSpacing: '-0.05em', wordSpacing: '0.15em', marginBottom: 14 }}>
          Finally understand<br />your fatigue
        </h1>
        <p style={{ fontFamily: BODY, fontSize: 15, color: INK_SOFT, lineHeight: 1.65, maxWidth: 300 }}>
          Tired of not being taken seriously? Get clarity before your next doctor visit.
        </p>
      </div>

      {/* Connected step tracker */}
      <div style={{ padding: '0 24px 24px' }}>
        <div style={{ background: 'rgba(255,255,255,0.55)', borderRadius: 20, padding: '20px 20px 18px', border: `1px solid rgba(199,206,223,0.5)` }}>
          {/* Connector row */}
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 14 }}>
            {[
              { n: '1', label: 'Take the quiz', color: ACCENT },
              { n: '2', label: 'Pattern analysis', color: ACCENT },
              { n: '3', label: 'Get results', color: LIME },
            ].map((step, i) => (
              <>
                <div key={`step-${i}`} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: i === 1 ? 'none' : 1 }}>
                  <div style={{ width: 36, height: 36, borderRadius: '50%', backgroundColor: step.color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <span style={{ fontFamily: DISPLAY, fontWeight: 900, fontSize: 14, color: i === 2 ? INK : '#ffffff', lineHeight: 1 }}>{step.n}</span>
                  </div>
                </div>
                {i < 2 && (
                  <div key={`line-${i}`} style={{ flex: 1, height: 2, backgroundColor: i === 0 ? ACCENT : STROKE, opacity: i === 0 ? 0.4 : 0.6, margin: '0 4px' }} />
                )}
              </>
            ))}
          </div>
          {/* Step labels */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 4, textAlign: 'center' }}>
            {[
              { label: 'Take the quiz', desc: 'Questions about your symptoms & habits.' },
              { label: 'Pattern analysis', desc: 'Matched against medical survey data.' },
              { label: 'Get results', desc: 'Up to 3 possible causes explained.' },
            ].map((s, i) => (
              <div key={i}>
                <p style={{ fontFamily: BODY, fontSize: 11, fontWeight: 700, color: INK, lineHeight: 1.3, marginBottom: 3 }}>{s.label}</p>
                <p style={{ fontFamily: BODY, fontSize: 10, color: INK_SOFT, lineHeight: 1.4, margin: 0 }}>{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Main card: What you get + CTA */}
      <div style={{ margin: '0 16px 12px', backgroundColor: CARD, borderRadius: 28, padding: '24px 24px 24px', border: `1px solid rgba(199,206,223,0.4)`, boxShadow: '0 12px 30px rgba(86,98,145,0.1)' }}>
        <p style={{ fontFamily: BODY, fontSize: 10, fontWeight: 700, color: INK_SOFT, textTransform: 'uppercase', letterSpacing: 2.5, marginBottom: 16 }}>What you get</p>
        {[
          { text: 'List of most probable causes', icon: '○' },
          { text: 'Clear next steps to look into', icon: '○' },
          { text: 'Doctor-ready summary of your situation', icon: '○' },
        ].map((item, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 0', borderBottom: i < 2 ? `1px solid ${MUTED}` : 'none' }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: ACCENT, flexShrink: 0 }} />
            <p style={{ fontFamily: BODY, fontSize: 14, fontWeight: 500, color: INK, lineHeight: 1.4, margin: 0 }}>{item.text}</p>
          </div>
        ))}

        <a href="/chapters" style={{ display: 'block', backgroundColor: LIME, color: INK, textAlign: 'center', borderRadius: 100, padding: '16px 24px', fontFamily: BODY, fontSize: 15, fontWeight: 800, textDecoration: 'none', letterSpacing: -0.2, marginTop: 20 }}>
          Start the fatigue quiz
        </a>
        <p style={{ fontFamily: BODY, fontSize: 11, color: INK_SOFT, textAlign: 'center', marginTop: 10 }}>About 10 minutes · No account needed</p>
      </div>

      {/* Comparison */}
      <div style={{ margin: '0 16px 12px', backgroundColor: CARD, borderRadius: 28, padding: '22px 24px', border: `1px solid rgba(199,206,223,0.4)`, boxShadow: '0 12px 30px rgba(86,98,145,0.1)' }}>
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
      <div style={{ padding: '8px 24px 52px', textAlign: 'center' }}>
        <p style={{ fontFamily: BODY, fontSize: 12, color: INK_SOFT, lineHeight: 1.7 }}>
          HalfFull does not provide medical diagnoses or treatment.<br />It helps you prepare for a conversation with your doctor.
        </p>
      </div>
    </div>
  );
}
