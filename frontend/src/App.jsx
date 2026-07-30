import { useCallback, useState } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
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

  // Discover runs immersive: media fills the shell and the chrome floats over it. Saved
  // and shared lists are ordinary scrolling documents and keep the opaque chrome, so the
  // mode is a property of the route rather than something the screens negotiate.
  const immersive = useLocation().pathname === '/';

  const changeFilters = useCallback((next) => {
    setFilters(next);
    // Which vibes and price bands people actually reach for — the clearest signal about
    // what the catalog is missing.
    trackFilterChanged({
      date: next.date,
      vibes: next.vibes.length ? next.vibes.join(',') : 'any',
      prices: next.prices.length ? next.prices.join(',') : 'any',
      alcoholFree: next.alcoholFree,
    });
  }, []);

  return (
    <div className={immersive ? 'app app--immersive' : 'app'}>
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
