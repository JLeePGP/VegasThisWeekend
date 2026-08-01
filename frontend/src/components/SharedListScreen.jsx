import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { trackSave, trackShareOpen } from '../analytics';
import { fetchShareList } from '../api';
import { expiresInDays } from '../format';
import { useSavedEvents } from '../store/savedEvents';
import { useToast } from '../store/toast';
import EmptyState from './EmptyState';
import EventRow from './EventRow';

export default function SharedListScreen() {
  const { token } = useParams();
  const navigate = useNavigate();
  const { save, isSaved, savedIds } = useSavedEvents();
  const { show } = useToast();

  const [state, setState] = useState({ status: 'loading', data: null, error: null });

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: 'loading', data: null, error: null });

    fetchShareList(token, { signal: controller.signal })
      .then((data) => {
        // The real spread metric: links created only measures intent, this measures
        // reach. The token is deliberately not sent — only how many events it held.
        trackShareOpen();
        setState({ status: 'ready', data, error: null });
      })
      .catch((error) => {
        if (error.name === 'AbortError') return;
        setState({ status: 'error', data: null, error: error.message });
      });

    return () => controller.abort();
  }, [token]);

  if (state.status === 'loading') {
    return (
      <div className="screen">
        <EmptyState title="Opening list…" />
      </div>
    );
  }

  if (state.status === 'error') {
    return (
      <div className="screen">
        <EmptyState
          icon="🔗"
          title="This link isn't available"
          body="Shared lists last 30 days. This one has expired, or the link is wrong."
        >
          <button type="button" className="btn btn--primary" onClick={() => navigate('/')}>
            Find something to do
          </button>
        </EmptyState>
      </div>
    );
  }

  const { events, expires_at: expiresAt } = state.data;
  const unsaved = events.filter((event) => !savedIds.has(event.id));

  function saveAll() {
    unsaved.forEach((event) => {
      trackSave(event.id);
      save(event);
    });
    show(`Added ${unsaved.length} ${unsaved.length === 1 ? 'event' : 'events'} to your list.`);
  }

  return (
    <div className="screen">
      <p className="screen__intro">
        Someone shared {events.length} {events.length === 1 ? 'event' : 'events'} with you. This
        link expires in {expiresInDays(expiresAt)} days.
      </p>

      <ul className="list">
        {events.map((event) => (
          <EventRow
            key={event.id}
            event={event}
            withDay
            onSave={(saveTarget) => {
              trackSave(saveTarget.id);
              save(saveTarget);
            }}
            isSaved={isSaved(event.id)}
          />
        ))}
      </ul>

      <div className="sharebar">
        {unsaved.length > 0 ? (
          <button type="button" className="btn btn--primary btn--block" onClick={saveAll}>
            Save {unsaved.length === events.length ? 'all' : `${unsaved.length} more`} to my list
          </button>
        ) : (
          <button type="button" className="btn btn--secondary btn--block" onClick={() => navigate('/')}>
            Find more to do
          </button>
        )}
      </div>
    </div>
  );
}
