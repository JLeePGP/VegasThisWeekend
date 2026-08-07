import { useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import EventScreen from './components/EventScreen';
import ListScreen from './components/ListScreen';
import SavedScreen from './components/SavedScreen';
import SharedListScreen from './components/SharedListScreen';
import TabBar from './components/TabBar';
import { DEFAULT_FILTERS, DESKTOP_QUERY } from './constants';
import { fullDateLabel } from './format';
import useMediaQuery from './hooks/useMediaQuery';

export default function App() {
  // Held here rather than in the screen so a trip to Saved, or into an event and back,
  // does not reset them.
  const [filters, setFilters] = useState(DEFAULT_FILTERS);

  // Every screen is now an ordinary scrolling document with opaque chrome. The immersive
  // mode that used to apply to the deck — media filling the shell, controls floating over
  // it — went with the deck itself.

  // Filter changes are not counted. Plausible could carry an arbitrary string prop
  // cheaply; first-party counters are (day, metric, event) rows, and a combinatorial
  // filter string does not fit that shape without a table whose only job is saying which
  // chips are popular. Worth adding if that question ever gets asked — it is not one of
  // the four the PRD cares about.
  const changeFilters = setFilters;

  // A bottom tab bar is a phone convention — it sits where a thumb is. On a desktop
  // pointer it is just navigation parked in the least reachable corner of the window, so
  // the same component moves into the header instead. One `TabBar`, two positions: the
  // links, the counter and the active state are identical in both.
  const isDesktop = useMediaQuery(DESKTOP_QUERY);

  return (
    <div className="app">
      <header className="topbar">
        <h1 className="wordmark">Vegas This Weekend</h1>
        {isDesktop && <TabBar />}
        <div className="topbar__clock">
          <strong>{fullDateLabel(new Date())}</strong>
          <span>Vegas time</span>
        </div>
      </header>

      <Routes>
        <Route path="/" element={<ListScreen filters={filters} onFiltersChange={changeFilters} />} />
        <Route path="/e/:id" element={<EventScreen />} />
        <Route path="/saved" element={<SavedScreen />} />
        <Route path="/s/:token" element={<SharedListScreen />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {!isDesktop && <TabBar />}
    </div>
  );
}
