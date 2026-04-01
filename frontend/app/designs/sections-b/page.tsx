'use client';

const C = {
  ink: '#09090f',
  inkSoft: '#5f6783',
  accent: '#7765f4',
  lime: '#d7f068',
  card: '#f8f8fb',
  cardMuted: '#eaedf8',
  page: '#d8d8e3',
};

const outcomes = [
  { title: 'Probable causes ranked', desc: 'The most likely reasons behind your fatigue, ordered by how well they match your answers.' },
  { title: 'A clear action list', desc: 'Concrete next steps — what to track, what to ask your doctor, what to rule out first.' },
  { title: 'A doctor-ready summary', desc: 'A structured overview you can bring to your appointment so nothing gets missed.' },
];

const rows = [
  { halffull: 'Structured symptom input', gpt: 'One vague prompt' },
  { halffull: 'Built for fatigue specifically', gpt: 'General health advice' },
  { halffull: 'Clear ranked priorities', gpt: 'Long, unfocused answers' },
  { halffull: 'Helps you prepare for a doctor', gpt: 'Not actionable' },
];

export default function SectionsB() {
  return (
    <div style={{ background: `linear-gradient(180deg, #bcc8e8 0%, #b4bfe1 100%)`, minHeight: '100vh', display: 'flex', justifyContent: 'center', padding: '40px 16px', fontFamily: '"Space Grotesk", system-ui, sans-serif' }}>
      <div style={{ width: '100%', maxWidth: 420, display: 'flex', flexDirection: 'column', gap: 16 }}>

        <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', color: C.inkSoft, marginBottom: 4 }}>Option B</p>

        {/* What you get — left-border statements */}
        <section style={{ background: C.card, borderRadius: 24, padding: '24px 20px', boxShadow: '0 14px 30px rgba(86,98,145,0.13)' }}>
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: C.accent, marginBottom: 20 }}>What you get</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {outcomes.map((item, i) => (
              <div key={item.title} style={{
                borderLeft: `3px solid ${C.accent}`,
                paddingLeft: 16,
                paddingBottom: i < outcomes.length - 1 ? 20 : 0,
                marginBottom: i < outcomes.length - 1 ? 20 : 0,
                borderBottom: i < outcomes.length - 1 ? `1px solid rgba(151,166,210,0.18)` : 'none',
              }}>
                <p style={{ fontSize: 17, fontWeight: 800, color: C.ink, letterSpacing: '-0.03em', lineHeight: 1.2, marginBottom: 6, fontFamily: '"Archivo", "Arial Narrow", sans-serif' }}>{item.title}</p>
                <p style={{ fontSize: 13, color: C.inkSoft, lineHeight: 1.6 }}>{item.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Comparison — split card */}
        <section style={{ background: C.card, borderRadius: 24, overflow: 'hidden', boxShadow: '0 14px_30px rgba(86,98,145,0.13)' }}>
          {/* Column headers */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
            <div style={{ background: C.ink, padding: '16px 20px' }}>
              <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: C.lime, marginBottom: 2 }}>With HalfFull</p>
              <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)' }}>Structured clarity</p>
            </div>
            <div style={{ background: C.cardMuted, padding: '16px 20px', borderLeft: '1px solid rgba(151,166,210,0.22)' }}>
              <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: C.inkSoft, marginBottom: 2 }}>With GPT</p>
              <p style={{ fontSize: 12, color: 'rgba(95,103,131,0.55)' }}>Generic guessing</p>
            </div>
          </div>
          {/* Rows */}
          {rows.map((row, i) => (
            <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', borderTop: '1px solid rgba(151,166,210,0.16)' }}>
              <div style={{ padding: '14px 20px', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                <span style={{ color: C.lime, marginTop: 1, background: C.ink, borderRadius: '50%', width: 18, height: 18, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: 10, fontWeight: 900 }}>✓</span>
                <p style={{ fontSize: 13, fontWeight: 600, color: C.ink, lineHeight: 1.5 }}>{row.halffull}</p>
              </div>
              <div style={{ padding: '14px 20px', borderLeft: '1px solid rgba(151,166,210,0.16)', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                <span style={{ color: 'rgba(151,166,210,0.5)', fontSize: 10, marginTop: 2, flexShrink: 0 }}>✕</span>
                <p style={{ fontSize: 13, color: 'rgba(95,103,131,0.65)', lineHeight: 1.5, fontStyle: 'italic' }}>{row.gpt}</p>
              </div>
            </div>
          ))}
        </section>

      </div>
    </div>
  );
}
