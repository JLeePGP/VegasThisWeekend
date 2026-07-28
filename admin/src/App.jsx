import { useCallback, useEffect, useState } from 'react';

import { API_BASE, ApiError, createEvent, getStatus, readToken, updateEvent, writeToken } from './api';
import { EMPTY_EVENT } from './constants';
import DuplicateDialog from './components/DuplicateDialog';
import EventForm from './components/EventForm';
import EventList from './components/EventList';
import ExtractPanel from './components/ExtractPanel';
import TipsPanel from './components/TipsPanel';

const BLANK_RECURRENCE = { enabled: false, weekdays: [], until: '' };

const trimmedOrNull = (value) => {
  const text = (value ?? '').trim();
  return text ? text : null;
};

function toPayload(form, recurrence, { allowRecurrence }) {
  const payload = {
    name: form.name.trim(),
    venue: form.venue.trim(),
    neighborhood: form.neighborhood,
    // `datetime-local` emits exactly the naive Vegas wall clock the API expects.
    starts_at_local: form.starts_at_local,
    ends_at_local: form.ends_at_local,
    vibe: form.vibe,
    price_tier: form.price_tier,
    price_note: trimmedOrNull(form.price_note),
    hook: form.hook.trim(),
    description: form.description.trim(),
    image_url: trimmedOrNull(form.image_url),
    video_url: trimmedOrNull(form.video_url),
    ticket_url: trimmedOrNull(form.ticket_url),
    source_url: trimmedOrNull(form.source_url),
    is_active: form.is_active,
    mirror_image: form.mirror_image,
  };

  if (allowRecurrence && recurrence.enabled) {
    payload.recurrence = {
      weekdays: recurrence.weekdays,
      until_local_date: recurrence.until || null,
    };
  }
  return payload;
}

