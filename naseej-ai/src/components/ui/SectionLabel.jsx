// Consistent uppercase section label used across panels.
export default function SectionLabel({ children, color = '#5a6a8a' }) {
  return (
    <div className="text-[10px] tracking-widest mb-1.5 font-semibold" style={{ color }}>
      {children}
    </div>
  )
}
