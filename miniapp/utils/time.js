// Slots: 0–31 map to 08:00–24:00 in 30-min steps
const SLOT_START_HOUR = 8
const TOTAL_SLOTS = 32

function slotToTime(slot) {
  const totalMinutes = SLOT_START_HOUR * 60 + slot * 30
  const h = Math.floor(totalMinutes / 60)
  const m = totalMinutes % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

function timeToSlot(timeStr) {
  const [h, m] = timeStr.split(':').map(Number)
  return (h * 60 + m - SLOT_START_HOUR * 60) / 30
}

// Convert ISO datetime string to slot index (ignores date part)
function datetimeToSlot(isoStr) {
  const d = new Date(isoStr)
  const h = d.getHours()
  const m = d.getMinutes()
  return (h * 60 + m - SLOT_START_HOUR * 60) / 30
}

// Build a Set of taken slot indices from slots_taken array
function buildTakenSlots(slotsTaken) {
  const taken = new Set()
  for (const s of slotsTaken) {
    const from = datetimeToSlot(s.start_at)
    const to = datetimeToSlot(s.end_at)
    for (let i = from; i < to; i++) taken.add(i)
  }
  return taken
}

// Format date as YYYY-MM-DD
function formatDate(date) {
  const d = date instanceof Date ? date : new Date(date)
  return d.toISOString().slice(0, 10)
}

// Today as YYYY-MM-DD
function today() {
  return formatDate(new Date())
}

module.exports = { slotToTime, timeToSlot, datetimeToSlot, buildTakenSlots, formatDate, today, TOTAL_SLOTS }
