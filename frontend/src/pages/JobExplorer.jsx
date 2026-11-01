import { useEffect, useState } from "react";
import { Search, DollarSign, TrendingUp, Bot } from "lucide-react";
import client from "../api/client";
import { Layout, Card, PageHeader, Loading } from "../components/Layout";

export default function JobExplorer() {
  const [jobs, setJobs] = useState([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);

  const search = (q) => {
    setLoading(true);
    client.get(`/jobs?q=${encodeURIComponent(q)}`).then((res) => {
      setJobs(res.data);
      if (res.data.length && !selected) setSelected(res.data[0]);
      setLoading(false);
    });
  };

  useEffect(() => {
    search("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSelect = (job) => {
    client.get(`/jobs/${encodeURIComponent(job.title)}`).then((res) => setSelected(res.data));
  };

  const categories = ["All", ...Array.from(new Set(jobs.map((j) => j.category))).sort()];
  const visibleJobs = category === "All" ? jobs : jobs.filter((j) => j.category === category);

  return (
    <Layout>
      <PageHeader title="Job Role Explorer" subtitle="Explore real job roles, drawn from live postings, and their required skills" />

      <div className="relative mb-3">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            search(e.target.value);
          }}
          placeholder="Search job roles..."
          className="w-full rounded-lg border border-slate-200 pl-9 pr-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
      </div>

      <div className="flex flex-wrap gap-2 mb-5">
        {categories.map((c) => (
          <button
            key={c}
            onClick={() => setCategory(c)}
            className={`text-xs font-semibold px-3 py-1.5 rounded-full border transition-colors ${
              category === c
                ? "bg-primary-600 border-primary-600 text-white"
                : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      {loading ? (
        <Loading />
      ) : (
        <div className="grid md:grid-cols-3 gap-6">
          <div className="md:col-span-1 space-y-2">
            {visibleJobs.map((j) => (
              <button
                key={j.title}
                onClick={() => handleSelect(j)}
                className={`w-full text-left px-4 py-3 rounded-2xl border text-sm font-medium transition-colors ${
                  selected?.title === j.title
                    ? "bg-primary-50 border-primary-200 text-primary-700"
                    : "bg-white border-slate-100 text-slate-700 hover:bg-slate-50"
                }`}
              >
                {j.title}
                <span className="block text-xs font-normal text-slate-400 mt-0.5">{j.category}</span>
              </button>
            ))}
            {visibleJobs.length === 0 && (
              <p className="text-sm text-slate-400 px-2">No roles match that search/category.</p>
            )}
          </div>

          <Card className="md:col-span-2 h-fit">
            {selected ? (
              <>
                <h2 className="text-lg font-bold text-slate-800">{selected.title}</h2>
                <p className="text-xs font-semibold text-primary-600 uppercase tracking-wide mt-1">Overview</p>
                <p className="text-sm text-slate-600 mt-1.5">{selected.description}</p>

                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mt-5 mb-2">Required Skills</p>
                <div className="flex flex-wrap gap-2">
                  {(Array.isArray(selected.required_skills)
                    ? selected.required_skills
                    : selected.required_skills.split(",")
                  ).map((s) => (
                    <span key={s} className="text-xs bg-slate-100 text-slate-700 px-2.5 py-1 rounded-full">
                      {s.trim()}
                    </span>
                  ))}
                </div>

                <div className="flex gap-6 mt-6 pt-5 border-t border-slate-100">
                  {selected.avg_salary_lpa && (
                    <div className="flex items-center gap-2 text-sm text-slate-600">
                      <DollarSign size={16} className="text-primary-600" />
                      Average Salary: <span className="font-semibold">₹{selected.avg_salary_lpa} LPA</span>
                    </div>
                  )}
                  <div className="flex items-center gap-2 text-sm text-slate-600">
                    <TrendingUp size={16} className="text-teal-600" />
                    Job Growth: <span className="font-semibold">{selected.job_growth}</span>
                  </div>
                </div>

                {selected.automation_risk != null && (
                  <div className="mt-4 pt-4 border-t border-slate-100">
                    <AutomationRisk risk={selected.automation_risk} />
                  </div>
                )}
              </>
            ) : (
              <p className="text-sm text-slate-400">Select a role to see details.</p>
            )}
          </Card>
        </div>
      )}
    </Layout>
  );
}

function riskColors(risk) {
  if (risk >= 65) return { bg: "bg-red-50", border: "border-red-100", text: "text-red-700", bar: "bg-red-500", label: "High" };
  if (risk >= 40) return { bg: "bg-amber-50", border: "border-amber-100", text: "text-amber-700", bar: "bg-amber-500", label: "Moderate" };
  return { bg: "bg-teal-50", border: "border-teal-100", text: "text-teal-700", bar: "bg-teal-500", label: "Low" };
}

function AutomationRisk({ risk }) {
  const c = riskColors(risk);
  return (
    <div className={`rounded-lg border ${c.border} ${c.bg} px-3 py-2.5`}>
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-600">
          <Bot size={13} className={c.text} /> AI Automation Risk
        </span>
        <span className={`text-xs font-bold ${c.text}`}>{risk}% · {c.label}</span>
      </div>
      <div className="w-full h-1.5 rounded-full bg-white/70 overflow-hidden">
        <div className={`h-full rounded-full ${c.bar}`} style={{ width: `${risk}%` }} />
      </div>
      <p className="text-[11px] text-slate-500 mt-1.5">
        Estimated chance AI/automation significantly reshapes this role's tasks in the coming years.
      </p>
    </div>
  );
}
