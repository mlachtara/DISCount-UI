import { NavLink } from "react-router-dom";

export default function Navigation() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded-md text-sm font-medium transition-colors ${
      isActive
        ? "bg-brand-700 text-white"
        : "text-blue-100 hover:bg-brand-600 hover:text-white"
    }`;

  return (
    <nav className="bg-brand-900 text-white shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          <div className="flex items-center gap-2">
            <span className="font-bold text-lg tracking-tight">DISCOUNT UI</span>
            <span className="text-blue-300 text-xs hidden sm:inline">
              Detector-Based Importance Sampling
            </span>
          </div>
          <div className="flex items-center gap-1">
            <NavLink to="/" end className={linkClass}>
              Home
            </NavLink>
            <NavLink to="/upload" className={linkClass}>
              Upload
            </NavLink>
            <NavLink to="/jobs" className={linkClass}>
              Jobs
            </NavLink>
            <NavLink to="/about" className={linkClass}>
              About
            </NavLink>
          </div>
        </div>
      </div>
    </nav>
  );
}
