import { useEffect, useState } from "react";
import { Trash2, Plus, RefreshCw, Film, X, Clock, ClipboardCheck } from "lucide-react";
import client from "../api/client";
import { Layout, Card, PageHeader, Loading, Badge } from "../components/Layout";
import { formatClock, formatDuration } from "../utils/format";

const inputCls = "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500";
const EMPTY_COURSE = { title: "", provider: "YouTube", level: "Beginner", skill_tag: "", rating: 4.5 };

export default function AdminCourses() {
  const [tab, setTab] = useState("courses");
  const [courses, setCourses] = useState([]);
  const [skills, setSkills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newSkill, setNewSkill] = useState({ skill_name: "", category: "technical" });
  const [newCourse, setNewCourse] = useState(EMPTY_COURSE);
  const [selectedId, setSelectedId] = useState(null);
  const [lessons, setLessons] = useState([]);
  const [msg, setMsg] = useState({ type: "", text: "" });
  const [busy, setBusy] = useState(false);

  const load = () =>
    Promise.all([client.get("/admin/courses"), client.get("/admin/skills")]).then(([c, s]) => {
      setCourses(c.data);
      setSkills(s.data);
      setLoading(false);
    });

  const loadLessons = (courseId) =>
    client.get(`/admin/courses/${courseId}/lessons`).then((res) => setLessons(res.data));

  useEffect(() => { load(); }, []);
  useEffect(() => { if (selectedId) loadLessons(selectedId); else setLessons([]); }, [selectedId]);

  const selected = courses.find((c) => c.id === selectedId) || null;

  const addCourse = async (e) => {
    e.preventDefault();
    try {
      const res = await client.post("/admin/courses", newCourse);
      setNewCourse(EMPTY_COURSE);
      await load();
      setSelectedId(res.data.id);
      setMsg({ type: "ok", text: "Course created. Videos are found on YouTube automatically when the first student opens it." });
    } catch (err) {
      setMsg({ type: "err", text: err.response?.data?.error || "Could not add course" });
    }
  };

  const deleteCourse = async (id) => {
    if (!window.confirm("Delete this course?")) return;
    await client.delete(`/admin/courses/${id}`);
    if (selectedId === id) setSelectedId(null);
    load();
  };

  const refreshVideos = async () => {
    setBusy(true);
    setMsg({ type: "", text: "" });
    try {
      const res = await client.post(`/admin/courses/${selectedId}/refresh-videos`);
      setMsg({ type: "ok", text: res.data.message });
      await Promise.all([loadLessons(selectedId), load()]);
    } catch (err) {
      setMsg({ type: "err", text: err.response?.data?.error || "Could not search YouTube" });
    } finally { setBusy(false); }
  };

  const deleteLesson = async (id) => {
    if (!window.confirm("Remove this lesson?")) return;
    await client.delete(`/admin/lessons/${id}`);
    await Promise.all([loadLessons(selectedId), load()]);
  };

  const addSkill = async (e) => {
    e.preventDefault();
    await client.post("/admin/skills", newSkill);
    setNewSkill({ skill_name: "", category: "technical" });
    load();
  };

  if (loading) return <Layout><Loading /></Layout>;

  return (
    <Layout>
      <PageHeader title="Manage Courses / Skills" subtitle="Each course is a skill topic. Its videos are found on YouTube automatically and students pass an assessment to earn the skill." />

      <div className="flex gap-2 mb-5">
        {["courses", "skills"].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium capitalize transition-colors ${
              tab === t ? "bg-primary-600 text-white" : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
            }`}
          >
            Manage {t}
          </button>
        ))}
      </div>

      {msg.text && (
        <div className={`mb-4 text-sm rounded-lg px-3 py-2 border ${msg.type === "ok" ? "text-teal-700 bg-teal-50 border-teal-100" : "text-red-600 bg-red-50 border-red-100"}`}>
          {msg.text}
        </div>
      )}

      {tab === "courses" ? (
        <div className="grid md:grid-cols-3 gap-6">
          {/* ---------- left: new course + lesson manager ---------- */}
          <div className="md:col-span-1 space-y-5 h-fit">
            <Card>
              <h3 className="font-bold text-slate-800 mb-3 text-sm">Add a course</h3>
              <form onSubmit={addCourse} className="space-y-2">
                <input required placeholder="Title" value={newCourse.title} onChange={(e) => setNewCourse({ ...newCourse, title: e.target.value })} className={inputCls} />
                <input placeholder="Provider (set automatically from YouTube)" value={newCourse.provider} onChange={(e) => setNewCourse({ ...newCourse, provider: e.target.value })} className={inputCls} />
                <select value={newCourse.level} onChange={(e) => setNewCourse({ ...newCourse, level: e.target.value })} className={inputCls}>
                  <option>Beginner</option><option>Intermediate</option><option>Advanced</option>
                </select>
                <input required list="skill-options" placeholder="Skill learners earn (e.g. Python)" value={newCourse.skill_tag} onChange={(e) => setNewCourse({ ...newCourse, skill_tag: e.target.value })} className={inputCls} />
                <datalist id="skill-options">{skills.map((s) => <option key={s.skill_name} value={s.skill_name} />)}</datalist>
                <button type="submit" className="w-full flex items-center justify-center gap-1.5 bg-primary-600 hover:bg-primary-700 text-white text-sm font-semibold py-2 rounded-lg">
                  <Plus size={14} /> Add Course
                </button>
              </form>
            </Card>

            {selected && (
              <Card>
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="min-w-0">
                    <h3 className="font-bold text-slate-800 text-sm flex items-center gap-1.5"><Film size={15} className="text-primary-600" /> Lessons</h3>
                    <p className="text-xs text-slate-400 mt-0.5 truncate">{selected.title}</p>
                  </div>
                  <button onClick={() => setSelectedId(null)} className="text-slate-300 hover:text-slate-500"><X size={16} /></button>
                </div>

                {lessons.length === 0 ? (
                  <p className="text-xs text-slate-400 mb-3">No videos saved yet. They are fetched from YouTube when a student first opens this course, or you can fetch them now.</p>
                ) : (
                  <ul className="mb-3 divide-y divide-slate-100 border border-slate-100 rounded-lg">
                    {lessons.map((l, i) => (
                      <li key={l.id} className="flex items-center gap-2 px-3 py-2">
                        <span className="text-xs text-slate-400 w-4">{i + 1}</span>
                        <a
                          href={`https://www.youtube.com/watch?v=${l.youtube_id}`}
                          target="_blank" rel="noreferrer"
                          className="flex-1 min-w-0 text-sm text-slate-700 hover:text-primary-600 truncate"
                          title={l.channel_title || ""}
                        >
                          {l.title}
                        </a>
                        <span className="text-[11px] text-slate-400">{formatClock(l.duration_seconds)}</span>
                        <button onClick={() => deleteLesson(l.id)} className="text-slate-300 hover:text-red-500"><Trash2 size={14} /></button>
                      </li>
                    ))}
                  </ul>
                )}

                <button onClick={refreshVideos} disabled={busy} className="w-full flex items-center justify-center gap-1.5 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white text-sm font-semibold py-2 rounded-lg">
                  <RefreshCw size={14} className={busy ? "animate-spin" : ""} /> {busy ? "Searching YouTube…" : lessons.length ? "Search YouTube again" : "Find videos on YouTube"}
                </button>
                <p className="text-[11px] text-slate-400 mt-2">Needs <code>YOUTUBE_API_KEY</code> in backend/.env. Searching again replaces the saved videos.</p>
              </Card>
            )}
          </div>

          {/* ---------- right: course table ---------- */}
          <Card className="md:col-span-2 p-0 overflow-hidden h-fit !p-0">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
                <tr>
                  <th className="text-left px-4 py-3">Course</th>
                  <th className="text-left px-4 py-3">Skill</th>
                  <th className="text-left px-4 py-3">Videos</th>
                  <th className="text-left px-4 py-3">Assessment</th>
                  <th className="text-right px-4 py-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {courses.map((c) => (
                  <tr key={c.id} className={`hover:bg-slate-50 ${selectedId === c.id ? "bg-primary-50/50" : ""}`}>
                    <td className="px-4 py-2.5">
                      <p className="font-medium text-slate-800">{c.title}</p>
                      <p className="text-xs text-slate-400">{c.provider} · {c.level}</p>
                    </td>
                    <td className="px-4 py-2.5 text-slate-500">{c.skill_tag}</td>
                    <td className="px-4 py-2.5">
                      {c.lesson_count > 0 ? (
                        <Badge tone="teal"><Film size={11} /> {c.lesson_count} · {formatDuration(c.total_seconds)}</Badge>
                      ) : (
                        <Badge tone="slate"><Clock size={11} /> not fetched yet</Badge>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      {c.question_count > 0 ? (
                        <Badge tone="teal"><ClipboardCheck size={11} /> {c.question_count} questions</Badge>
                      ) : (
                        <Badge tone="amber">no questions</Badge>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right whitespace-nowrap">
                      <button onClick={() => setSelectedId(c.id)} className="text-xs font-semibold text-primary-600 hover:underline mr-3">Manage videos</button>
                      <button onClick={() => deleteCourse(c.id)} className="text-slate-400 hover:text-red-500 align-middle"><Trash2 size={15} /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      ) : (
        <div className="grid md:grid-cols-3 gap-6">
          <Card className="md:col-span-1 h-fit">
            <h3 className="font-bold text-slate-800 mb-3 text-sm">Add Skill</h3>
            <form onSubmit={addSkill} className="space-y-2">
              <input required placeholder="Skill name" value={newSkill.skill_name} onChange={(e) => setNewSkill({ ...newSkill, skill_name: e.target.value })} className={inputCls} />
              <select value={newSkill.category} onChange={(e) => setNewSkill({ ...newSkill, category: e.target.value })} className={inputCls}>
                <option value="technical">Technical</option>
                <option value="soft">Soft</option>
              </select>
              <button type="submit" className="w-full flex items-center justify-center gap-1.5 bg-primary-600 hover:bg-primary-700 text-white text-sm font-semibold py-2 rounded-lg">
                <Plus size={14} /> Add Skill
              </button>
            </form>
          </Card>

          <Card className="md:col-span-2">
            <div className="flex flex-wrap gap-2">
              {skills.map((s) => (
                <span key={s.skill_name} className="text-xs bg-slate-100 text-slate-700 px-3 py-1.5 rounded-full">
                  {s.skill_name} <span className="text-slate-400">· {s.category}</span>
                </span>
              ))}
            </div>
          </Card>
        </div>
      )}
    </Layout>
  );
}
