import { useEffect, useRef, useState } from 'react'

export const money = (n: number, cents = false) =>
  n.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: cents ? 2 : 0,
  })

export const longDate = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })

export const clock = (iso: string) =>
  new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', second: '2-digit' })

export const TICKET_TYPES: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price override',
}

export const BOSS_STATUS: Record<string, string> = {
  open: 'Open',
  in_progress: 'In progress',
  waiting_on_approval: 'Waiting on approval',
  blocked: 'Blocked',
  resolved: 'Resolved',
}

export const KIND_LABEL: Record<string, string> = {
  invoice: 'Vendor invoice',
  rent: 'Rent payment',
  purchase_order: 'Purchase order',
}

/** Tween a number toward its target with an ease-out curve. */
export function useAnimatedNumber(target: number, duration = 1100) {
  const [value, setValue] = useState(target)
  const from = useRef(target)
  useEffect(() => {
    const start = performance.now()
    const begin = from.current
    let frame = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 4)
      setValue(begin + (target - begin) * eased)
      if (t < 1) frame = requestAnimationFrame(tick)
      else from.current = target
    }
    frame = requestAnimationFrame(tick)
    // Browsers pause animation frames in background tabs; never leave a stale number on screen.
    const settle = setTimeout(() => { cancelAnimationFrame(frame); setValue(target); from.current = target }, duration + 150)
    return () => {
      cancelAnimationFrame(frame)
      clearTimeout(settle)
      from.current = target
    }
  }, [target, duration])
  return value
}

/** Run `fn` now and then every `ms`, skipping overlapping calls. */
export function usePolling(fn: () => Promise<void>, ms: number, deps: unknown[] = []) {
  const busy = useRef(false)
  useEffect(() => {
    let alive = true
    const run = async () => {
      if (busy.current || !alive) return
      busy.current = true
      try { await fn() } finally { busy.current = false }
    }
    run()
    const id = setInterval(run, ms)
    return () => { alive = false; clearInterval(id) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ms, ...deps])
}
