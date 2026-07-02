import { useState, useEffect } from 'react'

// Eased count-up for metric values.
export default function CountUp({ to, duration = 1500, format }) {
  const [value, setValue] = useState(0)

  useEffect(() => {
    let start = null
    let rafId = null
    const numTo = parseFloat(String(to).replace(/[^0-9.]/g, ''))
    const raf = (ts) => {
      if (!start) start = ts
      const progress = Math.min((ts - start) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setValue(numTo * eased)
      if (progress < 1) rafId = requestAnimationFrame(raf)
      else setValue(numTo)
    }
    rafId = requestAnimationFrame(raf)
    return () => cancelAnimationFrame(rafId)
  }, [to, duration])

  return <>{format ? format(value) : value.toFixed(0)}</>
}
