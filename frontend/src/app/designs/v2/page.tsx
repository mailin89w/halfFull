// Design V2 — Lavender Editorial
// Reference: TABU app — periwinkle background, oversized heavy type, white data cards, quirky blob character

const areas = [
  { label: 'Sleep Quality',  pct: 85, color: '#6B6BDC' },
  { label: 'Iron & Anemia',  pct: 78, color: '#6B6BDC' },
  { label: 'Nutrition',      pct: 60, color: '#9090CC' },
  { label: 'Thyroid',        pct: 55, color: '#9090CC' },
  { label: 'Mental Health',  pct: 45, color: '#B8B8E4' },
];

const tests = [
  'Full blood count + ferritin',
  'Thyroid panel — TSH & free T4',
  'Sleep study referral',
  'Vitamin D + B12 + folate',
];

function BlobCharacter() {
  return (
    <svg width="100" height="100" viewBox="0 0 100 100" fill="none">
      {/* Body blob */}
      <path d="M20 65 C18 50 22 38 30 32 C38 26 50 24 60 28 C70 32 76 42 74 56 C72 68 64 76 52 78 C40 80 22 80 20 65Z" fill="#4A4AB8"/>
      {/* Head */}
      <circle cx="50" cy="30" r="18" fill="#3535A0"/>
      {/* Eyes */}
      <circle cx="44" cy="27" r="3.5" fill="white"/>
      <circle cx="56" cy="27" r="3.5" fill="white"/>
      <circle cx="45" cy="28" r="1.8" fill="#1A1A3A"/>
      <circle cx="57" cy="28" r="1.8" fill="#1A1A3A"/>
      {/* Eye shine */}
      <circle cx="46" cy="27" r="0.8" fill="white"/>
      <circle cx="58" cy="27" r="0.8" fill="white"/>
      {/* Smile */}
      <path d="M44 34 Q50 40 56 34" stroke="white" strokeWidth="2.2" strokeLinecap="round" fill="none"/>
      {/* Left arm */}
      <path d="M22 58 Q10 52 14 42" stroke="#4A4AB8" strokeWidth="7" strokeLinecap="round"/>
      {/* Right arm — holding something up */}
      <path d="M76 55 Q88 45 82 36" stroke="#4A4AB8" strokeWidth="7" strokeLinecap="round"/>
      {/* Hand sparkle */}
      <path d="M83 32 L84.5 28 L86 32 L90 33.5 L86 35 L84.5 39 L83 35 L79 33.5Z" fill="#B8B8E4"/>
    </svg>
  );
}

