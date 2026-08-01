// Every time in this app is shown in Las Vegas time, whatever timezone the viewer is in.
// A tourist checking from New York wants "Friday 10pm" to mean 10pm in Vegas, not a
// converted 1am Saturday. The 5am rollover mirrors the backend: a night belongs to the
// day it started on.

const VEGAS_TZ = 'America/Los_Angeles';
const ROLLOVER_HOUR = 5;
const DAY_MS = 86_400_000;

const numericParts = new Intl.DateTimeFormat('en-US', {
  timeZone: VEGAS_TZ,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

const timeOnly = new Intl.DateTimeFormat('en-US', {
  timeZone: VEGAS_TZ,
  hour: 'numeric',
  minute: '2-digit',
});

const weekdayAndDate = new Intl.DateTimeFormat('en-US', {
  timeZone: VEGAS_TZ,
  weekday: 'short',
  month: 'short',
  day: 'numeric',
});

function partsOf(value) {
  const parsed = value instanceof Date ? value : new Date(value);
  const found = {};
  for (const part of numericParts.formatToParts(parsed)) {
    found[part.type] = part.value;
  }
  return {
    year: Number(found.year),
    month: Number(found.month),
    day: Number(found.day),
    hour: Number(found.hour),
    minute: Number(found.minute),
  };
}

/** The calendar day an event is filed under, as YYYY-MM-DD. */
export function listingDate(value) {
  const { year, month, day, hour } = partsOf(value);
  // Pure calendar arithmetic — UTC here is a container, not a timezone conversion.
  const stamp = Date.UTC(year, month - 1, day) - (hour < ROLLOVER_HOUR ? DAY_MS : 0);
  return new Date(stamp).toISOString().slice(0, 10);
}

function shiftDay(isoDay, days) {
  return new Date(Date.parse(`${isoDay}T00:00:00Z`) + days * DAY_MS).toISOString().slice(0, 10);
}

/** "Tonight", "Tomorrow", or "Sat, Aug 1". */
export function dayLabel(value) {
  const day = listingDate(value);
  const today = listingDate(new Date());

  if (day === today) {
    const { hour } = partsOf(value);
    return hour >= 17 || hour < ROLLOVER_HOUR ? 'Tonight' : 'Today';
  }
  if (day === shiftDay(today, 1)) return 'Tomorrow';
  return weekdayAndDate.format(new Date(value));
}

/**
 * A heading for a whole listing day: `{ lead, date }`.
 *
 * `lead` is "Today" or "Tomorrow" where one applies, and null otherwise — the header
 * covers a whole day, so the evening-only "Tonight" that `dayLabel` uses for a single
 * event would be wrong above a 2pm one. `date` is always present, because a header
 * reading only "Today" gives someone scrolling nothing to orient by.
 */
export function dayHeading(isoDay) {
  const today = listingDate(new Date());
  // Noon UTC is 5am in Vegas — the same calendar day under either zone, which parsing
  // the bare date string is not: that is UTC midnight, and formats as the day before.
  const date = weekdayAndDate.format(new Date(`${isoDay}T12:00:00Z`));

  if (isoDay === today) return { lead: 'Today', date };
  if (isoDay === shiftDay(today, 1)) return { lead: 'Tomorrow', date };
  return { lead: null, date };
}

/**
 * Events in listing-day buckets, order preserved: `[{ day, events }]`.
 *
 * Relies on the server returning them chronologically, which is why the listing endpoint
 * promotes nothing out of time order — a promoted row would land in the wrong bucket, or
 * open a second bucket for a day that already had one.
 */
export function groupByDay(events) {
  const groups = [];
  for (const event of events) {
    const day = listingDate(event.start_at);
    const last = groups[groups.length - 1];
    if (last && last.day === day) last.events.push(event);
    else groups.push({ day, events: [event] });
  }
  return groups;
}

/** "9:00 PM" */
export const timeLabel = (value) => timeOnly.format(new Date(value));

/** "Tonight · 9:00 PM" */
export const whenLabel = (value) => `${dayLabel(value)} · ${timeLabel(value)}`;

/** "9:00 PM – 2:00 AM" */
export const rangeLabel = (start, end) => `${timeLabel(start)} – ${timeLabel(end)}`;

/** "Sat, Aug 1" — the full date, for the detail sheet where there is room. */
export const fullDateLabel = (value) => weekdayAndDate.format(new Date(value));

export const hasFinished = (endsAt) => new Date(endsAt).getTime() < Date.now();

export function expiresInDays(isoTimestamp) {
  const remaining = new Date(isoTimestamp).getTime() - Date.now();
  return Math.max(0, Math.ceil(remaining / DAY_MS));
}
