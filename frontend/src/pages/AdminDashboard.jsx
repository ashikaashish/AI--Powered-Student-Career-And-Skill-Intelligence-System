import { useEffect, useState } from "react";
import { Users, Award, BookOpen, Briefcase } from "lucide-react";
import client from "../api/client";
import { Layout, Card, PageHeader, Loading } from "../components/Layout";

// "2026-10-29" -> "29 Oct"
function shortDate(iso) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

export default function AdminDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    client.get("/admin/dashboard").then((res) => {
      setData(res.data);
      setLoading(false);
    });
  }, []);

  if (loading || !data) return <Layout><Loading /></Layout>;

  const stats = [
    { label: "Total Students", value: data.total_students, icon: Users },
    { label: "Total Skills", value: data.total_skills, icon: Award },
    { label: "Total Courses", value: data.total_courses, icon: BookOpen },
    { label: "Total Careers", value: data.total_careers, icon: Briefcase },
  ];

  const registrations = data.registrations_over_time;
  const maxCount = Math.max(1, ...registrations.map((r) => r.count));
  const maxSkillCount = Math.max(1, ...data.top_skills.map((s) => s.count));
  const totalRecent = registrations.reduce((sum, r) => sum + r.count, 0);
  const CHART_HEIGHT = 160; // px

  return (
    <Layout>
      <PageHeader title="Admin Dashboard" subtitle="Overview of the system" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {stats.map((s) => (
          <Card key={s.label}>
            <div className="w-9 h-9 rounded-lg bg-primary-50 flex items-center justify-center mb-3">
              <s.icon size={18} className="text-primary-600" />
            </div>
            <p className="text-2xl font-bold text-slate-800">{s.value}</p>
            <p className="text-xs text-slate-400 mt-1">{s.label}</p>
          </Card>
        ))}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <Card>
          <div className="flex items-baseline justify-between mb-4">
            <h3 className="font-bold text-slate-800">Students Registered Over Time</h3>
            <span className="text-xs text-slate-400">
              Last 14 days · {totalRecent} new
            </span>
          </div>

          {registrations.length === 0 ? (
            <p className="text-sm text-slate-400">No registration data yet.</p>
          ) : (
            <div className="flex gap-2">
              {/* Y-axis labels */}
              <div
                className="flex flex-col justify-between text-[10px] text-slate-400 text-right pr-1"
                style={{ height: CHART_HEIGHT }}
              >
                <span>{maxCount}</span>
                <span>0</span>
              </div>

              {/* Bars */}
              <div className="flex-1 overflow-x-auto">
                <div
                  className="flex items-end gap-2 border-b border-slate-200"
                  style={{ height: CHART_HEIGHT }}
                >
                  {registrations.map((r) => (
                    <div
                      key={r.date}
                      className="flex-1 min-w-[18px] h-full flex flex-col justify-end items-center group"
                      title={`${r.date}: ${r.count} student${r.count === 1 ? "" : "s"}`}
                    >
                      {r.count > 0 && (
                        <span className="text-[10px] font-semibold text-slate-600 mb-1">
                          {r.count}
                        </span>
                      )}
                      <div
                        className={`w-full rounded-t-md transition-all ${
                          r.count > 0
                            ? "bg-primary-500 group-hover:bg-primary-600"
                            : "bg-slate-200"
                        }`}
                        style={{
                          height:
                            r.count > 0
                              ? `${(r.count / maxCount) * (CHART_HEIGHT - 20)}px`
                              : "3px",
                        }}
                      />
                    </div>
                  ))}
                </div>

                {/* X-axis labels */}
                <div className="flex gap-2 mt-1">
                  {registrations.map((r, i) => (
                    <span
                      key={r.date}
                      className="flex-1 min-w-[18px] text-center text-[9px] text-slate-400"
                    >
                      {i % 2 === 0 ? shortDate(r.date) : ""}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </Card>

        <Card>
          <h3 className="font-bold text-slate-800 mb-4">Top Skills Among Students</h3>
          <div className="space-y-3">
            {data.top_skills.map((s) => (
              <div key={s.skill_name}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-600">{s.skill_name}</span>
                  <span className="font-semibold text-slate-500">{s.count}</span>
                </div>
                <div className="progress-track h-2">
                  <div
                    className="progress-fill h-full"
                    style={{ width: `${(s.count / maxSkillCount) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </Layout>
  );
}