import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft, CheckCircle2, Circle, PlayCircle, Lock, ChevronRight, Clock, ClipboardCheck, Play,
} from "lucide-react";
import client, { API_BASE_URL } from "../api/client";
import { Layout, Card, Loading, ProgressBar, Badge } from "../components/Layout";
import { formatClock, formatDuration } from "../utils/format";

const SYNC_EVERY_MS = 5000;

// Load the YouTube IFrame Player API once for the whole app.
let ytApiPromise = null;
function loadYouTubeApi() {
  if (window.YT && window.YT.Player) return Promise.resolve(window.YT);
  if (ytApiPromise) return ytApiPromise;
  ytApiPromise = new Promise((resolve) => {
    const prev = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => { if (prev) prev(); resolve(window.YT); };
    const tag = document.createElement("script");
    tag.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(tag);
  });
  return ytApiPromise;
}

export default function CourseLearn() {
  const { courseId } = useParams();
  const navigate = useNavigate();

  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [activeId, setActiveId] = useState(null);
  const [live, setLive] = useState({});          // lessonId -> furthest second reached (before the server confirms)
  const [notice, setNotice] = useState("");
  const [enrolling, setEnrolling] = useState(false);
  const [playerError, setPlayerError] = useState("");

  const holderRef = useRef(null);
  const playerRef = useRef(null);
  const readyRef = useRef(false);
  const maxRef = useRef(0);                      // furthest second legitimately reached in the active lesson
  const posRef = useRef(null);                   // {lessonId, position, duration} for flush-on-leave
  const lastSyncRef = useRef(0);
  const activeRef = useRef(null);
  const dataRef = useRef(null);
  const loadedLessonRef = useRef(null);          // lesson currently loaded in the YouTube player

  const load = useCallback(() => {
    return client
      .get(`/learn/courses/${courseId}`)
      .then((res) => {
        setData(res.data);
        setActiveId((cur) => cur ?? res.data.resume_lesson_id);
      })
      .catch((err) => setError(err.response?.data?.error || "Could not load this course"));
  }, [courseId]);

  useEffect(() => { load(); }, [load]);

  const lessons = data?.lessons || [];
  const active = lessons.find((l) => l.id === activeId) || null;
  const activeIndex = lessons.findIndex((l) => l.id === activeId);
  const enrolled = !!data?.enrolled;
  const status = data?.status;                   // in_progress | watched | completed
  const threshold = data?.completion_threshold || 90;
  const watchedDone = status === "watched" || status === "completed";

  useEffect(() => { activeRef.current = active; dataRef.current = data; });

  const totalSeconds = lessons.reduce((a, l) => a + (l.duration_seconds || 0), 0);
  const liveWatched = lessons.reduce(
    (a, l) => a + Math.min(l.duration_seconds || 0, Math.max(l.watched_seconds || 0, live[l.id] || 0)), 0);
  const overall = totalSeconds > 0 ? Math.max(data?.watch_percent || 0, (liveWatched / totalSeconds) * 100) : 0;

  // ---- tell the server where the player is ----
  const report = useCallback(async ({ ended = false } = {}) => {
    const p = playerRef.current;
    const lesson = activeRef.current;
    if (!p || !readyRef.current || !lesson || !p.getDuration) return;
    const duration = p.getDuration();
    if (!duration) return;
    try {
      const res = await client.post(`/learn/lessons/${lesson.id}/progress`, {
        position: p.getCurrentTime(), duration, ended,
      });
      const r = res.data;
      setData((d) => d && ({
        ...d,
        status: r.status,
        watch_percent: r.watch_percent,
        lessons: d.lessons.map((l) => l.id === r.lesson.id ? {
          ...l, watched_seconds: r.lesson.watched_seconds, last_position: r.lesson.last_position,
          duration_seconds: r.lesson.duration_seconds, percent: r.lesson.percent, completed: r.lesson.completed,
        } : l),
      }));
      maxRef.current = Math.max(maxRef.current, r.lesson.watched_seconds);
    } catch { /* transient: next tick retries */ }
  }, []);

  // ---- create the YouTube player once the course is loaded and the learner is enrolled ----
  useEffect(() => {
    if (!enrolled || !lessons.length || !holderRef.current || playerRef.current) return;
    let cancelled = false;
    loadYouTubeApi().then((YT) => {
      if (cancelled || !holderRef.current) return;
      const first = lessons.find((l) => l.id === (activeRef.current?.id ?? lessons[0].id)) || lessons[0];
      loadedLessonRef.current = first.id;
      playerRef.current = new YT.Player(holderRef.current, {
        videoId: first.youtube_id,
        width: "100%", height: "100%",
        playerVars: { rel: 0, modestbranding: 1, playsinline: 1, origin: window.location.origin },
        events: {
          onReady: () => { readyRef.current = true; resumeActive(0); },
          onStateChange: (e) => {
            if (e.data === YT.PlayerState.ENDED) onEnded();
            if (e.data === YT.PlayerState.PAUSED) report();
          },
          onError: () => setPlayerError("This video can't be played here (the owner may have disabled embedding). Try another lesson or ask an admin to refresh the videos."),
        },
      });
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enrolled, lessons.length]);

  // destroy the player when leaving the page
  useEffect(() => () => {
    try { playerRef.current?.destroy(); } catch { /* ignore */ }
    playerRef.current = null; readyRef.current = false;
  }, []);

  const resumeActive = (delay) => {
    const lesson = activeRef.current;
    const p = playerRef.current;
    if (!lesson || !p) return;
    maxRef.current = lesson.watched_seconds || 0;
    const at = Math.min(lesson.last_position || 0, maxRef.current);
    if (at > 3) setTimeout(() => { try { p.seekTo(at, true); } catch { /* ignore */ } }, delay);
  };

  // switching lessons
  useEffect(() => {
    if (!readyRef.current || !playerRef.current || !active) return;
    if (loadedLessonRef.current === active.id) return;
    loadedLessonRef.current = active.id;
    maxRef.current = active.watched_seconds || 0;
    const start = Math.min(active.last_position || 0, maxRef.current);
    setPlayerError("");
    playerRef.current.loadVideoById({ videoId: active.youtube_id, startSeconds: start > 3 ? start : 0 });
  }, [active?.id]);  // eslint-disable-line react-hooks/exhaustive-deps

  // ---- once a second: track position, block skipping ahead, sync to the server every 5s ----
  useEffect(() => {
    if (!enrolled) return;
    const id = setInterval(() => {
      const p = playerRef.current;
      const lesson = activeRef.current;
      if (!p || !readyRef.current || !lesson || !p.getPlayerState) return;
      const state = p.getPlayerState();
      const t = p.getCurrentTime();
      const d = p.getDuration();
      if (state === 1 || state === 3) {           // playing / buffering
        if (t > maxRef.current + 3) {             // jumped ahead of what was actually watched
          p.seekTo(maxRef.current, true);
          setNotice("You can jump back anytime, but can't skip ahead of what you've watched.");
          setTimeout(() => setNotice(""), 3500);
          return;
        }
        if (t > maxRef.current) maxRef.current = t;
        posRef.current = { lessonId: lesson.id, position: t, duration: d };
        setLive((m) => ({ ...m, [lesson.id]: Math.max(m[lesson.id] || 0, maxRef.current) }));
        if (state === 1 && Date.now() - lastSyncRef.current >= SYNC_EVERY_MS) {
          lastSyncRef.current = Date.now();
          report();
        }
      }
    }, 1000);
    return () => clearInterval(id);
  }, [enrolled, report]);

  // save when leaving the page (keepalive survives tab close)
  useEffect(() => {
    const flush = () => {
      const p = posRef.current;
      if (!p || !p.duration || !dataRef.current?.enrolled) return;
      fetch(`${API_BASE_URL}/learn/lessons/${p.lessonId}/progress`, {
        method: "POST", keepalive: true,
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("careerai_token")}` },
        body: JSON.stringify({ position: p.position, duration: p.duration }),
      }).catch(() => {});
    };
    window.addEventListener("pagehide", flush);
    return () => { window.removeEventListener("pagehide", flush); flush(); };
  }, []);

  const onEnded = async () => {
    await report({ ended: true });
    const list = dataRef.current?.lessons || [];
    const idx = list.findIndex((l) => l.id === activeRef.current?.id);
    if (idx >= 0 && list[idx + 1]) setActiveId(list[idx + 1].id);
  };

  const selectLesson = (id) => {
    if (id === activeId) return;
    report();
    setActiveId(id);
  };

  const handleEnroll = async () => {
    setEnrolling(true);
    try {
      await client.post(`/courses/${courseId}/enroll`);
      await load();
    } catch (err) {
      setError(err.response?.data?.error || "Could not enroll");
    } finally { setEnrolling(false); }
  };

  if (error && !data) return <Layout><Card><p className="text-sm text-slate-500">{error}</p><Link to="/courses" className="text-primary-600 text-sm font-semibold">← Back to courses</Link></Card></Layout>;
  if (!data) return <Layout><Loading /></Layout>;

  const { course } = data;

  return (
    <Layout>
      <button onClick={() => navigate("/courses")} className="flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-primary-600 mb-3">
        <ArrowLeft size={15} /> All courses
      </button>

      <div className="flex flex-wrap items-start justify-between gap-3 mb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 tracking-tight">{course.title}</h1>
          <p className="text-sm text-slate-500 mt-1 font-medium">
            {course.level} · topic <span className="text-primary-700 font-semibold">{course.skill_tag}</span>
            {lessons.length > 0 && <> · {lessons.length} video{lessons.length > 1 ? "s" : ""} · {formatDuration(data.total_seconds)}</>}
          </p>
        </div>
        {status === "completed" && <Badge tone="teal"><CheckCircle2 size={13} /> Skill earned</Badge>}
      </div>

      {status === "watched" && (
        <div className="mb-5 rounded-2xl border border-primary-200 bg-gradient-to-br from-primary-50 to-white p-5 shadow-sm flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-100 text-primary-700 flex items-center justify-center shrink-0"><ClipboardCheck size={20} /></div>
            <div>
              <p className="font-bold text-slate-800">You've finished the videos — time for the {course.skill_tag} assessment</p>
              <p className="text-sm text-slate-600 mt-0.5">Pass it and “{course.skill_tag}” is added to your profile skills.</p>
              {data.last_attempt && !data.last_attempt.passed && (
                <p className="text-xs text-amber-700 mt-1">Last attempt: {data.last_attempt.score_percent}% — you can try again.</p>
              )}
            </div>
          </div>
          <Link to={`/courses/${courseId}/assessment`} className="bg-primary-600 hover:bg-primary-700 text-white text-sm font-semibold px-5 py-2.5 rounded-lg">
            {data.last_attempt ? "Retake assessment" : "Take assessment"}
          </Link>
        </div>
      )}

      {lessons.length === 0 ? (
        <Card>
          <p className="text-sm text-slate-600">
            {data.video_error || "No videos have been found for this topic yet."}
          </p>
          {data.video_error?.includes("YOUTUBE_API_KEY") && (
            <p className="text-xs text-slate-400 mt-2">Ask the admin to add a YouTube API key to <code>backend/.env</code>.</p>
          )}
        </Card>
      ) : (
        <div className="grid lg:grid-cols-3 gap-5">
          {/* ---------------- player ---------------- */}
          <div className="lg:col-span-2 space-y-4">
            <div className="rounded-2xl overflow-hidden bg-black shadow-lg aspect-video relative">
              {enrolled ? (
                <div className="absolute inset-0"><div ref={holderRef} /></div>
              ) : (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center text-white gap-3 p-6 bg-gradient-to-br from-slate-800 to-slate-900">
                  <Lock size={30} className="text-slate-400" />
                  <p className="font-semibold">Enroll to start watching</p>
                  <p className="text-xs text-slate-400 max-w-xs">Videos from YouTube play right here. Your progress is saved automatically.</p>
                  <button onClick={handleEnroll} disabled={enrolling}
                    className="mt-1 bg-primary-600 hover:bg-primary-700 disabled:opacity-60 text-white text-sm font-semibold px-5 py-2 rounded-lg">
                    {enrolling ? "Enrolling…" : "Enroll — it's free"}
                  </button>
                </div>
              )}
            </div>

            {playerError && <div className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{playerError}</div>}
            {notice && <div className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">{notice}</div>}

            {active && (
              <p className="text-xs text-slate-400 flex items-center gap-1.5">
                <Play size={14} className="text-red-500" fill="currentColor" /> {active.title}{active.channel_title ? ` · ${active.channel_title}` : ""}
              </p>
            )}

            <Card className="!p-5">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-500 mb-2">
                <span>{status === "completed" ? "Assessment passed" : status === "watched" ? "Videos finished" : "Your progress"}</span>
                <span>{Math.round(overall)}%</span>
              </div>
              <ProgressBar value={overall} />
              <p className="text-[11px] text-slate-400 mt-2">
                {status === "completed"
                  ? `“${course.skill_tag}” is on your profile.`
                  : status === "watched"
                    ? `Pass the ${course.skill_tag} assessment to add it to your profile.`
                    : enrolled
                      ? `Watch ${threshold}% of the videos to unlock the ${course.skill_tag} assessment.`
                      : "Enroll to start tracking your progress."}
              </p>
            </Card>
          </div>

          {/* ---------------- video list ---------------- */}
          <Card className="!p-0 h-fit overflow-hidden">
            <div className="px-5 py-3.5 border-b border-slate-100 text-sm font-bold text-slate-800">Course videos</div>
            <ul className="divide-y divide-slate-100">
              {lessons.map((l, i) => {
                const isActive = l.id === activeId;
                const pct = Math.min(100, Math.max(l.percent || 0, l.duration_seconds ? ((live[l.id] || 0) / l.duration_seconds) * 100 : 0));
                const done = l.completed || pct >= threshold;
                return (
                  <li key={l.id}>
                    <button
                      disabled={!enrolled}
                      onClick={() => selectLesson(l.id)}
                      className={`w-full text-left px-5 py-3.5 flex items-start gap-3 transition-colors ${isActive ? "bg-primary-50" : "hover:bg-slate-50"} disabled:cursor-not-allowed`}
                    >
                      <span className="mt-0.5 shrink-0">
                        {done ? <CheckCircle2 size={17} className="text-teal-600" />
                          : isActive ? <PlayCircle size={17} className="text-primary-600" />
                          : !enrolled ? <Lock size={16} className="text-slate-300" />
                          : <Circle size={17} className="text-slate-300" />}
                      </span>
                      <span className="flex-1 min-w-0">
                        <span className={`block text-sm leading-snug ${isActive ? "font-semibold text-primary-800" : "font-medium text-slate-700"}`}>
                          {i + 1}. {l.title}
                        </span>
                        <span className="flex items-center gap-1 text-[11px] text-slate-400 mt-0.5">
                          <Clock size={11} /> {formatClock(l.duration_seconds)}
                          {enrolled && pct > 0 && !done && <span className="ml-1">· {Math.round(pct)}% watched</span>}
                        </span>
                        {enrolled && pct > 0 && !done && <ProgressBar value={pct} className="!h-1 mt-1.5" />}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            {enrolled && activeIndex >= 0 && activeIndex < lessons.length - 1 && (
              <button onClick={() => selectLesson(lessons[activeIndex + 1].id)}
                className="w-full flex items-center justify-center gap-1 text-xs font-semibold text-primary-600 hover:bg-primary-50 py-3 border-t border-slate-100">
                Next video <ChevronRight size={14} />
              </button>
            )}
           {watchedDone && status !== "completed" && (
  <Link to={`/courses/${courseId}/assessment`}
    className="w-full flex items-center justify-center gap-1.5 text-xs font-semibold text-white bg-primary-600 hover:bg-primary-700 py-3">
    <ClipboardCheck size={14} /> Take assessment
  </Link>
)}
          </Card>
        </div>
      )}
    </Layout>
  );
}
