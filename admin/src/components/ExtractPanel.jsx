import { useState } from 'react';
import { extract } from '../api';

/**
 * Paste a URL, get a draft. The text mode is not a nicety — Instagram and Facebook
 * posts are login-walled and no server-side fetch will ever reach them, so pasting the
 * post's text is the only path for a real slice of the PRD's sources.
 */
export default function ExtractPanel({ enabled, onDraft }) {
  const [mode, setMode] = useState('url');
  const [url, setUrl] = useState('');
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notes, setNotes] = useState(null);

  const canSubmit = enabled && !busy && (mode === 'url' ? url.trim() : text.trim());

  async function run(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotes(null);

    try {
      const result = await extract(mode === 'url' ? { url: url.trim() } : { text: text.trim() });

      if (!result.found_event) {
        setNotes(result.notes || 'No specific event was found on that page.');
        return;
      }

      onDraft(result);
      setNotes(
        result.uncertain_fields.length
          ? `Draft loaded. ${result.uncertain_fields.length} field(s) were guessed — highlighted below.`
          : 'Draft loaded. Check it over before saving.',
      );
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={run}>
      <div className="panel__head">
        <h2>Extract from a link</h2>
        <p>Claude reads the page and fills the form. Nothing saves until you say so.</p>
        <button
          type="button"
          className="btn btn--ghost btn--small spacer"
          onClick={() => {
            setMode(mode === 'url' ? 'text' : 'url');
            setError(null);
            setNotes(null);
          }}
        >
          {mode === 'url' ? 'Paste text instead' : 'Use a URL instead'}
        </button>
      </div>

      {!enabled && (
        <div className="banner" data-tone="warn">
          ANTHROPIC_API_KEY is not set on the API, so extraction is off. Manual entry below
          works exactly as normal.
        </div>
      )}

      {error && (
        <div className="banner" data-tone="error">
          {error}
        </div>
      )}
      {notes && (
        <div className="banner" data-tone="info">
          {notes}
        </div>
      )}

      {mode === 'url' ? (
        <div className="field">
          <label htmlFor="extract-url">Event URL</label>
          <input
            id="extract-url"
            type="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://www.eventbrite.com/e/..."
            disabled={!enabled}
          />
        </div>
      ) : (
        <div className="field">
          <label htmlFor="extract-text">Pasted text</label>
          <textarea
            id="extract-text"
            rows={6}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Paste the post, flyer text, or listing here — anything a server can't fetch."
            disabled={!enabled}
          />
        </div>
      )}

      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={!canSubmit}>
          {busy ? 'Reading…' : 'Extract'}
        </button>
        <span className="field__note" style={{ marginLeft: 0 }}>
          Takes a few seconds — it fetches and reads the whole page.
        </span>
      </div>
    </form>
  );
}
