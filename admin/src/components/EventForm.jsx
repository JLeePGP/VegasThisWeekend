import { HOOK_MAX, NEIGHBORHOODS, PRICE_TIERS, VIBES, WEEKDAYS } from '../constants';

/**
 * The single event form. Extraction pre-fills it; manual entry starts it empty —
 * deliberately one form and one validation path, so a failed extraction degrades into
 * typing rather than a dead end.
 *
 * Every time field is a `datetime-local` input, whose value format is exactly the
 * naive Vegas wall clock the API expects. No conversion happens in this browser.
 */
export default function EventForm({
  value,
  onChange,
  uncertain = new Set(),
  recurrence,
  onRecurrenceChange,
  allowRecurrence = true,
}) {
  const set = (field) => (event) => {
    const target = event.target;
    onChange({ ...value, [field]: target.type === 'checkbox' ? target.checked : target.value });
  };

  const field = (name, label, control, { span = false } = {}) => (
    <div className={`field${span ? ' span-2' : ''}`} data-uncertain={uncertain.has(name)}>
      <label htmlFor={`f-${name}`}>
        {label}
        {uncertain.has(name) && <span className="field__note">guessed — check</span>}
      </label>
      {control}
    </div>
  );

  const text = (name, extra = {}) => (
    <input id={`f-${name}`} type="text" value={value[name] ?? ''} onChange={set(name)} {...extra} />
  );

  const toggleWeekday = (day) => {
    const next = recurrence.weekdays.includes(day)
      ? recurrence.weekdays.filter((item) => item !== day)
      : [...recurrence.weekdays, day];
    onRecurrenceChange({ ...recurrence, weekdays: next });
  };

  const hookLength = (value.hook ?? '').length;

  return (
    <>
      <div className="grid">
        {field('name', 'Event name', text('name', { placeholder: 'Midnight Mass' }), { span: true })}

        {field('venue', 'Venue', text('venue', { placeholder: 'Neon Cathedral' }))}
        {field(
          'neighborhood',
          'Neighborhood',
          <select id="f-neighborhood" value={value.neighborhood} onChange={set('neighborhood')}>
            {/* An event edited straight in the database may carry a label outside the
                list; keep it selectable rather than silently blanking the field. */}
            {!NEIGHBORHOODS.includes(value.neighborhood) && value.neighborhood && (
              <option value={value.neighborhood}>{value.neighborhood}</option>
            )}
            {NEIGHBORHOODS.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>,
        )}

        {field(
          'address',
          'Street address',
          text('address', { placeholder: '1023 Fremont St, Las Vegas, NV 89101' }),
          { span: true },
        )}

        {field(
          'starts_at_local',
          'Starts (Vegas time)',
          <input
            id="f-starts_at_local"
            type="datetime-local"
            value={value.starts_at_local}
            onChange={set('starts_at_local')}
          />,
        )}
        {field(
          'ends_at_local',
          'Ends (Vegas time)',
          <input
            id="f-ends_at_local"
            type="datetime-local"
            value={value.ends_at_local}
            onChange={set('ends_at_local')}
          />,
        )}
      </div>

      <div className="grid grid--three" style={{ marginTop: 14 }}>
        {field(
          'vibe',
          'Category',
          <select id="f-vibe" value={value.vibe} onChange={set('vibe')}>
            {VIBES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>,
        )}
        {field(
          'price_tier',
          'Price tier',
          <select id="f-price_tier" value={value.price_tier} onChange={set('price_tier')}>
            {PRICE_TIERS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>,
        )}
        {field('price_note', 'Price detail', text('price_note', { placeholder: '$25 advance / $35 door' }))}
      </div>

      <div className="grid" style={{ marginTop: 14 }}>
        <div className="field span-2">
          <label>
            Also counts as
            <span className="field__note">optional — the primary category is already applied</span>
          </label>
          <div className="tagpick">
            {VIBES.filter((option) => option.value !== value.vibe).map((option) => {
              const on = (value.tags ?? []).includes(option.value);
              return (
                <button
                  key={option.value}
                  type="button"
                  className="tagpick__chip"
                  aria-pressed={on}
                  onClick={() =>
                    onChange({
                      ...value,
                      tags: on
                        ? value.tags.filter((tag) => tag !== option.value)
                        : [...(value.tags ?? []), option.value],
                    })
                  }
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="field span-2">
          <label className="checkline" htmlFor="f-alcohol_free">
            <input
              id="f-alcohol_free"
              type="checkbox"
              checked={Boolean(value.alcohol_free)}
              onChange={set('alcohol_free')}
            />
            <span>
              <strong>Alcohol-free</strong>
              {/* Worth being blunt in the UI: this is the one field where guessing
                  optimistically sends someone in recovery to a bar. */}
              <span className="checkline__hint">
                Only tick this if the source actually says so — dry, sober, no bar. Not
                mentioning alcohol is not the same as being alcohol-free.
              </span>
            </span>
          </label>
        </div>
      </div>

      <div className="grid" style={{ marginTop: 14 }}>
        <div className="field span-2" data-uncertain={uncertain.has('hook')}>
          <label htmlFor="f-hook">
            Hook — the one line on the card
            <span className="field__note" data-over={hookLength > HOOK_MAX}>
              {hookLength}/{HOOK_MAX}
            </span>
          </label>
          <input
            id="f-hook"
            type="text"
            value={value.hook}
            onChange={set('hook')}
            placeholder="Forty local vendors, zero tourists, one very good tamale cart"
          />
        </div>

        {field(
          'description',
          'Description',
          <textarea id="f-description" value={value.description} onChange={set('description')} rows={4} />,
          { span: true },
        )}

        {field('ticket_url', 'Ticket URL', text('ticket_url', { type: 'url', placeholder: 'https://' }))}
        {field('image_url', 'Image URL', text('image_url', { type: 'url', placeholder: 'https://' }))}
        {field('source_url', 'Source URL', text('source_url', { type: 'url', placeholder: 'https://' }))}
        {field('video_url', 'Video URL', text('video_url', { type: 'url', placeholder: 'https://' }))}
      </div>

      <div className="grid" style={{ marginTop: 16 }}>
        <label className="checkbox">
          <input type="checkbox" checked={value.is_active} onChange={set('is_active')} />
          <span>
            Live
            <small>Uncheck to save it without showing it in the app yet.</small>
          </span>
        </label>
        <label className="checkbox">
          <input type="checkbox" checked={value.mirror_image} onChange={set('mirror_image')} />
          <span>
            Copy image to R2
            <small>Venue URLs break; a mirrored copy does not.</small>
          </span>
        </label>
      </div>

      {allowRecurrence && (
        <div className="panel" style={{ marginTop: 18, background: 'var(--ink-850)' }}>
          <div className="panel__head">
            <h2>Repeats</h2>
            <p>Residencies and weekly nights become one event per night.</p>
          </div>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={recurrence.enabled}
              onChange={(event) => onRecurrenceChange({ ...recurrence, enabled: event.target.checked })}
            />
            <span>This event runs on a repeating schedule</span>
          </label>

          {recurrence.enabled && (
            <div style={{ marginTop: 14 }}>
              <div className="field">
                <label>Nights it runs</label>
                <div className="chip-row">
                  {WEEKDAYS.map((day) => (
                    <button
                      key={day.value}
                      type="button"
                      className="chip"
                      aria-pressed={recurrence.weekdays.includes(day.value)}
                      onClick={() => toggleWeekday(day.value)}
                    >
                      {day.short}
                    </button>
                  ))}
                </div>
                <span className="field__note" style={{ marginLeft: 0 }}>
                  Leave empty to repeat on the same weekday as the start date.
                </span>
              </div>

              <div className="field" style={{ marginTop: 12, maxWidth: 220 }}>
                <label htmlFor="f-until">Last date</label>
                <input
                  id="f-until"
                  type="date"
                  value={recurrence.until ?? ''}
                  onChange={(event) => onRecurrenceChange({ ...recurrence, until: event.target.value })}
                />
                <span className="field__note" style={{ marginLeft: 0 }}>
                  Blank generates 26 occurrences, then stops.
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
