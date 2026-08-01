import { useState } from 'react';
import { trackSubscribe } from '../analytics';
import { subscribe } from '../api';

// The weekly email signup.
//
// This is the one deliberate exception to "no accounts, no cookies": an address is
// personal data, where nothing else the app stores is. It earns the exception by fixing
// the problem the app cannot fix on its own — an app is only useful to someone who
// remembers to open it, and an email arrives whether they remember or not.
//
// Stated plainly rather than dressed up: what it is, how often, and that it is only used
// for that. No pre-ticked anything, no interstitial, and it sits at the end of the list
// where someone has already seen what the app does, rather than in front of it.

// Deliberately promises no day and no first-issue date.
//
// The first version said "every Thursday" and "first issue lands Thursday", which is a
// dated commitment made to whoever signs up first — and the first signups are the people
// most likely to notice it going unmet. Nobody signing up is counting on a particular
// Thursday; they are counting on the thing being good when it arrives. Say what it is,
// not when, until there is a list worth sending to and an issue ready to send.
const COPY = {
  list_end: {
    title: 'That’s everything on right now',
    body: 'Get the week’s picks by email — the things worth leaving the house for, not the same Strip listings.',
  },
  saved: {
    title: 'Keep the good ones coming',
    body: 'A short weekly email with the week’s picks. Your saved list stays on this device either way.',
  },
};

export default function EmailCapture({ source }) {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('idle'); // idle | sending | done | error
  const [error, setError] = useState(null);

  const copy = COPY[source] ?? COPY.list_end;

  async function handleSubmit(submitEvent) {
    submitEvent.preventDefault();
    if (status === 'sending') return;

    setStatus('sending');
    setError(null);
    try {
      await subscribe(email.trim(), source);
      trackSubscribe();
      setStatus('done');
    } catch (failure) {
      setError(failure.message ?? 'Could not sign you up. Try again.');
      setStatus('error');
    }
  }

  if (status === 'done') {
    // Says "if you were not already", because the endpoint deliberately cannot tell the
    // difference — answering that would let anyone test whether an address is on the list.
    return (
      <section className="signup signup--done">
        <p className="signup__title">You’re on the list</p>
        <p className="signup__body">
          You’ll get the first issue soon. Nothing else is sent to this address.
        </p>
      </section>
    );
  }

  return (
    <section className="signup">
      <h2 className="signup__title">{copy.title}</h2>
      <p className="signup__body">{copy.body}</p>

      <form className="signup__form" onSubmit={handleSubmit}>
        <label className="signup__label" htmlFor={`signup-${source}`}>
          Email address
        </label>
        <div className="signup__row">
          <input
            id={`signup-${source}`}
            className="signup__input"
            type="email"
            name="email"
            value={email}
            onChange={(changeEvent) => setEmail(changeEvent.target.value)}
            placeholder="you@example.com"
            required
            autoComplete="email"
            inputMode="email"
            // The browser's own validation catches a missing @ before a request goes
            // out; the server validates properly either way.
            aria-describedby={`signup-note-${source}`}
          />
          <button
            type="submit"
            className="btn btn--primary"
            disabled={status === 'sending' || email.trim() === ''}
          >
            {status === 'sending' ? 'Signing up…' : 'Sign up'}
          </button>
        </div>

        {status === 'error' && (
          <p className="signup__error" role="alert">
            {error}
          </p>
        )}

        {/* "At most" rather than "one email a week": a cap cannot be broken by a quiet
            week, where a promised frequency can. */}
        <p className="signup__note" id={`signup-note-${source}`}>
          At most one email a week. No account, no tracking, unsubscribe any time.
        </p>
      </form>
    </section>
  );
}