export default function App() {
  const [token, setToken] = useState(readToken);
  const [tokenInput, setTokenInput] = useState('');
  const [status, setStatus] = useState(null);
  const [gateError, setGateError] = useState(null);
  const [checking, setChecking] = useState(false);

  const [tab, setTab] = useState('add');
  const [refreshKey, setRefreshKey] = useState(0);

  const [form, setForm] = useState(EMPTY_EVENT);
  const [recurrence, setRecurrence] = useState(BLANK_RECURRENCE);
  const [uncertain, setUncertain] = useState(new Set());
  const [editing, setEditing] = useState(null);

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [saved, setSaved] = useState(null);
  const [collisions, setCollisions] = useState(null);

  const connect = useCallback(async () => {
    setChecking(true);
    setGateError(null);
    try {
      setStatus(await getStatus());
    } catch (failure) {
      setStatus(null);
      setGateError(failure.message);
      if (failure instanceof ApiError && failure.status === 401) {
        writeToken('');
        setToken('');
      }
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    if (token) connect();
  }, [token, connect]);

  function signIn(event) {
    event.preventDefault();
    const value = tokenInput.trim();
    if (!value) return;
    writeToken(value);
    setToken(value);
    setTokenInput('');
  }

  function signOut() {
    writeToken('');
    setToken('');
    setStatus(null);
  }

  function resetForm() {
    setForm(EMPTY_EVENT);
    setRecurrence(BLANK_RECURRENCE);
    setUncertain(new Set());
    setEditing(null);
  }

  function loadDraft(result) {
    const draft = result.draft;
    setForm({
      ...EMPTY_EVENT,
      name: draft.name,
      venue: draft.venue,
      neighborhood: draft.neighborhood,
      starts_at_local: draft.starts_at_local,
      ends_at_local: draft.ends_at_local,
      vibe: draft.vibe,
      price_tier: draft.price_tier,
      price_note: draft.price_note ?? '',
      hook: draft.hook,
      description: draft.description,
      ticket_url: draft.ticket_url ?? '',
      image_url: draft.image_url ?? '',
      source_url: draft.source_url ?? '',
    });
    setUncertain(new Set(result.uncertain_fields));
    setEditing(null);
    setSaved(null);
    setSaveError(null);
    setRecurrence(
      result.recurrence.repeats
        ? {
            enabled: true,
            weekdays: result.recurrence.weekdays,
            until: result.recurrence.until_local_date ?? '',
          }
        : BLANK_RECURRENCE,
    );
  }

  function startEditing(event) {
    setForm({
      name: event.name,
      venue: event.venue,
      neighborhood: event.neighborhood,
      starts_at_local: event.starts_at_local,
      ends_at_local: event.ends_at_local,
      vibe: event.vibe,
      price_tier: event.price_tier,
      price_note: event.price_note ?? '',
      hook: event.hook,
      description: event.description,
      image_url: event.image_url ?? '',
      video_url: event.video_url ?? '',
      ticket_url: event.ticket_url ?? '',
      source_url: event.source_url ?? '',
      is_active: event.is_active,
      // Already stored; re-uploading the same file on every edit would be waste.
      mirror_image: false,
    });
    setRecurrence(BLANK_RECURRENCE);
    setUncertain(new Set());
    setEditing(event);
    setSaved(null);
    setSaveError(null);
    setTab('add');
  }

  async function save({ force = false } = {}) {
    setSaving(true);
    setSaveError(null);
    try {
      const payload = toPayload(form, recurrence, { allowRecurrence: !editing });

      if (editing) {
        await updateEvent(editing.id, payload);
        setSaved({ message: `Updated "${payload.name}".` });
      } else {
        const result = await createEvent(payload, { force });
        const count = result.created.length;
        setSaved({
          message:
            count === 1
              ? `Saved "${payload.name}".`
              : `Saved ${count} nights of "${payload.name}".`,
          warning: result.image_warning,
        });
      }

      setCollisions(null);
      resetForm();
      setRefreshKey((key) => key + 1);
    } catch (failure) {
      if (failure.status === 409 && failure.payload?.detail?.collisions) {
        setCollisions(failure.payload.detail.collisions);
      } else {
        setSaveError(failure.message);
      }
    } finally {
      setSaving(false);
    }
  }

  // ---------------------------------------------------------------- gate

  if (!token || !status) {
    return (
      <div className="shell">
        <div className="gate panel">
          <h1>VegasThisWeekend admin</h1>
          <p>
            Paste the ADMIN_TOKEN for <span className="mono">{API_BASE || '(no API configured)'}</span>.
            It is kept in this browser only.
          </p>

          {gateError && (
            <div className="banner" data-tone="error">
              {gateError}
            </div>
          )}

          <form onSubmit={signIn}>
            <div className="field">
              <label htmlFor="token">Admin token</label>
              <input
                id="token"
                type="password"
                value={tokenInput}
                onChange={(event) => setTokenInput(event.target.value)}
                autoComplete="off"
              />
            </div>
            <div className="actions">
              <button type="submit" className="btn btn--primary" disabled={checking || !tokenInput.trim()}>
                {checking ? 'Checking…' : 'Connect'}
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------- app

  const isLive = status.environment === 'production';

  return (
    <div className="shell">
      <header className="topbar">
        <h1>VegasThisWeekend admin</h1>
        <span className="badge" data-tone={isLive ? 'live' : undefined}>
          {isLive ? 'writing to production' : status.environment}
        </span>
        <div className="topbar__meta">
          <span className="badge" data-tone={status.extraction_enabled ? 'on' : 'off'}>
            extraction {status.extraction_enabled ? 'on' : 'off'}
          </span>
          <span className="badge" data-tone={status.r2_enabled ? 'on' : 'off'}>
            images {status.r2_enabled ? 'on' : 'off'}
          </span>
          <span>
            {status.event_count} events
            {status.sample_event_count > 0 && ` · ${status.sample_event_count} sample`}
          </span>
          <button type="button" className="btn btn--ghost btn--small" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>

      <nav className="tabs" role="tablist">
        {[
          ['add', editing ? 'Edit event' : 'Add event'],
          ['events', 'Events'],
          ['tips', 'Insider tips'],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            className="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === 'add' && (
        <>
          {!editing && <ExtractPanel enabled={status.extraction_enabled} onDraft={loadDraft} />}

          <form
            className="panel"
            onSubmit={(event) => {
              event.preventDefault();
              save();
            }}
          >
            <div className="panel__head">
              <h2>{editing ? `Editing: ${editing.name}` : 'Event details'}</h2>
              <p>All times are Las Vegas local.</p>
              {editing && (
                <button type="button" className="btn btn--ghost btn--small spacer" onClick={resetForm}>
                  Cancel edit
                </button>
              )}
            </div>

            {saveError && (
              <div className="banner" data-tone="error">
                {saveError}
              </div>
            )}
            {saved && (
              <div className="banner" data-tone={saved.warning ? 'warn' : 'ok'}>
                {saved.message}
                {saved.warning ? ` Image not mirrored: ${saved.warning}` : ''}
              </div>
            )}

            <EventForm
              value={form}
              onChange={setForm}
              uncertain={uncertain}
              recurrence={recurrence}
              onRecurrenceChange={setRecurrence}
              allowRecurrence={!editing}
            />

            <div className="actions">
              <button type="submit" className="btn btn--primary" disabled={saving}>
                {saving ? 'Saving…' : editing ? 'Save changes' : 'Save event'}
              </button>
              <button type="button" className="btn btn--ghost" onClick={resetForm} disabled={saving}>
                Clear
              </button>
            </div>
          </form>
        </>
      )}

      {tab === 'events' && <EventList onEdit={startEditing} refreshKey={refreshKey} />}
      {tab === 'tips' && <TipsPanel />}

      {collisions && (
        <DuplicateDialog
          collisions={collisions}
          saving={saving}
          onCancel={() => setCollisions(null)}
          onSaveAnyway={() => save({ force: true })}
        />
      )}
    </div>
  );
}
