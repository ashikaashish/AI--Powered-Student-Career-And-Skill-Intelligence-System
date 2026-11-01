import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  User,
  BarChart3,
  Sparkles,
  BookOpen,
  Briefcase,
  MessageSquare,
  TrendingUp,
  LogOut,
  ShieldCheck,
  UserCheck,
  Compass,
  BrainCircuit,
  Users,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

const studentLinks = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/profile", label: "Profile", icon: User },
  { to: "/aptitude-quiz", label: "Aptitude Test", icon: Compass },
  { to: "/skill-gap", label: "Skill Gap", icon: BarChart3 },
  { to: "/recommendations", label: "AI Careers", icon: Sparkles },
  { to: "/courses", label: "Learning", icon: BookOpen },
  { to: "/jobs", label: "Job Explorer", icon: Briefcase },
  { to: "/chatbot", label: "AI Assistant", icon: MessageSquare },
  { to: "/progress", label: "Progress", icon: TrendingUp },
];

const adminLinks = [
  { to: "/admin", label: "Overview", icon: BarChart3 },
  { to: "/admin/students", label: "Students", icon: Users },
  { to: "/admin/courses", label: "Courses & Skills", icon: BookOpen },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";
  const links = isAdmin ? adminLinks : studentLinks;

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <aside className="w-64 bg-[#14203e] text-slate-300 flex flex-col h-screen fixed left-0 top-0 border-r border-slate-800 shadow-xl select-none z-30">
      {/* Brand header */}
      <div className="p-5 border-b border-slate-800/80 flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-primary-600 to-indigo-500 flex items-center justify-center text-white shadow-lg shadow-primary-500/25">
          <BrainCircuit className="w-6 h-6" />
        </div>
        <div>
          <h1 className="font-bold text-white tracking-wide text-sm leading-tight">CareerAI</h1>
          <p className="text-[11px] text-slate-400 font-medium">Career Intelligence Platform</p>
        </div>
      </div>

      {/* Role badge */}
      <div className="px-4 pt-4 pb-2">
        <div
          className={`flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg text-xs font-semibold border ${
            isAdmin
              ? "bg-indigo-600/20 text-indigo-300 border-indigo-500/30"
              : "bg-primary-600/20 text-primary-300 border-primary-500/30"
          }`}
        >
          {isAdmin ? <ShieldCheck className="w-3.5 h-3.5" /> : <UserCheck className="w-3.5 h-3.5" />}
          <span>{isAdmin ? "Admin Account" : "Student Account"}</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
        <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">
          {isAdmin ? "Administration Suite" : "Student Intelligence"}
        </div>
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end
            className={({ isActive }) =>
              `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                isActive
                  ? "bg-primary-600/20 text-primary-400 border border-primary-500/30 shadow-sm shadow-primary-900/30 font-semibold"
                  : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60"
              }`
            }
          >
            <Icon className="w-4 h-4" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* User footer */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-900/40">
        <div className="flex items-center justify-between px-1 py-1">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-8 h-8 rounded-full bg-primary-600/30 border border-primary-500/40 flex items-center justify-center text-primary-300 font-bold text-xs shrink-0">
              {(user?.name || "U")[0].toUpperCase()}
            </div>
            <div className="overflow-hidden">
              <p className="text-xs font-semibold text-white truncate">{user?.name || "User"}</p>
              <p className="text-[10px] text-slate-400 truncate capitalize">{user?.role || "student"}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            title="Log Out"
            className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
