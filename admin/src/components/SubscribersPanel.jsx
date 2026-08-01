import { useCallback, useEffect, useMemo, useState } from 'react';
import { deleteSubscriber, listSubscribers } from '../api';

/**
 * The newsletter list, and the way addresses get from this database into a provider.
 *
 * Two things about this panel are deliberate rather than incidental:
 *
 * **Addresses are masked until you ask.** This is the only screen in the project that
 * displays personal data, and the most likely way it leaks is not a breach — it is a
 * screen share, a screenshot, or someone standing behind you. Reveal is one click and
 * applies to one row.
 *
 * **Exporting is windowed, not "everything".** Unsubscribes live with whichever provider
 * sends the email; this table never hears about them. Exporting the whole list a second
 * time would therefore re-add every person who had opted out — the one genuinely
 * unpleasant mistake available here. So the default export is "since the last time you
 * exported", and the date is remembered locally so you do not have to.
 */

const LAST_EXPORT_KEY = 'vtw.admin.lastSubscriberExport';

const readLastExport = () => {
  try {
    return window.localStorage.getItem(LAST_EXPORT_KEY) ?? '';
  } catch {
    return '';
  }
};

/** `jklee31295@gmail.com` -> `jk•••••@gmail.com`. Enough to recognise a row you are
 *  looking for, not enough to read over a shoulder or off a recording. */
function mask(email) {
  const [local, domain] = email.split('@');
  if (!domain) return '•'.repeat(email.length);
  const head = local.slice(0, 2);
  return `${head}${'•'.repeat(Math.max(3, local.length - 2))}@${domain}`;
}

const vegasDate = (iso) =>
  new Date(iso).toLocaleDateString('en-US', {
    timeZone: 'America/Los_Angeles',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

const SOURCE_LABELS = { list_end: 'End of list', saved: 'Saved screen' };

export default function SubscribersPanel() {
  const [data, setData] = useState(null);
  const [since, setSince] = useState(readLastExport);
  const [revealed, setRevealed] = useState(() => new Set());
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  // Not named `window` — that would shadow the global one this component also uses.
  const load = useCallback(async (windowStart) => {
    setBusy(true);
    try {
      setData(await listSubscribers({ since: windowStart }));
      setError(null);
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    load(since);
    // Deliberately only on mount and on an explicit Apply — typing a date should not
    // fire a request per keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const items = data?.items ?? [];

  const bySource = useMemo(() => {
    const counts = {};
    for (const item of items) counts[item.source] = (counts[item.source] ?? 0) + 1;
    return counts;
  }, [items]);

  async function copyAll() {
    // Newline-separated rather than CSV: it is what every provider's paste-a-list box
    // wants, and it survives being pasted into anything else.
    const text = items.map((item) => item.email).join('\n');
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      // Remembered so the next export defaults to the window starting today.
      try {
        window.localStorage.setItem(LAST_EXPORT_KEY, new Date().toISOString().slice(0, 10));
      } catch {
        /* storage blocked; the date box just will not prefill next time */
      }
    } catch {
      setError('Copy was blocked. Reveal the addresses and copy them by hand.');
    }
  }

  async function remove(item) {
    if (!confirm(`Remove ${item.email} from the list?`)) return;
    try {
      await deleteSubscriber(item.id);
      await load(since);
    } catch (failure) {
      setError(failure.message);
    }
  }

  return (
    <div className="panel">
      <div className="panel__head">
        <h2>Newsletter list</h2>
        {data && (
          <span className="muted">
            {data.total} {data.total === 1 ? 'address' : 'addresses'}
            {Object.keys(bySource).length > 0 &&
              ` · ${Object.entries(bySource)
                .map(([source, count]) => `${count} from ${SOURCE_LABELS[source] ?? source}`)
                .join(', ')}`}
          </span>
        )}
      </div>

      {error && <p className="error">{error}</p>}

      <div className="actions">
        <div className="field">
          <label htmlFor="subscribers-since">Signed up since</label>
          <input
            id="subscribers-since"
            type="date"
            value={since}
            onChange={(event) => {
              setSince(event.target.value);
              setCopied(false);
            }}
          />
        </div>

        <button type="button" className="btn" onClick={() => load(since)} disabled={busy}>
          {busy ? 'Loading…' : 'Apply'}
        </button>

        {since && (
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              setSince('');
              load('');
            }}
          >
            Show all
          </button>
        )}

        <button
          type="button"
          className="btn btn--primary"
          onClick={copyAll}
          disabled={items.length === 0}
        >
          {copied ? 'Copied' : `Copy ${items.length} for import`}
        </button>
      </div>

      <p className="muted stats__note">
        Copy pastes one address per line, which is what every provider&rsquo;s import box
        wants. Doing so records today&rsquo;s date, so the next export defaults to only what
        has arrived since — <strong>export the window, not the whole list</strong>, or you
        will re-add everyone who has unsubscribed with the provider.
      </p>

      {items.length === 0 ? (
        <p className="muted">
          {since
            ? 'Nobody has signed up since that date.'
            : 'No signups yet. The form is at the end of the listing and on the Saved screen.'}
        </p>
      ) : (
        <table className="stats__table">
          <thead>
            <tr>
              <th>Address</th>
              <th>Signed up from</th>
              <th>When</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>
                  {revealed.has(item.id) ? (
                    <span>{item.email}</span>
                  ) : (
                    <button
                      type="button"
                      className="btn btn--ghost btn--small"
                      onClick={() =>
                        setRevealed((current) => new Set(current).add(item.id))
                      }
                      title="Reveal this address"
                    >
                      {mask(item.email)}
                    </button>
                  )}
                </td>
                <td className="muted">{SOURCE_LABELS[item.source] ?? item.source}</td>
                <td className="muted">{vegasDate(item.created_at)}</td>
                <td>
                  <button
                    type="button"
                    className="btn btn--ghost btn--small"
                    onClick={() => remove(item)}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
