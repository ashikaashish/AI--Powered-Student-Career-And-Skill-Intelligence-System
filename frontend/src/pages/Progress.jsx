import { useEffect, useState } from "react";
import { BookOpen, Award, FolderCheck, Gauge, CheckCircle2 } from "lucide-react";
import client from "../api/client";
import { Layout, Card, PageHeader, Loading } from "../components/Layout";

export default function Progress() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    client.get("/progress").then((res) => {
      setData(res.data);
      setLoading(false);
    });
  }, []);

  if (loading || !data) return <Layout><Loading /></Layout>;

  const stats = [
    { label: "Courses Completed", value: data.courses_completed, icon: BookOpen },
    { label: "Skills Learned", value: data.skills_learned, icon: Award },
    { label: "Career Readiness", value: `${data.career_readiness_percent}%`, icon: Gauge },
  ];

  return (
    <Layout>
      <PageHeader title="My Progress" subtitle="Track your learning and career journey" />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
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
          <h3 className="font-bold text-slate-800 mb-4">Recent Achievements</h3>
          {data.recent_achievements.length === 0 ? (
            <p className="text-sm text-slate-400">Complete a course to see it here.</p>
          ) : (
            <div className="space-y-2">
              {data.recent_achievements.map((a, i) => (
                <div key={i} className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-slate-50">
                  <div className="flex items-center gap-2 text-sm text-slate-700">
                    <CheckCircle2 size={16} className="text-teal-600" />
                    Completed "{a.title}"
                  </div>
                  <span className="text-xs text-slate-400">
                    {a.completed_at ? new Date(a.completed_at).toLocaleDateString() : ""}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </Layout>
  );
}
