export default function DesignsIndex() {
  const sections = [
    {
      title: 'Start Page',
      designs: [
        { href: '/designs/start-v1', label: 'Start V1 — Bold Periwinkle', desc: 'Old brand style · lavender bg · overlapping orbs · heavy type' },
        { href: '/designs/start-v2', label: 'Start V2 — Midnight Ink', desc: 'Dark editorial · electric violet · large numbered steps' },
        { href: '/designs/start-v3', label: 'Start V3 — Warm Paper', desc: 'Cream bg · deep purple · marker highlight steps · amber accents' },
      ],
    },
    {
      title: 'Results Page',
      designs: [
        { href: '/designs/v1', label: 'Results V1 — Bold Yellow', desc: 'High contrast · energetic · strong typography' },
        { href: '/designs/v2', label: 'Results V2 — Lavender Editorial', desc: 'Oversized type · data-forward · playful' },
        { href: '/designs/v3', label: 'Results V3 — White & Pink', desc: 'Airy · glowing · wellness-calm' },
      ],
    },
  ];

  return (
    <div style={{ backgroundColor: '#F5F5F5', minHeight: '100vh', fontFamily: 'system-ui, sans-serif', padding: '48px 24px' }}>
      <p style={{ fontSize: 12, fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', color: '#999', marginBottom: 8 }}>Design Explorations</p>
      <h1 style={{ fontSize: 28, fontWeight: 800, color: '#1A1A1A', marginBottom: 40, letterSpacing: -0.5 }}>Static Prototypes</h1>
      {sections.map((section) => (
        <div key={section.title} style={{ marginBottom: 40 }}>
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', color: '#BBB', marginBottom: 14 }}>{section.title}</p>
          {section.designs.map((d) => (
            <a key={d.href} href={d.href} style={{ display: 'block', backgroundColor: '#FFFFFF', borderRadius: 16, padding: '20px 24px', marginBottom: 10, textDecoration: 'none', boxShadow: '0 2px 12px rgba(0,0,0,0.06)' }}>
              <p style={{ fontSize: 16, fontWeight: 700, color: '#1A1A1A', marginBottom: 4 }}>{d.label}</p>
              <p style={{ fontSize: 13, color: '#999' }}>{d.desc}</p>
            </a>
          ))}
        </div>
      ))}
    </div>
  );
}
