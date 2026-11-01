import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, TrendingUp, DollarSign, Bot, GraduationCap } from "lucide-react";
import client from "../api/client";
import { Layout, Card, PageHeader, Loading } from "../components/Layout";

export default function Recommendations() {
  const [recs, setRecs] = useState([]);
  const [message, setMessage] = useState("");
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    client
      .get("/recommend?top_n=6")
      .then((res) => {
        setRecs(res.data.recommendations);
        setMessage(res.data.message || "");
        setSummary(res.data.skills_summary || null);
      })
      .catch((err) => setError(err.response?.data?.error || "Could not load recommendations"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Layout>
      <PageHeader title="AI Career Recommendations" subtitle="Top career paths based on your profile" />

      {loading ? (
        <Loading />
      ) : error ? (
        <Card>
          <p className="text-sm text-slate-500">{error}</p>
        </Card>
      ) : (
        <div>
          {message && (
            <div className="mb-4 text-sm text-primary-700 bg-primary-50 border border-primary-100 rounded-lg px-3 py-2">
              {message}
            </div>
          )}
          {summary && summary.total > 0 && (
            <div className="mb-4 text-sm bg-white border border-slate-200 rounded-2xl px-4 py-3 flex flex-wrap items-center gap-x-4 gap-y-1">
              <span className="text-slate-600">
                Matched against the <b className="text-slate-800">{summary.total} skills</b> on your profile.
              </span>
              {summary.from_courses.length > 0 && (
                <span className="flex items-center gap-1.5 text-teal-700 font-medium">
                  <GraduationCap size={15} />
                  Earned from courses: {summary.from_courses.map((c) => c.skill_name).join(", ")}
                </span>
              )}
              <Link to="/courses" className="ml-auto text-primary-600 font-semibold hover:underline">
                Learn another skill →
              </Link>
            </div>
          )}
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {recs.map((r, i) => (
            <Card key={r.title} className="flex flex-col">
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-lg bg-primary-50 flex items-center justify-center">
                  <TrendingUp size={18} className="text-primary-600" />
                </div>
                <span className="text-xs font-bold text-teal-700 bg-teal-50 px-2 py-1 rounded-full">
                  {r.match_score}% Match
                </span>
              </div>
              <h3 className="font-bold text-slate-800">{r.title}</h3>
              <p className="text-sm text-slate-500 mt-1.5 flex-1">{r.description}</p>

              <div className="mt-4 pt-4 border-t border-slate-100 space-y-1.5 text-xs text-slate-500">
                <div className="flex items-center gap-1.5">
                  <DollarSign size={13} />
                  {r.avg_salary_lpa ? `${r.avg_salary_lpa} LPA average` : "Salary data not available"}
                </div>
                <div className="flex items-center gap-1.5">
                  <TrendingUp size={13} /> {r.job_growth} demand growth
                </div>
                {r.automation_risk != null && (
                  <div className="flex items-center gap-1.5">
                    <Bot size={13} />
                    <span className={riskTextColor(r.automation_risk)}>
                      {r.automation_risk}% AI automation risk
                    </span>
                  </div>
                )}
              </div>

              {r.matched_skills && (
                <div className="mt-3 space-y-2">
                  {r.matched_skills.length > 0 && (
                    <div>
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">Skills you have</p>
                      <div className="flex flex-wrap gap-1">
                        {r.matched_skills.map((k) => (
                          <span key={k} className="text-[11px] bg-teal-50 text-teal-700 border border-teal-100 rounded-full px-2 py-0.5">{k}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {r.missing_skills.length > 0 && (
                    <div>
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">Still to learn</p>
                      <div className="flex flex-wrap gap-1">
                        {r.missing_skills.slice(0, 6).map((k) => (
                          <Link key={k} to={`/courses`} className="text-[11px] bg-slate-100 text-slate-600 rounded-full px-2 py-0.5 hover:bg-primary-50 hover:text-primary-700">{k}</Link>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {i === 0 && (
                <div className="mt-3 bg-primary-50 rounded-lg p-3 text-xs text-primary-700 space-y-1">
                  <p className="font-semibold flex items-center gap-1"><CheckCircle2 size={13}/> Why this career?</p>
                  <p>Your skills match well with this role's requirements and it has strong salary potential.</p>
                </div>
              )}
            </Card>
          ))}
          </div>
        </div>
      )}
    </Layout>
  );
}

function riskTextColor(risk) {
  if (risk >= 65) return "text-red-600 font-semibold";
  if (risk >= 40) return "text-amber-600 font-semibold";
  return "text-teal-600 font-semibold";
}
