// Design V3 — White & Pink Wellness
// Reference: Meditation app — pure white, glowing pink orb, airy whitespace, thin lines, calm

const focusAreas = [
  { label: 'Sleep',          note: 'Quality & disruption patterns',          tag: 'Priority',    tagColor: '#E87FAA' },
  { label: 'Iron & Anemia',  note: 'Most common treatable cause',            tag: 'Priority',    tagColor: '#E87FAA' },
  { label: 'Nutrition',      note: 'Supplement gaps for plant-based diet',   tag: 'Investigate', tagColor: '#9090C4' },
  { label: 'Thyroid',        note: 'Often missed — highly treatable',        tag: 'Investigate', tagColor: '#9090C4' },
  { label: 'Mental Health',  note: 'Mood & energy are tightly linked',       tag: 'Monitor',     tagColor: '#B0B0C8' },
];

const tests = [
  'Full blood count + ferritin',
  'Thyroid panel — TSH & free T4',
  'Sleep study referral',
  'Vitamin D + B12 + folate',
];

export default function DesignV3() {
  return (
    <div style={{ backgroundColor: '#F6F6FC', minHeight: '100vh', fontFamily: 'system-ui, -apple-system, sans-serif', maxWidth: 430, margin: '0 auto' }}>

      {/* Nav */}
      <nav style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '22px 28px' }}>
        <span style={{ fontWeight: 700, fontSize: 16, color: '#2D2D3A', letterSpacing: -0.3 }}>HalfFull</span>
        <a href="/designs" style={{ fontSize: 11, fontWeight: 600, color: '#A0A0B8', textTransform: 'uppercase', letterSpacing: 1.5, textDecoration: 'none' }}>← All</a>
      </nav>

      {/* Intro text */}
      <div style={{ padding: '4px 28px 0' }}>
        <p style={{ fontSize: 14, color: '#A0A0B8', marginBottom: 5, fontWeight: 500 }}>Your results are ready</p>
        <h1 style={{ fontSize: 30, fontWeight: 700, color: '#2D2D3A', lineHeight: 1.2, letterSpacing: -0.8 }}>
          Here's your<br />energy picture
        </h1>
      </div>

      {/* Glowing orb hero */}
      <div style={{ position: 'relative', display: 'flex', justifyContent: 'center', padding: '32px 0 20px', overflow: 'hidden' }}>

        {/* Outer glow rings */}
        <div style={{ position: 'absolute', width: 300, height: 300, borderRadius: '50%', background: 'radial-gradient(circle, rgba(232,127,170,0.10) 0%, transparent 70%)', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }} />
        <div style={{ position: 'absolute', width: 220, height: 220, borderRadius: '50%', background: 'radial-gradient(circle, rgba(232,127,170,0.16) 0%, transparent 70%)', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }} />

        {/* Main orb */}
        <div style={{ width: 168, height: 168, borderRadius: '50%', background: 'radial-gradient(circle at 32% 30%, #FFCADA, #E87FAA 60%, #D0608E)', boxShadow: '0 16px 60px rgba(220,100,150,0.38), 0 4px 20px rgba(220,100,150,0.22)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', position: 'relative', zIndex: 1 }}>
          <span style={{ fontSize: 56, fontWeight: 700, color: 'white', lineHeight: 1, letterSpacing: -3 }}>17</span>
          <span style={{ fontSize: 14, color: 'rgba(255,255,255,0.75)', fontWeight: 500, marginTop: 2 }}>out of 100</span>
        </div>

        {/* Floating sparkles */}
        <svg width="320" height="260" viewBox="0 0 320 260" style={{ position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%)', pointerEvents: 'none' }} fill="none">
          {/* Small 4-point stars scattered around */}
          <path d="M80 50 L81.5 45 L83 50 L88 51.5 L83 53 L81.5 58 L80 53 L75 51.5Z" fill="rgba(232,127,170,0.45)"/>
          <path d="M240 40 L241 36 L242 40 L246 41 L242 42 L241 46 L240 42 L236 41Z" fill="rgba(232,127,170,0.35)"/>
          <path d="M60 150 L61 147 L62 150 L65 151 L62 152 L61 155 L60 152 L57 151Z" fill="rgba(232,127,170,0.3)"/>
          <path d="M258 130 L259 127 L260 130 L263 131 L260 132 L259 135 L258 132 L255 131Z" fill="rgba(232,127,170,0.28)"/>
          <path d="M100 200 L101 197 L102 200 L105 201 L102 202 L101 205 L100 202 L97 201Z" fill="rgba(232,127,170,0.22)"/>
          <path d="M220 210 L221 208 L222 210 L224 211 L222 212 L221 214 L220 212 L218 211Z" fill="rgba(232,127,170,0.2)"/>
          {/* Thin curved lines */}
          <path d="M270 80 Q290 100 280 130" stroke="rgba(232,127,170,0.18)" strokeWidth="1.5" fill="none"/>
          <path d="M50 90 Q30 110 40 140" stroke="rgba(232,127,170,0.15)" strokeWidth="1.5" fill="none"/>
        </svg>
      </div>

      {/* Score labels */}
      <div style={{ textAlign: 'center', padding: '0 28px 8px' }}>
        <p style={{ fontSize: 20, fontWeight: 700, color: '#2D2D3A', marginBottom: 6, letterSpacing: -0.4 }}>Depleted</p>
        <p style={{ fontSize: 14, color: '#A0A0B8', lineHeight: 1.5 }}>
          With care, you could reach{' '}
          <strong style={{ color: '#E87FAA', fontWeight: 700 }}>67/100 — Good energy</strong>
        </p>
      </div>

      {/* Thin divider */}
      <div style={{ height: 1, backgroundColor: '#EAEAF2', margin: '20px 28px' }} />

      {/* Focus areas */}
      <div style={{ padding: '0 28px' }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, color: '#2D2D3A', marginBottom: 18, letterSpacing: -0.3 }}>Areas to focus on</h2>

        {focusAreas.map((item, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 15, paddingBottom: 15, borderBottom: i < focusAreas.length - 1 ? '1px solid #EAEAF2' : 'none' }}>
            <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
              {/* Icon dot */}
              <div style={{ width: 38, height: 38, borderRadius: 13, backgroundColor: `${item.tagColor}18`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <div style={{ width: 11, height: 11, borderRadius: '50%', backgroundColor: item.tagColor }} />
              </div>
              <div>
                <p style={{ fontSize: 15, fontWeight: 600, color: '#2D2D3A', marginBottom: 3, letterSpacing: -0.2 }}>{item.label}</p>
                <p style={{ fontSize: 12, color: '#A8A8C0', fontWeight: 400 }}>{item.note}</p>
              </div>
            </div>
            <span style={{ backgroundColor: `${item.tagColor}18`, color: item.tagColor, borderRadius: 100, padding: '5px 13px', fontSize: 11, fontWeight: 700, flexShrink: 0, marginLeft: 8 }}>
              {item.tag}
            </span>
          </div>
        ))}
      </div>

      {/* Thin divider */}
      <div style={{ height: 1, backgroundColor: '#EAEAF2', margin: '20px 28px' }} />

      {/* Doctor section */}
      <div style={{ padding: '0 28px 52px' }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, color: '#2D2D3A', marginBottom: 14, letterSpacing: -0.3 }}>Ask your doctor</h2>

        {/* White card */}
        <div style={{ backgroundColor: '#FFFFFF', borderRadius: 20, overflow: 'hidden', boxShadow: '0 2px 20px rgba(45,45,58,0.06)' }}>
          {tests.map((test, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '16px 22px', borderBottom: i < tests.length - 1 ? '1px solid #F3F3F8' : 'none' }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', backgroundColor: '#E87FAA', flexShrink: 0 }} />
              <span style={{ fontSize: 14, color: '#2D2D3A', fontWeight: 500 }}>{test}</span>
            </div>
          ))}
        </div>

        {/* Soft closing note */}
        <p style={{ fontSize: 13, color: '#B8B8CC', textAlign: 'center', marginTop: 24, lineHeight: 1.6, fontStyle: 'italic' }}>
          These patterns are recoverable.<br />The right care moves most people significantly.
        </p>
      </div>
    </div>
  );
}