export default function DesignV2() {
  return (
    <div style={{ backgroundColor: '#DCDCF0', minHeight: '100vh', fontFamily: 'system-ui, -apple-system, sans-serif', maxWidth: 430, margin: '0 auto' }}>

      {/* Nav */}
      <nav style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '22px 24px' }}>
        <span style={{ fontWeight: 900, fontSize: 17, color: '#1A1A1A', letterSpacing: -0.5 }}>HalfFull</span>
        <a href="/designs" style={{ fontSize: 11, fontWeight: 700, color: '#8080A8', textTransform: 'uppercase', letterSpacing: 1.5, textDecoration: 'none' }}>← All</a>
      </nav>

      {/* Massive headline */}
      <div style={{ padding: '0 24px 20px' }}>
        <p style={{ fontSize: 13, fontWeight: 600, color: '#8080A8', marginBottom: 6, letterSpacing: 0.2 }}>Assessment complete</p>
        <h1 style={{ fontSize: 54, fontWeight: 900, lineHeight: 0.9, color: '#1A1A1A', letterSpacing: -3, marginBottom: 0 }}>
          YOUR<br />ENERGY<br />REPORT
        </h1>
      </div>

      {/* Score + character row */}
      <div style={{ padding: '0 24px', display: 'flex', gap: 12, marginBottom: 16 }}>

        {/* Score card */}
        <div style={{ flex: 1, backgroundColor: '#FFFFFF', borderRadius: 24, padding: '20px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', minHeight: 200 }}>
          <p style={{ fontSize: 10, fontWeight: 700, color: '#8080A8', textTransform: 'uppercase', letterSpacing: 1.8 }}>Score now</p>

          <div>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3 }}>
              <span style={{ fontSize: 68, fontWeight: 900, lineHeight: 1, color: '#1A1A1A', letterSpacing: -4 }}>17</span>
              <span style={{ fontSize: 14, color: '#A0A0C0', marginBottom: 8, fontWeight: 600 }}>/100</span>
            </div>
            <p style={{ fontSize: 13, fontWeight: 800, color: '#6B6BDC', marginTop: 2 }}>Depleted</p>
          </div>

          {/* Mini bar chart — shows journey */}
          <div>
            <div style={{ display: 'flex', gap: 4, alignItems: 'flex-end', height: 44 }}>
              {[17, 28, 40, 54, 67].map((h, i) => (
                <div key={i} style={{ flex: 1, borderRadius: '4px 4px 0 0', backgroundColor: i === 0 ? '#6B6BDC' : i === 4 ? '#C7D9A7' : '#E8E8F4', height: `${(h / 70) * 100}%` }} />
              ))}
            </div>
            <p style={{ fontSize: 10, color: '#B0B0CC', marginTop: 6, fontWeight: 600 }}>Now → Potential: 67</p>
          </div>
        </div>

        {/* Character card */}
        <div style={{ width: 148, backgroundColor: '#6B6BDC', borderRadius: 24, padding: '20px 16px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'space-between' }}>
          <p style={{ fontSize: 10, fontWeight: 700, color: 'rgba(255,255,255,0.6)', textTransform: 'uppercase', letterSpacing: 1.5 }}>Potential</p>
          <BlobCharacter />
          <div style={{ textAlign: 'center' }}>
            <p style={{ fontSize: 44, fontWeight: 900, color: '#FFFFFF', lineHeight: 1, letterSpacing: -2 }}>67</p>
            <p style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.65)', marginTop: 2 }}>Good energy</p>
          </div>
        </div>
      </div>

      {/* Concern bars */}
      <div style={{ padding: '0 24px 16px' }}>
        <div style={{ backgroundColor: '#FFFFFF', borderRadius: 24, padding: '22px 22px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 20 }}>
            <div>
              <p style={{ fontSize: 10, fontWeight: 700, color: '#8080A8', textTransform: 'uppercase', letterSpacing: 1.8, marginBottom: 4 }}>Findings</p>
              <h2 style={{ fontSize: 20, fontWeight: 900, color: '#1A1A1A', letterSpacing: -0.5 }}>5 areas flagged</h2>
            </div>
            <span style={{ fontSize: 11, fontWeight: 700, color: '#B0B0CC' }}>Concern level</span>
          </div>

          {areas.map((item, i) => (
            <div key={i} style={{ marginBottom: i < areas.length - 1 ? 16 : 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 7 }}>
                <span style={{ fontSize: 14, fontWeight: 700, color: '#1A1A1A' }}>{item.label}</span>
                <span style={{ fontSize: 13, fontWeight: 800, color: item.color }}>{item.pct}%</span>
              </div>
              <div style={{ height: 9, backgroundColor: '#EEEEF8', borderRadius: 100, overflow: 'hidden' }}>
                <div style={{ width: `${item.pct}%`, height: '100%', backgroundColor: item.color, borderRadius: 100 }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Doctor card — dark */}
      <div style={{ padding: '0 24px 20px' }}>
        <div style={{ backgroundColor: '#1A1A3A', borderRadius: 24, padding: '22px 22px' }}>
          <p style={{ fontSize: 10, fontWeight: 700, color: '#6B6BDC', textTransform: 'uppercase', letterSpacing: 1.8, marginBottom: 4 }}>Next step</p>
          <h2 style={{ fontSize: 20, fontWeight: 900, color: '#FFFFFF', marginBottom: 18, letterSpacing: -0.4 }}>Bring to your doctor</h2>
          {tests.map((test, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, paddingTop: 13, paddingBottom: 13, borderBottom: i < tests.length - 1 ? '1px solid rgba(255,255,255,0.07)' : 'none' }}>
              <div style={{ width: 28, height: 28, borderRadius: '50%', border: '2px solid #6B6BDC', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 800, color: '#6B6BDC', flexShrink: 0 }}>
                {i + 1}
              </div>
              <span style={{ fontSize: 14, color: 'rgba(255,255,255,0.82)', fontWeight: 500 }}>{test}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Closing quote block */}
      <div style={{ margin: '0 24px 52px', backgroundColor: '#6B6BDC', borderRadius: 24, padding: '28px 24px', textAlign: 'center' }}>
        <p style={{ fontSize: 24, fontWeight: 900, color: '#FFFFFF', lineHeight: 1.25, letterSpacing: -0.8 }}>
          "These patterns<br />are recoverable."
        </p>
        <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.55)', marginTop: 10, fontWeight: 500 }}>
          Based on your assessment responses
        </p>
      </div>
    </div>
  );
}
