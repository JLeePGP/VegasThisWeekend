import { Component } from 'react';

/**
 * Catches render errors so a single bad component cannot white-screen the app.
 *
 * Deliberately a class: `getDerivedStateFromError` and `componentDidCatch` have no hook
 * equivalent, so this is still the only way to build one in React 19.
 *
 * What it does NOT catch, so nobody is surprised later: event handlers, async work
 * (fetch, timers), and errors thrown during SSR. Those still need their own try/catch —
 * the API layer already handles its own failures and surfaces them as empty states.
 */
export default class ErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    // Console only. Sending this anywhere would mean shipping a third-party error
    // reporter, and stack traces can carry user content — neither fits the app's
    // no-third-parties, no-PII stance. Revisit if first-party logging ever lands.
    console.error('Render error:', error, info?.componentStack);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (!this.state.failed) return this.props.children;

    return (
      <div className="crash" role="alert">
        <div className="crash__inner">
          <p className="crash__kicker">Something broke</p>
          <h1 className="crash__title">
            That&rsquo;s on us,
            <br />
            not on you.
          </h1>
          <p className="crash__body">
            The page hit an error it couldn&rsquo;t recover from. Reloading usually sorts
            it. Your saved events are stored on this device and are still there.
          </p>
          <button type="button" className="crash__button" onClick={this.handleReload}>
            Reload
          </button>
        </div>
      </div>
    );
  }
}
