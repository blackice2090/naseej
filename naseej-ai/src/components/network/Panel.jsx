// Shared section shell for the Network Intelligence dashboard — subtle border,
// controlled glass background, consistent header. Keeps every section visually
// aligned with the existing Naseej panels without repeating markup.
export default function Panel({ title, titleAr, icon: Icon, right, children, className = '' }) {
  return (
    <section
      className={`rounded-lg p-4 flex flex-col ${className}`}
      style={{
        background: 'rgba(10,15,30,0.6)',
        border: '1px solid rgba(255,255,255,0.06)',
        backdropFilter: 'blur(8px)',
      }}
    >
      {title && (
        <div className="flex items-center justify-between mb-3 shrink-0">
          <div className="flex items-center gap-2">
            {Icon && <Icon size={13} style={{ color: '#4fc3f7' }} />}
            <h2 className="text-[11px] font-bold tracking-[2px]" style={{ color: '#4fc3f7' }}>{title}</h2>
            {titleAr && (
              <span className="text-[11px] leading-relaxed" style={{ color: '#7c4dff', fontFamily: 'var(--font-arabic)' }} dir="rtl">{titleAr}</span>
            )}
          </div>
          {right}
        </div>
      )}
      {children}
    </section>
  )
}
