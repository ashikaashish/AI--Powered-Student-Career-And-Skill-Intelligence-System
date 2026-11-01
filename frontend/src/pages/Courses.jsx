import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Star, CheckCircle2, PlayCircle, Clock, Film, Sparkles, ClipboardCheck, Search, X } from "lucide-react";
import client from "../api/client";
import { Layout, Card, PageHeader, Loading, ProgressBar, Badge } from "../components/Layout";
import { formatDuration } from "../utils/format";

const LEVELS = ["All", "Beginner", "Intermediate", "Advanced"];
const PAGE_SIZE = 24;

export default function Courses() {
  const navigate = useNavigate();
  const [level, setLevel] = useState("All");
  const [courses, setCourses] = useState([]);
  const [recommended, setRecommended] = useState([]);
  const [progressMap, setProgressMap] = useState({}); // course_id -> {status, watch_percent}
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [visible, setVisible] = useState(PAGE_SIZE);

  // Search by title, skill, provider or level. Every word typed must match (so "python beginner" works).
  const filtered = useMemo(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    if (words.length === 0) return courses;
    return courses.filter((c) => {
      const hay = `${c.title} ${c.skill_tag} ${c.provider} ${c.level}`.toLowerCase();
      return words.every((w) => hay.includes(w));
    });
  }, [courses, query]);

  useEffect(() => {
    setLoading(true);
    client
      .get(`/courses?level=${level}`)
      .then((res) => { setCourses(res.data); setError(""); })
      .catch(() => setError("Could not load courses. Make sure the backend is running (python app.py) and restart it after updating."))
      .finally(() => setLoading(false));
    client.get("/courses/recommended").then((res) => setRecommended(res.data.map((c) => c.id))).catch(() => {});
    client.get("/courses/enrolled").then((res) => setProgressMap(res.data)).catch(() => {});
  }, [level]);

  // Enroll, then go straight to the in-platform player.
  const handleEnroll = async (course) => {
    setBusyId(course.id);
    setError("");
    try {
      await client.post(`/courses/${course.id}/enroll`);
      navigate(`/courses/${course.id}/learn`);
    } catch (err) {
      setError(err.response?.data?.error || "Could not enroll. Please try again.");
      setBusyId(null);
    }
  };

  return (
    <Layout>
      <PageHeader
        title="Learning"
        subtitle="Watch YouTube videos for each topic, pass the assessment, and the skill is added to your profile"
      />

      <div className="relative mb-4 max-w-xl">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setVisible(PAGE_SIZE); }}
          placeholder="Search courses by topic, skill or provider (e.g. Python, SQL, Leadership)…"
          className="w-full pl-9 pr-9 py-2.5 rounded-xl border border-slate-200 bg-white text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-200 focus:border-primary-400"
        />
        {query && (
          <button
            onClick={() => { setQuery(""); setVisible(PAGE_SIZE); }}
            aria-label="Clear search"
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
          >
            <X size={16} />
          </button>
        )}
      </div>

      <div className="flex gap-2 mb-3 flex-wrap">
        {LEVELS.map((l) => (
          <button
            key={l}
            onClick={() => { setLevel(l); setVisible(PAGE_SIZE); }}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              level === l ? "bg-primary-600 text-white" : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
            }`}
          >
            {l}
          </button>
        ))}
      </div>

      {!loading && courses.length > 0 && (
        <p className="text-xs text-slate-400 mb-4">
          {query
            ? `${filtered.length} course${filtered.length === 1 ? "" : "s"} match "${query}"`
            : `${courses.length} courses`}
        </p>
      )}

      {error && (
        <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</div>
      )}

      {loading ? (
        <Loading />
      ) : courses.length === 0 ? (
        <Card><p className="text-sm text-slate-500">No courses to show.</p></Card>
      ) : filtered.length === 0 ? (
        <Card><p className="text-sm text-slate-500">No courses match "{query}". Try a different word, like a skill name (Python, SQL, Excel).</p></Card>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {filtered.slice(0, visible).map((c) => {
            const progress = progressMap[c.id];
            const enrolled = !!progress;
            const isCompleted = progress?.status === "completed";
            const watchPercent = progress?.watch_percent || 0;
            const isWatched = progress?.status === "watched";
            const ready = c.question_count > 0;      // topic has an assessment
            const hasVideos = c.lesson_count > 0;

            return (
              <Card key={c.id} className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-primary-50 flex items-center justify-center shrink-0 text-primary-600 font-bold">
                  {c.title[0]}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold text-slate-800 text-sm truncate">{c.title}</h3>
                    {recommended.includes(c.id) && (
                      <span className="text-[10px] font-bold text-primary-600 bg-primary-50 px-1.5 py-0.5 rounded-full shrink-0">
                        For you
                      </span>
                    )}
                    {isCompleted && <Badge tone="teal">Skill earned</Badge>}
                    {isWatched && <Badge tone="amber">Assessment pending</Badge>}
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">{c.provider} · {c.level}</p>
                  <p className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                    <Sparkles size={11} className="text-primary-500" /> Pass the assessment to earn: <span className="font-semibold text-slate-700">{c.skill_tag}</span>
                  </p>
                  <div className="flex items-center gap-3 mt-1 text-xs text-slate-400">
                    <span className="flex items-center gap-1 text-amber-500"><Star size={12} fill="currentColor" /> {c.rating}</span>
                    {hasVideos && (
                      <>
                        <span className="flex items-center gap-1"><Film size={11} /> {c.lesson_count} lesson{c.lesson_count > 1 ? "s" : ""}</span>
                        <span className="flex items-center gap-1"><Clock size={11} /> {formatDuration(c.total_seconds)}</span>
                      </>
                    )}
                  </div>

                  {enrolled && !isCompleted && !isWatched && (
                    <div className="mt-2 max-w-[220px]">
                      <ProgressBar value={watchPercent} />
                      <p className="text-[10px] text-slate-400 mt-0.5">{Math.round(watchPercent)}% watched</p>
                    </div>
                  )}
                </div>

                <div className="flex flex-col gap-1.5 items-end shrink-0">
                  {!ready ? (
                    <span className="text-xs font-semibold text-slate-400 bg-slate-100 px-2.5 py-1.5 rounded-md">Coming soon</span>
                  ) : isWatched ? (
                    <button
                      onClick={() => navigate(`/courses/${c.id}/assessment`)}
                      className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-md bg-amber-500 text-white hover:bg-amber-600"
                    >
                      <ClipboardCheck size={13} /> Take assessment
                    </button>
                  ) : enrolled ? (
                    <button
                      onClick={() => navigate(`/courses/${c.id}/learn`)}
                      className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-md bg-primary-600 text-white hover:bg-primary-700"
                    >
                      {isCompleted ? (
                        <><CheckCircle2 size={13} /> Review</>
                      ) : (
                        <><PlayCircle size={13} /> {watchPercent > 0 ? "Continue" : "Start"}</>
                      )}
                    </button>
                  ) : (
                    <button
                      onClick={() => handleEnroll(c)}
                      disabled={busyId === c.id}
                      className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-md bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-60"
                    >
                      {busyId === c.id ? "Enrolling…" : "Enroll"}
                    </button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {!loading && filtered.length > visible && (
        <div className="flex justify-center mt-5">
          <button
            onClick={() => setVisible((v) => v + PAGE_SIZE)}
            className="px-5 py-2 rounded-full text-sm font-medium bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
          >
            Show more ({filtered.length - visible} left)
          </button>
        </div>
      )}
    </Layout>
  );
}
