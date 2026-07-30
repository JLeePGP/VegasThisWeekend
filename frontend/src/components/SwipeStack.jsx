import { useCallback, useEffect, useRef, useState } from 'react';
import { useSwipeable } from 'react-swipeable';
import EventCard from './EventCard';

// How far a card must travel before releasing it counts as a decision. A fast flick
// commits much earlier, which is how the gesture feels right on a phone.
const COMMIT_DISTANCE = 110;
const FLICK_VELOCITY = 0.5;
const FLICK_DISTANCE = 45;

// Must match the .stack__slot[data-leaving] transition duration.
const EXIT_MS = 300;

const VISIBLE_CARDS = 3;
// Movement under this is a tap, not a drag, so the card stays put and onClick fires.
const TAP_SLOP = 8;

// Stamps reach full strength at roughly half the commit distance rather than at the
// commit point itself, so the verdict is readable while you are still deciding — which
// is the only moment it is useful.
const STAMP_RAMP = 2.1;
const stampOpacity = (value) => Math.min(1, Math.max(0, value * STAMP_RAMP));

export default function SwipeStack({
  events,
  onSave,
  onDismiss,
  onExpand,
  inputLocked = false,
  // Filled with { save, skip } so the on-screen buttons drive the same animation path
  // as a gesture, instead of a second code path that can drift out of sync.
  controlsRef,
}) {
  const [drag, setDrag] = useState(null); // { x, y } while a finger or mouse is down
  const [leaving, setLeaving] = useState(null); // 'save' | 'skip' during the exit animation
  const committingRef = useRef(false);
  const timerRef = useRef(null);

  const top = events[0] ?? null;

  useEffect(() => () => window.clearTimeout(timerRef.current), []);

  const commit = useCallback(
    // `method` is passed through to the parent purely so analytics can tell a real
    // gesture from the buttons or arrow keys — worth knowing for a product whose whole
    // premise is the swipe.
    (direction, method) => {
      if (committingRef.current || !top) return;
      committingRef.current = true;
      setLeaving(direction);

      // Let the card fly off before telling the parent to drop it, otherwise the next
      // card snaps into place while this one is still mid-flight.
      timerRef.current = window.setTimeout(() => {
        setLeaving(null);
        setDrag(null);
        committingRef.current = false;
        (direction === 'save' ? onSave : onDismiss)(top, method);
      }, EXIT_MS);
    },
    [top, onSave, onDismiss],
  );

  useEffect(() => {
    if (!controlsRef) return;
    controlsRef.current = {
      save: () => commit('save', 'button'),
      skip: () => commit('skip', 'button'),
    };
  }, [controlsRef, commit]);

  const handlers = useSwipeable({
    onSwiping: (gesture) => {
      if (committingRef.current || inputLocked) return;
      // deltaX is (current - start): positive is a drag to the right, toward save.
      setDrag({ x: gesture.deltaX, y: gesture.deltaY });
    },
    onSwiped: (gesture) => {
      if (committingRef.current || inputLocked) {
        setDrag(null);
        return;
      }
      const travelled = gesture.deltaX;
      const flicked = gesture.velocity > FLICK_VELOCITY;

      if (travelled > COMMIT_DISTANCE || (flicked && travelled > FLICK_DISTANCE)) {
        commit('save', 'gesture');
      } else if (travelled < -COMMIT_DISTANCE || (flicked && travelled < -FLICK_DISTANCE)) {
        commit('skip', 'gesture');
      } else {
        setDrag(null);
      }
    },
    trackMouse: true,
    preventScrollOnSwipe: true,
    delta: TAP_SLOP,
  });

  // Desktop fallback, as the swipe gesture has no meaning without a touchscreen.
  useEffect(() => {
    if (inputLocked || !top) return undefined;

    const handleKey = (keyEvent) => {
      if (keyEvent.metaKey || keyEvent.ctrlKey || keyEvent.altKey) return;
      if (keyEvent.key === 'ArrowLeft') {
        keyEvent.preventDefault();
        commit('skip', 'keyboard');
      } else if (keyEvent.key === 'ArrowRight') {
        keyEvent.preventDefault();
        commit('save', 'keyboard');
      } else if (keyEvent.key === 'ArrowUp') {
        keyEvent.preventDefault();
        onExpand(top);
      }
    };

    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [commit, inputLocked, onExpand, top]);

  const intent = leaving ? (leaving === 'save' ? 1 : -1) : (drag?.x ?? 0) / COMMIT_DISTANCE;

  function topCardStyle() {
    if (leaving) {
      const direction = leaving === 'save' ? 1 : -1;
      return {
        transform: `translate(${direction * 130}%, ${(drag?.y ?? 0) * 0.4}px) rotate(${direction * 22}deg)`,
      };
    }
    if (drag) {
      // Vertical movement is damped: this is a horizontal decision, and letting the card
      // wander up and down makes it feel loose.
      return {
        transform: `translate(${drag.x}px, ${drag.y * 0.35}px) rotate(${drag.x / 20}deg)`,
      };
    }
    return undefined;
  }

  return (
    <div className="stack">
      {events.slice(0, VISIBLE_CARDS).map((event, depth) => {
        const isTop = depth === 0;
        return (
          <div
            key={event.id}
            className="stack__slot"
            data-depth={depth}
            data-leaving={isTop && Boolean(leaving)}
            data-settling={isTop && !drag && !leaving}
            style={isTop ? topCardStyle() : undefined}
            {...(isTop ? handlers : {})}
          >
            <EventCard event={event} isTop={isTop} onExpand={() => onExpand(event)} />
          </div>
        );
      })}

      {/* Verdict stamps belong to the stack, not to the card. Inside the card they
          travelled with it and slid off the edge of the screen at exactly the moment
          you needed to read them — which is the reason they were hard to see. Pinned
          here they stay put while the card moves under them. */}
      <span className="stack__verdict stack__verdict--save" style={{ opacity: stampOpacity(intent) }}>
        Save
      </span>
      <span className="stack__verdict stack__verdict--skip" style={{ opacity: stampOpacity(-intent) }}>
        Skip
      </span>
    </div>
  );
}

export { COMMIT_DISTANCE };
