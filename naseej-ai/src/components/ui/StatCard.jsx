export default function StatCard({ value, label, accent = '#4fc3f7' }) {
  return (
    <div
      className="rounded p-3 text-center"
      style={{
        background: 'rgba(10,15,30,0.6)',
        border: '1px solid rgba(255,255,255,0.06)',
        backdropFilter: 'blur(8px)',
      }}
    >
      <div className="text-xl font-bold font-mono" style={{ color: accent }}>{value}</div>
      <div className="text-[10px] tracking-widest mt-0.5" style={{ color: '#5a6a8a' }}>{label}</div>
    </div>
  )
}
