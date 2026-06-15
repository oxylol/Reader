import { NavLink } from "react-router-dom";

export default function BottomNav({ isAdmin }: { isAdmin: boolean }) {
  void isAdmin;
  return (
    <nav className="bottom-nav">
      <NavLink to="/" end>
        <span className="ico">📚</span>
        Library
      </NavLink>
      <NavLink to="/browse">
        <span className="ico">🔍</span>
        Browse
      </NavLink>
      <NavLink to="/settings">
        <span className="ico">⚙️</span>
        Settings
      </NavLink>
    </nav>
  );
}
