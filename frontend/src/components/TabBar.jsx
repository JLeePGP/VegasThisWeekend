import { NavLink } from 'react-router-dom';
import { useSavedEvents } from '../store/savedEvents';
import { IconCompass, IconSave } from './Icons';

export default function TabBar() {
  const { saved } = useSavedEvents();

  return (
    <nav className="tabbar" aria-label="Main">
      <NavLink to="/" className="tab" end>
        <IconCompass width={19} height={19} />
        Discover
      </NavLink>
      <NavLink to="/saved" className="tab">
        <IconSave width={17} height={17} />
        Saved
        {saved.length > 0 && <span className="tab__count">{saved.length}</span>}
      </NavLink>
    </nav>
  );
}
