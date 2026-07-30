import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { trackDetailOpened, trackShareCreated } from '../analytics';
import { createShareList } from '../api';
import { MAX_SHARE_EVENTS } from '../constants';
import { useSavedEvents } from '../store/savedEvents';
import { useToast } from '../store/toast';
import EmptyState from './EmptyState';
import EventSheet from './EventSheet';
import { IconShare } from './Icons';
import SavedRow from './SavedRow';

export default function SavedScreen() {
  const navigate = useNavigate();
  const { saved, remove, save, isSaved } = useSavedEvents();
  const { show } = useToast();
  const [detail, setDetail] = useState(null);
  const [sharing, setSharing] = useState(false);

  const openDetail = useCallback((event) => {
    trackDetailOpened({ vibe: event.vibe, source: 'saved' });
    setDetail(event);
  }, []);

  async function handleShare() {
    setSharing(true);
    try {
      const shared = saved.slice(0, MAX_SHARE_EVENTS);
      const { path } = await createShareList(shared.map((event) => event.id));
      const url = `${window.location.origin}${path}`;
      const trimmed = saved.length > MAX_SHARE_EVENTS;

      // Counted at creation, not at delivery: whether they then complete the native
      // share sheet is outside our knowledge, and the token itself is never sent.
      trackShareCreated({ count: shared.length, truncated: trimmed });

      // The native share sheet is the better experience where it exists. If it is missing
      // or refuses (it needs a secure context and a user gesture), fall through to the
      // clipboard rather than leaving the tap with nothing to show for it.
      if (navigator.share) {
        try {
          await navigator.share({ title: 'Vegas This Weekend', text: 'Here’s my list:', url });
          if (trimmed) show(`Shared the first ${MAX_SHARE_EVENTS} of your ${saved.length} saves.`);
          else show('Shared.');
          return;
        } catch (error) {
          // Dismissing the sheet is a cancellation, not a failure worth recovering from.
          if (error.name === 'AbortError') return;
        }
      }

      const suffix = trimmed
        ? ` — the first ${MAX_SHARE_EVENTS} of your ${saved.length} saves.`
        : '.';
      try {
        await navigator.clipboard.writeText(url);
        show(`Link copied${suffix}`);
      } catch {
        // Clipboard access can be blocked outright; showing the link still lets them copy it.
        show(url);
      }
    } catch (error) {
      // Dismissing the native share sheet is a cancellation, not a failure.
      if (error.name === 'AbortError') return;
      show(error.message ?? 'Could not create a share link.', 'error');
    } finally {
      setSharing(false);
    }
  }

  if (saved.length === 0) {
    return (
      <div className="screen">
        <EmptyState
          icon="♡"
          title="Nothing saved yet"
          body="Swipe right on anything that looks good and it will show up here, ready to share."
        >
          <button type="button" className="btn btn--primary" onClick={() => navigate('/')}>
            Start swiping
          </button>
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="screen">
      <p className="screen__intro">
        {saved.length} saved {saved.length === 1 ? 'event' : 'events'}, in the order they happen.
        Saved on this device only.
      </p>

      <ul className="saved-list">
        {saved.map((event) => (
          <SavedRow key={event.id} event={event} onOpen={openDetail} onRemove={remove} />
        ))}
      </ul>

      <div className="sharebar">
        <button
          type="button"
          className="btn btn--primary btn--block"
          onClick={handleShare}
          disabled={sharing}
        >
          <IconShare width={18} height={18} />
          {sharing ? 'Creating link…' : 'Share this list'}
        </button>
      </div>

      <EventSheet
        event={detail}
        open={detail !== null}
        onClose={() => setDetail(null)}
        onSave={save}
        isSaved={detail ? isSaved(detail.id) : false}
      />
    </div>
  );
}
