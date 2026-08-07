import { useCallback, useSyncExternalStore } from 'react';

// Width, deliberately, and not the device.
//
// The obvious-looking alternative is to read the user-agent and decide "this is a phone".
// It does not work: iPadOS reports itself as macOS, Chrome freezes its UA string, and
// neither answers what should happen when a desktop window is dragged narrow or docked
// beside another app. Width answers all three for free and needs nothing from the server.
//
// `useSyncExternalStore` rather than a useState/useEffect pair. That pair renders once
// with the wrong answer and then corrects itself, which on this app would mean every
// desktop visitor seeing a flash of the mobile layout on first paint.
export default function useMediaQuery(query) {
  const subscribe = useCallback(
    (notify) => {
      const list = window.matchMedia(query);
      list.addEventListener('change', notify);
      return () => list.removeEventListener('change', notify);
    },
    [query],
  );

  const getSnapshot = useCallback(() => window.matchMedia(query).matches, [query]);

  // Nothing server-renders this app today, but the route-render checks used during
  // verification do run these components without a window. Mobile-first is the safe
  // assumption: it is the layout that works at every width.
  const getServerSnapshot = () => false;

  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
