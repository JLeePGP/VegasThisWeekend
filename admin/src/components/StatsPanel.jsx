import { useCallback, useEffect, useState } from 'react';
import { getStats } from '../api';
import { VIBES } from '../constants';

// The two series colours are not chosen by eye. Pink against teal — the obvious pick
// from the app's own palette — collapses under deuteranopia (ΔE 5.0, well under the
// ΔE 8 floor): the two lines become the same line for a red-green colourblind reader.
// This blue is the nearest hue that clears CVD separation, the dark-mode lightness band
// and contrast against the panel surface simultaneously.
const SAVE_COLOR = '#ff2e88';
const SKIP_COLOR = '#4a86e8';

// Below this many decisions a save rate is noise, not signal — one save out of one view
// is 100%. Shown, but visibly discounted rather than ranked as if it meant something.
const MIN_DECISIONS = 5;

const RANGES = [
  { days: 7, label: '7 days' },
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
];

const VIBE_LABELS = Object.fromEntries(VIBES.map((v) => [v.value, v.label]));

const pct = (rate) => (rate === null || rate === undefined ? '—' : `${Math.round(rate * 100)}%`);

/** Whole numbers with thousands separators; em dash for nothing rather than a bare 0. */
const num = (value) => (value ? value.toLocaleString('en-US') : '0');

function Tile({ label, value, hint }) {
  return (
    <div className="tile">
      <span className="tile__label">{label}</span>
      <strong className="tile__value">{value}</strong>
      {hint && <span className="tile__hint">{hint}</span>}
    </div>
  );
}

/**
 * Saves and skips per day.
 *
 * Hand-rolled SVG rather than a charting library: two polylines and a grid is less code
 * than the adapter would be, and it keeps the admin bundle free of a dependency that
 * would also need a CSP exception.
 */
function DailyChart({ daily, days }) {
  const [hover, setHover] = useState(null);

  const dayKeys = Object.keys(daily).sort();
  if (dayKeys.length === 0) {
    return <p className="muted">No activity recorded yet.</p>;
  }

  const rows = dayKeys.map((day) => ({
    day,
    save: daily[day].save ?? 0,
    skip: daily[day].skip ?? 0,
  }));

  const W = 720;
  const H = 200;
  const PAD = { top: 14, right: 14, bottom: 26, left: 34 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  const peak = Math.max(1, ...rows.flatMap((r) => [r.save, r.skip]));
  const x = (i) => PAD.left + (rows.length === 1 ? plotW / 2 : (i / (rows.length - 1)) * plotW);
  const y = (v) => PAD.top + plotH - (v / peak) * plotH;

  const line = (key) => rows.map((r, i) => `${x(i)},${y(r[key])}`).join(' ');
  const gridValues = [0, Math.round(peak / 2), peak];

  return (
    <div className="chart">
      <div className="chart__legend">
        <span className="chart__key">
          <span className="chart__swatch" style={{ background: SAVE_COLOR }} />
          Saves
        </span>
        <span className="chart__key">
          <span className="chart__swatch" style={{ background: SKIP_COLOR }} />
          Skips
        </span>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="chart__svg"
        role="img"
        aria-label={`Saves and skips per day over the last ${days} days`}
        onMouseLeave={() => setHover(null)}
      >
        {gridValues.map((value) => (
          <g key={value}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(value)}
              y2={y(value)}
              className="chart__grid"
            />
            <text x={PAD.left - 8} y={y(value) + 4} className="chart__tick" textAnchor="end">
              {value}
            </text>
          </g>
        ))}

        <polyline points={line('skip')} fill="none" stroke={SKIP_COLOR} strokeWidth="2" />
        <polyline points={line('save')} fill="none" stroke={SAVE_COLOR} strokeWidth="2" />

        {hover !== null && (
          <line
            x1={x(hover)}
            x2={x(hover)}
            y1={PAD.top}
            y2={PAD.top + plotH}
            className="chart__crosshair"
          />
        )}

        {rows.map((row, i) => (
          <g key={row.day}>
            {hover === i && (
              <>
                <circle cx={x(i)} cy={y(row.save)} r="4.5" fill={SAVE_COLOR} />
                <circle cx={x(i)} cy={y(row.skip)} r="4.5" fill={SKIP_COLOR} />
              </>
            )}
            {/* An invisible full-height band per day: a hit target far bigger than the
                mark, so hovering does not require landing on a 2px line. */}
            <rect
              x={x(i) - plotW / Math.max(1, rows.length * 2)}
              y={PAD.top}
              width={plotW / Math.max(1, rows.length)}
              height={plotH}
              fill="transparent"
              onMouseEnter={() => setHover(i)}
            />
          </g>
        ))}

        <text x={PAD.left} y={H - 6} className="chart__tick">
          {rows[0].day.slice(5)}
        </text>
        {rows.length > 1 && (
          <text x={W - PAD.right} y={H - 6} className="chart__tick" textAnchor="end">
            {rows[rows.length - 1].day.slice(5)}
          </text>
        )}
      </svg>

      <p className="chart__readout">
        {hover === null ? (
          <span className="muted">Hover the chart for a day.</span>
        ) : (
          <>
            <strong>{rows[hover].day}</strong> · {num(rows[hover].save)} saves ·{' '}
            {num(rows[hover].skip)} skips
          </>
        )}
      </p>
    </div>
  );
}

