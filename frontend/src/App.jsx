import { useCallback, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { trackFilterChanged } from './analytics';
import DiscoverScreen from './components/DiscoverScreen';
import SavedScreen from './components/SavedScreen';
import SharedListScreen from './components/SharedListScreen';
import TabBar from './components/TabBar';
import { DEFAULT_FILTERS } from './constants';
import { fullDateLabel } from './format';

export default function App() {
  // Held here rather than in the screen so a trip to Saved and back does not reset them.
  const [filters, setFilters] = useState(DEFAULT_FILTERS);

  const changeFilters = useCallback((next) => {
    setFilters(next);
    // Which vibes and price bands people actually reach for — the clearest signal about
    // what the catalog is missing.
    trackFilterChanged({
      date: next.date,
      vibes: next.vibes.length ? next.vibes.join(',') : 'any',
      prices: next.prices.length ? next.prices.join(',') : 'any',
    });
  }, []);

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
        <Route path="/" element={<DiscoverScreen filters={filters} onFiltersChange={changeFilters} />} />
        <Route path="/saved" element={<SavedScreen />} />
        <Route path="/s/:token" element={<SharedListScreen />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      <TabBar />
    </div>
  );
}
