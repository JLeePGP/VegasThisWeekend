import { useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  trackDetailOpen,
  trackSave,
  trackTicketClick,
  trackTipReveal,
  trackVideoPlay,
  trackWebsiteClick,
} from '../analytics';
import { fetchEvent } from '../api';
import { priceLabel, vibeLabel } from '../constants';
import { fullDateLabel, rangeLabel } from '../format';
import { mapsUrl } from '../maps';
import { useSavedEvents } from '../store/savedEvents';
import EmptyState from './EmptyState';
import {
  IconArrowLeft,
  IconChevronDown,
  IconGlobe,
  IconPin,
  IconPlay,
  IconSave,
  IconTicket,
  IconTip,
} from './Icons';
import Poster from './Poster';
import VideoPlayer from './VideoPlayer';

// The detail view, at its own URL.
//
// It was a bottom sheet over the deck. A sheet made sense when the card behind it was the
// app; now the list is the app, and details are a place you go — which means a back
// button that works, a link that can be sent to someone, and a page that survives a
// refresh. It is also the only shape that can ever be indexed, though nothing here does
// server-side rendering yet.
//
// The image is a bounded hero rather than a full-bleed background. Everything below it is
// text on the page's own surface, so nothing has to be legible over an unpredictable
// photo.

export default function EventScreen() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { save, isSaved } = useSavedEvents();

  // Arriving from a list carries the event in router state, so the common path renders
  // immediately. A direct link, a refresh or a shared URL has none, and fetches.
  const passed = location.state?.event;
  const [event, setEvent] = useState(passed ?? null);
  const [error, setError] = useState(null);
  const [tipRevealed, setTipRevealed] = useState(false);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (passed?.id === id) {
      setEvent(passed);
      return;
    }

    const controller = new AbortController();
    setEvent(null);
    setError(null);
    fetchEvent(id, { signal: controller.signal })
      .then(setEvent)
      .catch((failure) => {
        if (failure.name === 'AbortError') return;
        setError(failure.message);
      });
    return () => controller.abort();
  }, [id, passed]);

  // Counted once per event opened, not on every render this component does.
  useEffect(() => {
    if (event?.id) trackDetailOpen(event.id);
  }, [event?.id]);

  useEffect(() => setTipRevealed(false), [id]);

  // Back to wherever they came from, which keeps the list's scroll position. A direct
  // link has nothing to go back to, so that lands on the list instead.
  const goBack = () => (location.key === 'default' ? navigate('/') : navigate(-1));

  if (error) {
    return (
      <div className="screen">
        <EmptyState
          icon="🌵"
          title="This event isn't here"
          body="It may have finished, or been taken down."
        >
          <button type="button" className="btn btn--primary" onClick={() => navigate('/')}>
            See what's on
          </button>
        </EmptyState>
      </div>
    );
  }

  if (!event) {
    return (
      <div className="screen">
        <div className="skeleton" aria-label="Loading event" />
      </div>
    );
  }

  const saved = isSaved(event.id);

  return (
    <div className="screen screen--detail">
      <button type="button" className="detail__back" onClick={goBack}>
        <IconArrowLeft width={18} height={18} />
        Back
      </button>

      <div className="detail__hero">
        <Poster event={event} />

        {/* Video lives behind this button and nowhere else. It is not the background of
            this page, and it is not in the list. */}
        {event.video_url && (
          <button
            type="button"
            className="detail__play"
            onClick={() => {
              trackVideoPlay(event.id);
              setPlaying(true);
            }}
          >
            <IconPlay width={20} height={20} />
            Play video
          </button>
        )}
      </div>

      <h1 className="detail__title">{event.name}</h1>

      <dl className="detail__facts">
        <div className="detail__fact">
          <dt>When</dt>
          <dd>
            {fullDateLabel(event.start_at)} · {rangeLabel(event.start_at, event.end_at)}
          </dd>
        </div>
        <div className="detail__fact">
          <dt>Where</dt>
          <dd>
            {event.venue}, {event.neighborhood}
            {event.address && <span className="detail__address">{event.address}</span>}
            <a
              className="detail__maplink"
              href={mapsUrl(event)}
              target="_blank"
              rel="noopener noreferrer"
            >
              <IconPin width={14} height={14} />
              Open in Maps
            </a>
          </dd>
        </div>
        <div className="detail__fact">
          <dt>Price</dt>
          <dd>{event.price_note || priceLabel(event.price_tier)}</dd>
        </div>
        <div className="detail__fact">
          <dt>Category</dt>
          <dd>{vibeLabel(event.vibe)}</dd>
        </div>
      </dl>

      <p className="detail__description">{event.description}</p>

      {event.source_url && (
        <a
          className="detail__link"
          href={event.source_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => trackWebsiteClick(event.id)}
        >
          <IconGlobe width={16} height={16} />
          Event website
        </a>
      )}

      {event.insider_tip && (
        <div className="tip">
          <button
            type="button"
            className="tip__toggle"
            aria-expanded={tipRevealed}
            onClick={() => {
              // Only count the reveal, not the collapse.
              if (!tipRevealed) trackTipReveal(event.id);
              setTipRevealed((current) => !current);
            }}
          >
            <IconTip className="tip__icon" width={20} height={20} />
            Insider tip
            <IconChevronDown className="tip__chevron" width={18} height={18} />
          </button>
          {tipRevealed && <p className="tip__body">{event.insider_tip}</p>}
        </div>
      )}

      <div className="detail__actions">
        {event.ticket_url && (
          <a
            className="btn btn--secondary"
            href={event.ticket_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => trackTicketClick(event.id)}
          >
            <IconTicket width={18} height={18} />
            Tickets
          </a>
        )}
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={saved}
          onClick={() => {
            trackSave(event.id);
            save(event);
          }}
        >
          <IconSave width={18} height={18} />
          {saved ? 'Saved' : 'Save'}
        </button>
      </div>

      {playing && (
        <VideoPlayer
          src={event.video_url}
          poster={event.image_url}
          onClose={() => setPlaying(false)}
        />
      )}
    </div>
  );
}