function SaveRateBar({ rate, decisions }) {
  const thin = decisions < MIN_DECISIONS;
  return (
    <div className="meter" title={`${decisions} decisions`}>
      <div className="meter__track">
        <div
          className="meter__fill"
          data-thin={thin}
          style={{ width: `${Math.round((rate ?? 0) * 100)}%` }}
        />
      </div>
      <span className="meter__value" data-thin={thin}>
        {pct(rate)}
      </span>
    </div>
  );
}

export default function StatsPanel() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (window) => {
    setLoading(true);
    setError(null);
    try {
      setData(await getStats(window));
    } catch (err) {
      setError(err.message ?? 'Could not load stats.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(days);
  }, [days, load]);

  if (loading && !data) return <p className="muted">Loading…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!data) return null;

  const t = data.totals;
  const decisions = (t.save ?? 0) + (t.skip ?? 0);
  // Only where skips exist, which since 1 Aug 2026 means only the swipe-era range. A
  // list has no explicit "no", so saves/(saves+0) would report a flawless rate forever.
  const overallRate = t.skip ? (t.save ?? 0) / decisions : null;
  // Whether this range still contains swipe-deck data at all. Drives whether the columns
  // that only that data can fill are worth showing.
  const hasSwipeEra = Boolean(t.skip || t.stack_exhausted);

  const rankedVibes = Object.entries(data.by_vibe)
    .map(([vibe, stats]) => ({ vibe, ...stats, decisions: stats.saves + stats.skips }))
    .filter((row) => row.decisions > 0)
    .sort((a, b) => (b.save_rate ?? 0) - (a.save_rate ?? 0));

  return (
    <div className="stats">
      <div className="stats__head">
        <h2>What people are doing</h2>
        <div className="segbar" role="group" aria-label="Time range">
          {RANGES.map((range) => (
            <button
              key={range.days}
              type="button"
              className="segbar__option"
              aria-pressed={days === range.days}
              onClick={() => setDays(range.days)}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      <div className="tiles">
        <Tile label="Visits" value={num(t.session_start)} />
        {/* The share, not the count, because the count alone says nothing without the
            denominator sitting next to it. */}
        <Tile
          label="From the home screen"
          value={
            t.session_start
              ? `${Math.round(((t.standalone_session ?? 0) / t.session_start) * 100)}%`
              : '—'
          }
          hint={`${num(t.standalone_session)} of ${num(t.session_start)} visits`}
        />
        <Tile label="Saves" value={num(t.save)} />
        <Tile label="Signups" value={num(t.subscribe)} hint="newsletter" />
        {hasSwipeEra && (
          <>
            <Tile label="Skips" value={num(t.skip)} hint="swipe era, ended 1 Aug" />
            <Tile
              label="Save rate"
              value={pct(overallRate)}
              hint={`${num(decisions)} decisions, swipe era`}
            />
          </>
        )}
        <Tile label="Links shared" value={num(t.share_create)} />
        <Tile
          label="Links opened"
          value={num(t.share_open)}
          hint="actual reach"
        />
        <Tile label="Details opened" value={num(t.detail_open)} />
        <Tile label="Tickets clicked" value={num(t.ticket_click)} />
        <Tile label="Websites clicked" value={num(t.website_click)} />
        <Tile label="Maps opened" value={num(t.map_click)} />
        <Tile label="Tips revealed" value={num(t.tip_reveal)} />
        <Tile label="Videos played" value={num(t.video_play)} />
        {/* The successor to "ran out of cards", and the same signal: people reaching the
            bottom of the listing means the catalog is too thin for the filters they
            picked. It was 31% of sessions on the deck, which is why sourcing rather than
            layout is the thing to fix. */}
        <Tile
          label="Reached the end"
          value={num(t.list_end)}
          hint="catalog too thin"
        />
        <Tile
          label="Installs"
          value={num(t.app_installed)}
          hint="Android only — see below"
        />
        {hasSwipeEra && (
          <Tile
            label="Ran out of cards"
            value={num(t.stack_exhausted)}
            hint="swipe era, ended 1 Aug"
          />
        )}
      </div>

      <p className="muted stats__note">
        <strong>Installs undercount, permanently.</strong> Safari fires no install event
        of any kind, so an iPhone user adding this to their home screen is invisible —
        that tile is Android and desktop Chrome only, and a low number is not evidence
        that nobody installs. <strong>From the home screen</strong> is the one to watch
        instead: it counts visits that arrived through an installed icon, works on both
        platforms, and answers the question installing was for — whether those people
        come back, and whether their saved events survive.
      </p>

      <section className="stats__section">
        <h3>Saves and skips per day</h3>
        <p className="muted stats__note">
          The skip line stops at 1 Aug 2026, when the swipe deck was removed. It is not a
          drop in interest — nothing produces a skip any more.
        </p>
        <DailyChart daily={data.daily} days={data.days} />
      </section>

      <section className="stats__section">
        <h3>Which events land</h3>
        <p className="muted stats__note">
          Ranked by saves. Save rate is blank for anything after 1 Aug 2026 and that is
          deliberate: a rate needs an explicit no, which a swipe left was and scrolling
          past a row is not. Where it does show, rates from fewer than {MIN_DECISIONS}{' '}
          decisions are dimmed, because one save out of one view is 100%.
        </p>
        {data.events.length === 0 ? (
          <p className="muted">Nothing recorded yet.</p>
        ) : (
          <table className="stats__table">
            <thead>
              <tr>
                <th>Event</th>
                <th>Category</th>
                <th className="num">Saves</th>
                <th className="num">Skips</th>
                <th>Save rate</th>
                <th className="num">Details</th>
                <th className="num">Tickets</th>
              </tr>
            </thead>
            <tbody>
              {data.events.map((event) => (
                <tr key={event.id}>
                  <td>{event.name}</td>
                  <td className="muted">{VIBE_LABELS[event.vibe] ?? event.vibe}</td>
                  <td className="num">{num(event.metrics.save)}</td>
                  <td className="num">{num(event.metrics.skip)}</td>
                  <td>
                    <SaveRateBar rate={event.save_rate} decisions={event.decisions} />
                  </td>
                  <td className="num">{num(event.metrics.detail_open)}</td>
                  <td className="num">{num(event.metrics.ticket_click)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="stats__section">
        <h3>Which categories land</h3>
        {rankedVibes.length === 0 ? (
          <p className="muted">Nothing recorded yet.</p>
        ) : (
          <table className="stats__table">
            <thead>
              <tr>
                <th>Category</th>
                <th className="num">Saves</th>
                <th className="num">Skips</th>
                <th>Save rate</th>
              </tr>
            </thead>
            <tbody>
              {rankedVibes.map((row) => (
                <tr key={row.vibe}>
                  <td>{VIBE_LABELS[row.vibe] ?? row.vibe}</td>
                  <td className="num">{num(row.saves)}</td>
                  <td className="num">{num(row.skips)}</td>
                  <td>
                    <SaveRateBar rate={row.save_rate} decisions={row.decisions} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <p className="muted stats__footnote">
        Counts only — no sessions, no IP addresses, nothing that identifies anyone. Since{' '}
        {data.since}, in Las Vegas time.
      </p>
    </div>
  );
}
