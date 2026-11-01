import Sidebar from "./Sidebar";

export function Layout({ children }) {
  return (
    <div className="min-h-screen bg-[#f1f5f9] flex">
      <Sidebar />
      <div className="flex-1 ml-64 flex flex-col min-w-0 min-h-screen">
        <main className="flex-1 p-6 sm:p-8 max-w-7xl w-full mx-auto">{children}</main>
      </div>
    </div>
  );
}

export function Card({ children, className = "" }) {
  return (
    <div className={`bg-white rounded-3xl border border-slate-200 shadow-sm p-6 ${className}`}>
      {children}
    </div>
  );
}

export function StatCard({ label, value, sub, accent = "primary" }) {
  const accentMap = {
    primary: "text-primary-700 bg-primary-50",
    teal: "text-teal-600 bg-teal-50",
    amber: "text-amber-600 bg-amber-50",
  };
  return (
    <Card className="flex flex-col justify-between">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className={`text-3xl font-extrabold mt-2 ${accentMap[accent].split(" ")[0]}`}>{value}</p>
      {sub && <p className="text-[11px] text-slate-400 mt-1">{sub}</p>}
    </Card>
  );
}

export function PageHeader({ title, subtitle, action }) {
  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800 tracking-tight">{title}</h1>
        {subtitle && <p className="text-slate-500 text-sm mt-1 font-medium">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Loading() {
  return (
    <div className="flex items-center justify-center py-24">
      <div className="w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin" />
    </div>
  );
}

export function ProgressBar({ value, className = "" }) {
  return (
    <div className={`progress-track h-2.5 w-full ${className}`}>
      <div className="progress-fill h-full transition-all" style={{ width: `${value}%` }} />
    </div>
  );
}

// A bold gradient CTA banner, used for "recommended next step" style call-outs.
export function GradientBanner({ eyebrow, title, action }) {
  return (
    <div className="gradient-banner rounded-3xl p-6 text-white shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border border-primary-900/40">
      <div className="space-y-1">
        {eyebrow && (
          <div className="inline-flex items-center gap-1.5 text-xs font-bold text-primary-300 uppercase tracking-wider">
            {eyebrow}
          </div>
        )}
        <p className="text-sm sm:text-base font-semibold text-slate-100">{title}</p>
      </div>
      {action}
    </div>
  );
}

// Small pill/badge used for match scores, statuses, etc.
export function Badge({ children, tone = "primary", className = "" }) {
  const tones = {
    primary: "bg-primary-50 text-primary-700 border-primary-200",
    teal: "bg-teal-50 text-teal-700 border-teal-200",
    amber: "bg-amber-50 text-amber-700 border-amber-200",
    slate: "bg-slate-100 text-slate-600 border-slate-200",
    red: "bg-red-50 text-red-600 border-red-100",
  };
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full border ${tones[tone]} ${className}`}>
      {children}
    </span>
  );
}
