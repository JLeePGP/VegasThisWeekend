import { useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import EventScreen from './components/EventScreen';
import ListScreen from './components/ListScreen';
import SavedScreen from './components/SavedScreen';
import SharedListScreen from './components/SharedListScreen';
import TabBar from './components/TabBar';
import { DEFAULT_FILTERS } from './constants';
import { fullDateLabel } from './format';

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

  return (
    <div className="app">
      <header className="topbar">
        <h1 className="wordmark">Vegas This Weekend</h1>
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

      <TabBar />
    </div>
  );
}
