import { useEffect, useState } from "react";
import { Building2, MapPin, ExternalLink, RefreshCw, CheckCircle2, Wifi, Clock } from "lucide-react";
import client from "../api/client";
import { Card, Loading } from "./Layout";

function matchTone(p) {
  if (p >= 67) return "bg-teal-50 text-teal-700 border-teal-100";
  if (p >= 34) return "bg-amber-50 text-amber-700 border-amber-100";
  return "bg-slate-50 text-slate-600 border-slate-200";
}

export default function LiveJobs() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [scope, setScope] = useState("india");
  const [location, setLocation] = useState(null);   // null = use the city on the profile
  const [locInput, setLocInput] = useState("");

  const load = (opts = {}) => {
    setLoading(true);
    setError("");
    const params = { scope: opts.scope ?? scope };
    const loc = opts.location !== undefined ? opts.location : location;
    if (loc !== null) params.location = loc;
    client
      .get("/jobs/for-me", { params })
      .then((res) => {
        setData(res.data);
        if (location === null && opts.location === undefined) setLocInput(res.data.location || "");
      })
      .catch(() => setError("Could not load job openings. Please try again."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const jobs = data?.jobs || [];

  return (
    <div>
      <Card className="mb-5">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
          Matched against your profile skills
        </p>
        <div className="flex flex-wrap gap-2">
          {(data?.skills_used || []).map((s) => (
            <span key={s} className="text-xs bg-primary-50 text-primary-700 border border-primary-100 px-2.5 py-1 rounded-full font-medium">
              {s}
            </span>
          ))}
          {data && data.skills_used.length === 0 && (
            <p className="text-sm text-slate-500">
              No technical skills on your profile yet. Add some on the Profile page and openings will appear here.
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3 mt-4 pt-4 border-t border-slate-100">
          <input
            value={locInput}
            onChange={(e) => setLocInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (setLocation(locInput), load({ location: locInput }))}
            placeholder="City (e.g. Mangaluru, Bengaluru)"
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <select
            value={scope}
            onChange={(e) => { setScope(e.target.value); load({ scope: e.target.value }); }}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="india">India + remote roles open to India</option>
            <option value="all">All locations worldwide</option>
          </select>
          <button
            onClick={() => { setLocation(locInput); load({ location: locInput }); }}
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-white bg-primary-600 hover:bg-primary-700 px-4 py-2 rounded-lg"
          >
            <RefreshCw size={14} /> Search
          </button>
        </div>
      </Card>

      {loading && <Loading />}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && data?.note && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2 mb-4">{data.note}</p>
      )}

      {!loading && data && (
        <>
          <p className="text-sm text-slate-500 mb-3">
            {jobs.length} current opening{jobs.length === 1 ? "" : "s"} found
            {data.sources.length > 0 && <> · via {data.sources.join(", ")}</>}
          </p>

          <div className="grid lg:grid-cols-2 gap-4">
            {jobs.map((j) => (
              <Card key={j.id} className="!p-5 flex flex-col">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="font-bold text-slate-800 leading-snug">{j.title}</h3>
                    <p className="flex items-center gap-1.5 text-sm font-semibold text-primary-700 mt-1">
                      <Building2 size={14} /> {j.company}
                    </p>
                  </div>
                  <span className={`shrink-0 text-xs font-bold px-2.5 py-1 rounded-full border ${matchTone(j.match_percent)}`}>
                    {j.match_percent}% match
                  </span>
                </div>

                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 mt-2">
                  {j.location && <span className="flex items-center gap-1"><MapPin size={12} /> {j.location}</span>}
                  {j.remote && <span className="flex items-center gap-1 text-teal-600"><Wifi size={12} /> Remote</span>}
                  {j.posted && <span className="flex items-center gap-1"><Clock size={12} /> {j.posted}</span>}
                  {j.salary && <span className="font-semibold text-slate-600">{j.salary}</span>}
                </div>

                {j.summary && <p className="text-xs text-slate-500 mt-3 line-clamp-3">{j.summary}</p>}

                <div className="flex flex-wrap gap-1.5 mt-3">
                  {j.matched_skills.map((s) => (
                    <span key={s} className="inline-flex items-center gap-1 text-[11px] bg-teal-50 text-teal-700 px-2 py-0.5 rounded-full">
                      <CheckCircle2 size={11} /> {s}
                    </span>
                  ))}
                  {j.missing_skills.slice(0, 3).map((s) => (
                    <span key={s} className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full">
                      to learn: {s}
                    </span>
                  ))}
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-[11px] text-slate-400">via {j.source}</span>
                  <a
                    href={j.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary-600 hover:text-primary-700"
                  >
                    View &amp; apply <ExternalLink size={13} />
                  </a>
                </div>
              </Card>
            ))}
          </div>

          {jobs.length === 0 && !data.note && (
            <p className="text-sm text-slate-400">
              No openings matched right now. Try "All locations" or add more skills to your profile.
            </p>
          )}
        </>
      )}
    </div>
  );
}