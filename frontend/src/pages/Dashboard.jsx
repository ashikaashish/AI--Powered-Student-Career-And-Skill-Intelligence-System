import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Target, Award, TrendingDown, Briefcase, ArrowRight, Sparkles } from "lucide-react";
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from "recharts";
import client from "../api/client";
import { useAuth } from "../context/AuthContext";
import { Layout, Card, PageHeader, Loading, GradientBanner } from "../components/Layout";

export default function Dashboard() {
  const { user } = useAuth();
  const [summary, setSummary] = useState(null);
  const [gap, setGap] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      client.get("/recommend/dashboard-summary"),
      client.get("/skills/gap").catch(() => ({ data: null })),
    ])
      .then(([summaryRes, gapRes]) => {
        setSummary(summaryRes.data);
        setGap(gapRes.data);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Layout><Loading /></Layout>;

  const colorClasses = {
    primary: { bg: "bg-primary-50", text: "text-primary-700" },
    teal: { bg: "bg-teal-50", text: "text-teal-600" },
    amber: { bg: "bg-amber-50", text: "text-amber-600" },
  };

  const stats = [
    { label: "Career Match Score", value: `${summary?.career_match_score ?? 0}%`, icon: Target, sub: "Great Match", color: "primary" },
    { label: "Skills Acquired", value: summary?.skills_acquired ?? 0, icon: Award, sub: "Verified skills", color: "teal" },
    { label: "Skills Gap", value: summary?.skills_gap ?? 0, icon: TrendingDown, sub: "To target mastery", color: "amber" },
    { label: "Career Options", value: summary?.career_options ?? 0, icon: Briefcase, sub: "Viable pathways", color: "primary" },
  ];

  const donutData = gap
    ? [
        { name: "Matched", value: gap.matched.length, color: "#2e5bdf" },
        { name: "Partial", value: gap.partial.length, color: "#699bf2" },
        { name: "Missing", value: gap.missing.length, color: "#e2e8f0" },
      ]
    : [];
  const totalSkills = gap ? gap.matched.length + gap.partial.length + gap.missing.length : 0;

  return (
    <Layout>
      <PageHeader
        title={`Welcome back, ${user?.name?.split(" ")[0] || "there"}!`}
        subtitle={new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {stats.map((s) => (
          <Card key={s.label} className="flex flex-col justify-between rounded-3xl">
            <div className="flex items-center justify-between mb-1">
              <p className="text-xs font-semibold text-slate-500">{s.label}</p>
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${colorClasses[s.color].bg}`}>
                <s.icon size={15} className={colorClasses[s.color].text} />
              </div>
            </div>
            <span className={`text-3xl font-extrabold ${colorClasses[s.color].text}`}>{s.value}</span>
            <p className="text-[11px] text-slate-400 font-medium mt-1">{s.sub}</p>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Top Career Suggestions */}
        <Card className="lg:col-span-7 flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center mb-5">
              <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wide">Top Career Suggestions</h2>
              <Link to="/recommendations" className="text-xs font-bold text-primary-600 hover:text-primary-700 flex items-center gap-1">
                <span>View All</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            <div className="space-y-3">
              {summary?.top_suggestions?.length ? (
                summary.top_suggestions.map((item, idx) => (
                  <Link
                    key={item.title}
                    to="/recommendations"
                    className="p-4 rounded-2xl bg-slate-50 hover:bg-primary-50/50 border border-slate-200/80 hover:border-primary-300 flex items-center justify-between transition group"
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-6 h-6 rounded-full bg-primary-100 text-primary-700 text-xs font-bold flex items-center justify-center">
                        {idx + 1}
                      </span>
                      <span className="text-xs font-bold text-slate-800 group-hover:text-primary-700 transition">
                        {item.title}
                      </span>
                    </div>
                    <span className="px-3 py-1 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-full text-xs font-bold">
                      {item.match_score}%
                    </span>
                  </Link>
                ))
              ) : (
                <p className="text-sm text-slate-400">Add skills to your profile to get suggestions.</p>
              )}
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-slate-100 flex justify-end">
            <Link
              to="/recommendations"
              className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-semibold shadow-sm transition"
            >
              View Full Recommendations
            </Link>
          </div>
        </Card>

        {/* Skill Gap Donut */}
        <Card className="lg:col-span-5 flex flex-col items-center justify-between text-center">
          <div className="w-full text-left">
            <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wide">Skill Gap Overview</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              {gap ? `Competency for ${gap.target_career}` : "Competency Breakdown"}
            </p>
          </div>

          {gap ? (
            <>
              <div className="relative w-44 h-44 my-2">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={donutData} cx="50%" cy="50%" innerRadius={55} outerRadius={75} paddingAngle={4} dataKey="value">
                      {donutData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                  <span className="text-[10px] uppercase font-bold text-slate-400">Total Skills</span>
                  <span className="text-2xl font-black text-slate-800">{totalSkills}</span>
                </div>
              </div>

              <div className="flex justify-center gap-4 text-xs font-medium w-full pt-2">
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-primary-600" />
                  <span className="text-slate-600">Matched ({gap.matched.length})</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-primary-300" />
                  <span className="text-slate-600">Partial ({gap.partial.length})</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-slate-200" />
                  <span className="text-slate-600">Missing ({gap.missing.length})</span>
                </div>
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-400 py-10">No skill data yet.</p>
          )}
        </Card>
      </div>

      {/* Recommended Next Step */}
      <div className="mt-6">
        <GradientBanner
          eyebrow={
            <>
              <Sparkles className="w-3.5 h-3.5" />
              <span>Recommended Next Step</span>
            </>
          }
          title={
            gap?.missing?.length
              ? `Improve your ${gap.missing.slice(0, 2).map((m) => m.skill).join(" and ")} skills`
              : "Keep building your profile to unlock more insights"
          }
          action={
            <Link
              to="/courses"
              className="px-5 py-2.5 bg-primary-500 hover:bg-primary-600 active:scale-95 text-white rounded-xl text-xs font-bold shadow-lg shadow-primary-500/30 flex items-center gap-2 transition whitespace-nowrap"
            >
              <span>Go to Learning</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          }
        />
      </div>
    </Layout>
  );
}
