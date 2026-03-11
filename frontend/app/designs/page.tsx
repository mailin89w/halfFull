export default function DesignsIndex() {
  return (
    <div style={{ backgroundColor: '#F5F5F5', minHeight: '100vh', fontFamily: 'system-ui, sans-serif', padding: '48px 24px' }}>
      <p style={{ fontSize: 12, fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', color: '#999', marginBottom: 8 }}>Design Explorations</p>
      <h1 style={{ fontSize: 28, fontWeight: 800, color: '#1A1A1A', marginBottom: 8, letterSpacing: -0.5 }}>Results Page — 3 Concepts</h1>
      <p style={{ fontSize: 14, color: '#888', marginBottom: 40 }}>Static mockups. Existing app is untouched.</p>
      {[
        { href: '/designs/v1', label: 'V1 — Bold Yellow', desc: 'High contrast · energetic · strong typography' },
        { href: '/designs/v2', label: 'V2 — Lavender Editorial', desc: 'Oversized type · data-forward · playful' },
        { href: '/designs/v3', label: 'V3 — White & Pink', desc: 'Airy · glowing · wellness-calm' },
      ].map((d) => (
        <a key={d.href} href={d.href} style={{ display: 'block', backgroundColor: '#FFFFFF', borderRadius: 16, padding: '20px 24px', marginBottom: 12, textDecoration: 'none', boxShadow: '0 2px 12px rgba(0,0,0,0.06)' }}>
          <p style={{ fontSize: 16, fontWeight: 700, color: '#1A1A1A', marginBottom: 4 }}>{d.label}</p>
          <p style={{ fontSize: 13, color: '#999' }}>{d.desc}</p>
        </a>
      ))}
    </div>
  );
}
