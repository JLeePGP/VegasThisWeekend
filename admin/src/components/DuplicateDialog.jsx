/**
 * Shown when a save collides with something already in the catalog.
 *
 * This warns rather than blocks: two genuinely different events can share a venue and
 * a start time (two rooms, two stages), so the decision stays with John.
 */
export default function DuplicateDialog({ collisions, onCancel, onSaveAnyway, saving }) {
  const total = collisions.reduce((sum, item) => sum + item.existing.length, 0);

  return (
    <div className="dialog-backdrop" role="dialog" aria-modal="true" aria-labelledby="dupe-title">
      <div className="dialog">
        <h2 id="dupe-title">This looks like it is already in the catalog</h2>
        <p>
          {total} existing {total === 1 ? 'event' : 'events'} matched on venue or name at a
          similar time. Save anyway if these are genuinely different.
        </p>

        {collisions.map((collision) => (
          <div key={collision.attempted_start_local} style={{ marginBottom: 14 }}>
            <div className="field__note" style={{ marginLeft: 0, marginBottom: 6 }}>
              Trying to add: <span className="mono">{collision.attempted_start_local}</span>
            </div>
            <div className="rows">
              {collision.existing.map((event) => (
                <div className="row" key={event.id}>
                  <span className="row__when">{event.starts_at_local.replace('T', ' ')}</span>
                  <div className="row__main">
                    <div className="row__title">{event.name}</div>
                    <div className="row__sub">
                      {event.venue} · {event.vibe}
                      {event.is_active ? '' : ' · inactive'}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}

        <div className="actions">
          <button type="button" className="btn btn--secondary" onClick={onCancel} disabled={saving}>
            Cancel
          </button>
          <button type="button" className="btn btn--danger" onClick={onSaveAnyway} disabled={saving}>
            {saving ? 'Saving…' : 'Save anyway'}
          </button>
        </div>
      </div>
    </div>
  );
}
