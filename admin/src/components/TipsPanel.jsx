import { useEffect, useState } from 'react';
import { createTip, deleteTip, listTips, updateTip } from '../api';
import { VIBES } from '../constants';

const BLANK = { venue: '', vibe: '', tip: '', priority: 0, is_active: true };

/**
 * Insider tips live in the database precisely so adding one never needs a redeploy.
 * A tip matches an event by venue, by category, or by both — venue wins when several
 * could apply.
 */
export default function TipsPanel() {
  const [tips, setTips] = useState([]);
  const [draft, setDraft] = useState(BLANK);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setTips(await listTips());
      setError(null);
    } catch (failure) {
      setError(failure.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const payload = {
        venue: draft.venue.trim() || null,
        vibe: draft.vibe || null,
        tip: draft.tip.trim(),
        priority: Number(draft.priority) || 0,
        is_active: draft.is_active,
      };
      if (editingId) await updateTip(editingId, payload);
      else await createTip(payload);
      setDraft(BLANK);
      setEditingId(null);
      await load();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(tip) {
    if (!window.confirm('Delete this tip?')) return;
    try {
      await deleteTip(tip.id);
      await load();
    } catch (failure) {
      setError(failure.message);
    }
  }

  function edit(tip) {
    setEditingId(tip.id);
    setDraft({
      venue: tip.venue ?? '',
      vibe: tip.vibe ?? '',
      tip: tip.tip,
      priority: tip.priority,
      is_active: tip.is_active,
    });
  }

  return (
    <>
      <form className="panel" onSubmit={save}>
        <div className="panel__head">
          <h2>{editingId ? 'Edit tip' : 'Add a tip'}</h2>
          <p>Shown on the expanded card when the venue or category matches.</p>
        </div>

        {error && (
          <div className="banner" data-tone="error">
            {error}
          </div>
        )}

        <div className="grid grid--three">
          <div className="field">
            <label htmlFor="tip-venue">Venue (optional)</label>
            <input
              id="tip-venue"
              type="text"
              value={draft.venue}
              onChange={(event) => setDraft({ ...draft, venue: event.target.value })}
              placeholder="Neon Cathedral"
            />
          </div>
          <div className="field">
            <label htmlFor="tip-vibe">Category (optional)</label>
            <select
              id="tip-vibe"
              value={draft.vibe}
              onChange={(event) => setDraft({ ...draft, vibe: event.target.value })}
            >
              <option value="">— any —</option>
              {VIBES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="tip-priority">Priority</label>
            <input
              id="tip-priority"
              type="number"
              min="0"
              max="100"
              value={draft.priority}
              onChange={(event) => setDraft({ ...draft, priority: event.target.value })}
            />
          </div>
        </div>

        <div className="field" style={{ marginTop: 14 }}>
          <label htmlFor="tip-text">The tip</label>
          <textarea
            id="tip-text"
            rows={3}
            value={draft.tip}
            onChange={(event) => setDraft({ ...draft, tip: event.target.value })}
            placeholder="Guest lists close far earlier than doors do…"
          />
        </div>

        <div className="actions">
          <button type="submit" className="btn btn--primary" disabled={busy || !draft.tip.trim()}>
            {editingId ? 'Save changes' : 'Add tip'}
          </button>
          {editingId && (
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => {
                setEditingId(null);
                setDraft(BLANK);
              }}
            >
              Cancel
            </button>
          )}
          <span className="field__note" style={{ marginLeft: 0 }}>
            A tip needs a venue, a category, or both — otherwise it matches nothing.
          </span>
        </div>
      </form>

      <div className="panel">
        <div className="panel__head">
          <h2>All tips</h2>
          <p>{tips.length} total</p>
        </div>

        {tips.length === 0 ? (
          <div className="empty">No tips yet.</div>
        ) : (
          <div className="rows">
            {tips.map((tip) => (
              <div className="row" key={tip.id} data-inactive={!tip.is_active}>
                <span className="row__when" style={{ flexBasis: 190 }}>
                  {tip.venue || '—'} / {tip.vibe || 'any'}
                </span>
                <div className="row__main">
                  <div className="row__sub" style={{ whiteSpace: 'normal', color: 'var(--text-mid)' }}>
                    {tip.tip}
                  </div>
                </div>
                <span className="row__tag">p{tip.priority}</span>
                <div className="row__buttons">
                  <button type="button" className="btn btn--ghost btn--small" onClick={() => edit(tip)}>
                    Edit
                  </button>
                  <button type="button" className="btn btn--danger btn--small" onClick={() => remove(tip)}>
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
