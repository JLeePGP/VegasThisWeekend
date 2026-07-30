import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { trackDetailOpened, trackShareCreated } from '../analytics';
import { createShareList } from '../api';
import { MAX_SHARE_EVENTS } from '../constants';
import { expiresInDays } from '../format';
import { useSavedEvents } from '../store/savedEvents';
import { useToast } from '../store/toast';
import EmptyState from './EmptyState';
import EventSheet from './EventSheet';
import { IconClose, IconShare } from './Icons';
import SavedRow from './SavedRow';

export default function SavedScreen() {
  const navigate = useNavigate();
  const { saved, remove, save, isSaved } = useSavedEvents();
  const { show } = useToast();
  const [detail, setDetail] = useState(null);
  const [sharing, setSharing] = useState(false);
  // The result stays on screen instead of a toast that vanishes. A toast could say "Link
  // copied" but gave no way to check what had actually been made, or what a recipient
  // would see — which is the part that was missing.
  const [share, setShare] = useState(null); // { url, count, truncated, expiresAt, copied }

  const openDetail = useCallback((event) => {
    trackDetailOpened({ vibe: event.vibe, source: 'saved' });
    setDetail(event);
  }, []);

  async function copyLink(url) {
    try {
      await navigator.clipboard.writeText(url);
      return true;
    } catch {
      // Blocked outright, or not a secure context. The panel shows the link either way,
      // so this degrades to "select it yourself" rather than to nothing.
      return false;
    }
  }

  async function handleShare() {
    setSharing(true);
    try {
      const shared = saved.slice(0, MAX_SHARE_EVENTS);
      const { path, expires_at: expiresAt } = await createShareList(
        shared.map((event) => event.id),
      );
      const url = `${window.location.origin}${path}`;
      const truncated = saved.length > MAX_SHARE_EVENTS;

      // Counted at creation, not at delivery: whether they then complete the native
      // share sheet is outside our knowledge, and the token itself is never sent.
      trackShareCreated({ count: shared.length, truncated });

      // Copy before offering the native sheet, so the panel can state truthfully whether
      // the link reached the clipboard rather than claiming it optimistically.
      const copied = await copyLink(url);
      setShare({ url, count: shared.length, truncated, expiresAt, copied });

      // The link exists and is on screen, so the work is done. Clearing the busy state
      // here rather than in `finally` matters: the native share sheet below can stay
      // open indefinitely, and awaiting it left the button stuck on "Creating link…"
      // for as long as the sheet was up — or forever if it never settled.
      setSharing(false);

      // The native sheet is the better hand-off where it exists, but it needs a secure
      // context and a user gesture. The panel stays up behind it either way.
      if (navigator.share) {
        try {
          await navigator.share({ title: 'Vegas This Weekend', text: 'Here’s my list:', url });
        } catch (error) {
          // Dismissing the sheet is a cancellation, not a failure worth reporting.
          if (error.name !== 'AbortError') {
            /* fall through — the panel already has the link */
          }
        }
      }
    } catch (error) {
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
        {share ? (
          <div className="sharelink">
            <div className="sharelink__head">
              <strong className="sharelink__title">
                {share.copied ? 'Link copied' : 'Link ready'}
              </strong>
              <button
                type="button"
                className="sharelink__dismiss"
                onClick={() => setShare(null)}
                aria-label="Dismiss share link"
              >
                <IconClose width={16} height={16} />
              </button>
            </div>

            {/* Readonly rather than plain text: it stays selectable on every platform,
                which is the fallback when the clipboard is blocked. */}
            <input
              className="sharelink__url"
              value={share.url}
              readOnly
              onFocus={(e) => e.target.select()}
              aria-label="Share link"
            />

            <div className="sharelink__actions">
              <button
                type="button"
                className="btn btn--secondary"
                onClick={async () => {
                  const copied = await copyLink(share.url);
                  setShare((current) => ({ ...current, copied }));
                  if (!copied) show('Copy blocked — select the link and copy it.', 'error');
                }}
              >
                {share.copied ? 'Copy again' : 'Copy'}
              </button>
              {/* Answers "what does the recipient actually get" by just showing them. */}
              <a
                className="btn btn--secondary"
                href={share.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Preview
              </a>
            </div>

            <p className="sharelink__meta">
              {share.count} {share.count === 1 ? 'event' : 'events'}
              {share.truncated && ` (the first ${MAX_SHARE_EVENTS} of your ${saved.length})`} ·
              expires in {expiresInDays(share.expiresAt)} days. This link is a snapshot —
              saving or removing events now won&rsquo;t change it.
            </p>
          </div>
        ) : (
          <button
            type="button"
            className="btn btn--primary btn--block"
            onClick={handleShare}
            disabled={sharing}
          >
            <IconShare width={18} height={18} />
            {sharing ? 'Creating link…' : 'Share this list'}
          </button>
        )}
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
