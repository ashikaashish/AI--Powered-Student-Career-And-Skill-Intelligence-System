import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CheckCircle2, AlertCircle, XCircle } from "lucide-react";
import client from "../api/client";
import { Layout, Card, PageHeader, Loading, ProgressBar } from "../components/Layout";

export default function SkillGap() {
  const [careers, setCareers] = useState([]);
  const [searchParams] = useSearchParams();
  const [selected, setSelected] = useState(searchParams.get("career") || "");
  const [gap, setGap] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    client.get("/jobs").then((res) => setCareers(res.data));
  }, []);

  useEffect(() => {
    setLoading(true);
    const url = selected ? `/skills/gap?career=${encodeURIComponent(selected)}` : "/skills/gap";
    client
      .get(url)
      .then((res) => {
        setGap(res.data);
        if (!selected) setSelected(res.data.target_career);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selected]);

  return (
    <Layout>
      <PageHeader
        title="Skill Gap Analysis"
        subtitle="Compare your skills with required skills"
        action={
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            {careers.map((c) => (
              <option key={c.title} value={c.title}>
                {c.title}
              </option>
            ))}
          </select>
        }
      />

      {loading || !gap ? (
        <Loading />
      ) : (
        <>
          <div className="grid md:grid-cols-2 gap-6 mb-6">
            <Card>
              <h3 className="font-bold text-slate-800 mb-4">Your Skills</h3>
              <div className="space-y-2">
                {[...gap.matched, ...gap.partial].length === 0 && (
                  <p className="text-sm text-slate-400">No matching skills yet.</p>
                )}
                {[...gap.matched, ...gap.partial].map((s) => (
                  <div key={s.skill} className="flex items-center justify-between px-3 py-2 rounded-lg bg-slate-50">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 size={16} className="text-teal-600" />
                      <span className="text-sm text-slate-700">{s.skill}</span>
                    </div>
                    <span className="text-xs font-semibold text-slate-500">{s.level}</span>
                  </div>
                ))}
              </div>
            </Card>

            <Card>
              <h3 className="font-bold text-slate-800 mb-4">Skills You Need to Learn</h3>
              <div className="space-y-2">
                {gap.missing.length === 0 && (
                  <p className="text-sm text-slate-400">You have all required skills! 🎉</p>
                )}
                {gap.missing.map((s) => (
                  <div key={s.skill} className="flex items-center justify-between px-3 py-2 rounded-lg bg-red-50">
                    <div className="flex items-center gap-2">
                      <XCircle size={16} className="text-red-500" />
                      <span className="text-sm text-slate-700">{s.skill}</span>
                    </div>
                    <span className="text-xs font-semibold text-red-500">Missing</span>
                  </div>
                ))}
                {gap.partial.map((s) => (
                  <div key={s.skill} className="flex items-center justify-between px-3 py-2 rounded-lg bg-amber-50">
                    <div className="flex items-center gap-2">
                      <AlertCircle size={16} className="text-amber-500" />
                      <span className="text-sm text-slate-700">{s.skill}</span>
                    </div>
                    <span className="text-xs font-semibold text-amber-600">Needs Work</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <Card>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-bold text-slate-800">Overall Skill Readiness for {gap.target_career}</h3>
              <span className="text-sm font-bold text-primary-600">{gap.overall_skill_percent}%</span>
            </div>
            <ProgressBar value={gap.overall_skill_percent} />
          </Card>
        </>
      )}
    </Layout>
  );
}
