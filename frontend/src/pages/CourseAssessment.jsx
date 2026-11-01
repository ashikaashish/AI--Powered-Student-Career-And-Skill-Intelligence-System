import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, XCircle, Sparkles, TrendingUp, ClipboardCheck, ShieldCheck, AlertTriangle } from "lucide-react";
import client from "../api/client";
import { Layout, Card, Loading } from "../components/Layout";
import ProctorPanel from "../components/ProctorPanel";
import useProctoring from "../hooks/useProctoring";

export default function CourseAssessment() {
  const { courseId } = useParams();
  const navigate = useNavigate();
  const [quiz, setQuiz] = useState(null);
  const [error, setError] = useState("");
  const [answers, setAnswers] = useState({});      // question id -> chosen option text
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  // --- proctoring state ---
  const [session, setSession] = useState(null);    // { session_id, time_limit_seconds, max_violations }
  const [started, setStarted] = useState(false);
  const [starting, setStarting] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [autoReason, setAutoReason] = useState("");
  const answersRef = useRef({});                   // latest answers, readable from timers/callbacks
  const deadlineRef = useRef(0);
  const submittingRef = useRef(false);
  const submitRef = useRef(() => {});

  const maxViolations = session?.max_violations ?? quiz?.max_violations ?? 3;
  const proctor = useProctoring({
    courseId,
    sessionId: session?.session_id,
    active: started && !result,
    maxViolations,
    onTerminate: () => {
      setAutoReason(`Your quiz was submitted automatically after ${maxViolations} integrity warnings.`);
      submitRef.current(true);
    },
  });

  useEffect(() => { answersRef.current = answers; }, [answers]);

  const load = () => {
    setResult(null);
    setAnswers({});
    setQuiz(null);
    setSession(null);
    setStarted(false);
    setAutoReason("");
    submittingRef.current = false;
    client.get(`/assessment/${courseId}`)
      .then((res) => setQuiz(res.data))
      .catch((err) => setError(err.response?.data?.error || "Could not load the assessment"));
  };
  useEffect(load, [courseId]);  // eslint-disable-line react-hooks/exhaustive-deps

  // Click "Start": go full screen first (browsers need a direct click for that), then ask the server
  // to start the clock, then try the camera. The camera is optional.
  const start = async () => {
    setStarting(true);
    proctor.enterFullscreen();
    try {
      const res = await client.post(`/assessment/${courseId}/start`);
      setSession(res.data);
      deadlineRef.current = Date.now() + res.data.time_limit_seconds * 1000;
      setSecondsLeft(res.data.time_limit_seconds);
      await proctor.startCamera();
      setStarted(true);
    } catch (err) {
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
      setError(err.response?.data?.error || "Could not start the assessment");
    } finally { setStarting(false); }
  };

  const submit = async (auto = false) => {
    if (submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    try {
      if (auto) proctor.logEvent("auto_submit");
      const res = await client.post(`/assessment/${courseId}/submit`, {
        answers: answersRef.current,
        session_id: session?.session_id,
      });
      proctor.stop();
      setResult(res.data);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      submittingRef.current = false;
      proctor.stop();
      setError(err.response?.data?.error || "Could not submit your answers");
    } finally { setSubmitting(false); }
  };
  useEffect(() => { submitRef.current = submit; });

  // Countdown. The server enforces the real limit; this just shows it and auto-submits at 0.
  useEffect(() => {
    if (!started || result) return;
    const t = setInterval(() => {
      const left = Math.max(0, Math.round((deadlineRef.current - Date.now()) / 1000));
      setSecondsLeft(left);
      if (left === 0) {
        clearInterval(t);
        setAutoReason("Time is up, so your answers were submitted automatically.");
        submitRef.current(true);
      }
    }, 500);
    return () => clearInterval(t);
  }, [started, result]);

  if (error) {
    return (
      <Layout>
        <Card>
          <p className="text-sm text-slate-600">{error}</p>
          <Link to={`/courses/${courseId}/learn`} className="text-primary-600 text-sm font-semibold">← Back to the course</Link>
        </Card>
      </Layout>
    );
  }
  if (!quiz) return <Layout><Loading /></Layout>;

  const { course } = quiz;
  const answered = Object.keys(answers).length;
  const allAnswered = answered === quiz.questions.length;

  return (
    <Layout>
      <button onClick={() => navigate(`/courses/${courseId}/learn`)} className="flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-primary-600 mb-3">
        <ArrowLeft size={15} /> Back to course
      </button>

      <div className="mb-5">
        <h1 className="text-2xl font-bold text-slate-800 tracking-tight flex items-center gap-2">
          <ClipboardCheck className="text-primary-600" size={24} /> {course.skill_tag} Assessment
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          {quiz.questions.length} questions on what you just learned. Score at least {quiz.pass_percent}% to add{" "}
          <span className="font-semibold text-primary-700">{course.skill_tag}</span> to your profile.
        </p>
      </div>

      {autoReason && !result && (
        <p className="mb-4 max-w-3xl text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">{autoReason}</p>
      )}
      {result && <ResultCard result={result} course={course} onRetry={load} autoReason={autoReason} />}

      {!started && !result && (
        <ConsentCard quiz={quiz} starting={starting} onStart={start} />
      )}

      {(started || result) && (
      <div className="grid lg:grid-cols-[minmax(0,1fr)_300px] gap-5 items-start">
      <div className={`space-y-4 max-w-3xl ${result ? "" : "select-none"}`}>
        {quiz.questions.map((q, i) => {
          const graded = result?.results.find((r) => r.id === q.id);
          return (
            <Card key={q.id}>
              <p className="text-sm font-semibold text-slate-800 mb-3">{i + 1}. {q.question}</p>
              <div className="space-y-2">
                {q.options.map((opt) => {
                  const chosen = answers[q.id] === opt;
                  let cls = "border-slate-200 hover:bg-slate-50";
                  if (graded) {
                    if (opt === graded.correct_answer) cls = "border-teal-300 bg-teal-50";
                    else if (chosen) cls = "border-red-300 bg-red-50";
                    else cls = "border-slate-100 opacity-70";
                  } else if (chosen) cls = "border-primary-500 bg-primary-50";
                  return (
                    <label key={opt} className={`flex items-start gap-3 rounded-lg border px-3 py-2.5 text-sm cursor-pointer transition-colors ${cls} ${graded ? "cursor-default" : ""}`}>
                      <input
                        type="radio"
                        name={`q${q.id}`}
                        disabled={!!result}
                        checked={chosen}
                        onChange={() => setAnswers({ ...answers, [q.id]: opt })}
                        className="mt-0.5 accent-primary-600"
                      />
                      <span className="text-slate-700">{opt}</span>
                    </label>
                  );
                })}
              </div>
              {graded && (
                <p className={`mt-3 text-xs flex items-start gap-1.5 ${graded.is_correct ? "text-teal-700" : "text-red-600"}`}>
                  {graded.is_correct ? <CheckCircle2 size={14} className="shrink-0 mt-0.5" /> : <XCircle size={14} className="shrink-0 mt-0.5" />}
                  <span>{graded.is_correct ? "Correct. " : `Correct answer: ${graded.correct_answer}. `}{graded.explanation}</span>
                </p>
              )}
            </Card>
          );
        })}

        {!result && (
          <div className="flex items-center gap-4">
            <button
              onClick={() => submit(false)}
              disabled={!allAnswered || submitting}
              className="bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white text-sm font-semibold px-6 py-2.5 rounded-lg"
            >
              {submitting ? "Checking…" : "Submit answers"}
            </button>
            <span className="text-xs text-slate-400">{answered} of {quiz.questions.length} answered</span>
          </div>
        )}
      </div>

      {!result && (
        <div className="lg:sticky lg:top-4">
          <ProctorPanel
            proctor={proctor}
            secondsLeft={secondsLeft}
            maxViolations={maxViolations}
            onReturnFullscreen={proctor.enterFullscreen}
          />
        </div>
      )}
      </div>
      )}
    </Layout>
  );
}

function ResultCard({ result, course, onRetry, autoReason }) {
  const { passed, score_percent, correct, total, newly_completed, career_impact, proctor } = result;
  return (
    <div className={`mb-5 max-w-3xl rounded-2xl border p-5 shadow-sm ${passed ? "border-teal-200 bg-gradient-to-br from-teal-50 to-white" : "border-amber-200 bg-gradient-to-br from-amber-50 to-white"}`}>
      <div className="flex items-start gap-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${passed ? "bg-teal-100 text-teal-700" : "bg-amber-100 text-amber-700"}`}>
          {passed ? <Sparkles size={20} /> : <XCircle size={20} />}
        </div>
        <div>
          <p className="font-bold text-slate-800">
            {passed ? "You passed!" : "Not quite — you didn't reach the pass mark"}
          </p>
          <p className="text-sm text-slate-600 mt-0.5">
            You scored {score_percent}% ({correct} of {total} correct).{" "}
            {passed
              ? newly_completed
                ? <><span className="font-semibold text-teal-700">{course.skill_tag}</span> has been added to your profile skills.</>
                : <>Your profile already includes <span className="font-semibold text-teal-700">{course.skill_tag}</span>.</>
              : proctor?.flagged
                ? "This attempt was flagged for too many integrity warnings, so it cannot pass. Stay in full screen on this tab and try again."
                : "Review the explanations below, rewatch the videos if needed and try again."}
          </p>
          {autoReason && <p className="text-xs text-amber-700 mt-1">{autoReason}</p>}
          {proctor && (
            <p className="text-xs text-slate-500 mt-1">Integrity warnings during this attempt: {proctor.violations} of {proctor.max_violations}.</p>
          )}
        </div>
      </div>

      {passed && career_impact?.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold text-slate-500 flex items-center gap-1 mb-2"><TrendingUp size={13} /> Careers that now match you better</p>
          <div className="flex flex-wrap gap-2">
            {career_impact.map((c) => (
              <span key={c.title} className="text-xs bg-white border border-teal-100 rounded-full px-3 py-1.5 text-slate-700">
                {c.title} <span className="font-bold text-teal-700">{c.match_score}%</span>
                <span className="text-teal-600 font-semibold"> ▲{c.change}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-4 mt-4 text-sm font-semibold">
        {passed ? (
          <>
            <Link to="/profile" className="text-primary-600 hover:underline">View my profile skills →</Link>
            <Link to="/recommendations" className="text-slate-500 hover:underline">See my AI career matches</Link>
            <Link to="/courses" className="text-slate-500 hover:underline">More courses</Link>
          </>
        ) : (
          <>
            <button onClick={onRetry} className="text-primary-600 hover:underline">Try again with fresh question order</button>
            <Link to={`/courses/${course.id}/learn`} className="text-slate-500 hover:underline">Rewatch the videos</Link>
          </>
        )}
      </div>
    </div>
  );
}

function ConsentCard({ quiz, starting, onStart }) {
  const mins = Math.round((quiz.time_limit_seconds || 600) / 60);
  return (
    <div className="max-w-3xl rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="font-bold text-slate-800 flex items-center gap-2"><ShieldCheck size={18} className="text-primary-600" /> Before you start</p>
      <ul className="mt-3 space-y-2 text-sm text-slate-600 list-disc pl-5">
        <li>You have <b>{mins} minutes</b>. The timer runs on our server, so refreshing the page will not pause it.</li>
        <li>The quiz opens in <b>full screen</b>. Switching tabs or leaving full screen counts as a warning. After <b>{quiz.max_violations} warnings</b> the quiz is submitted automatically and cannot pass.</li>
        <li>Your <b>camera</b> is used only to check that one face is visible. The check runs inside your browser; <b>no video is recorded or uploaded</b>. If you don't allow the camera, you can still take the quiz with the other checks on.</li>
        <li>Copy, paste and right-click are disabled during the quiz. Only the type of each event and its time are saved.</li>
      </ul>
      <p className="mt-3 text-xs text-slate-400 flex items-center gap-1"><AlertTriangle size={12} /> Close other tabs and apps, and sit in good light so the face check works well.</p>
      <button
        onClick={onStart}
        disabled={starting}
        className="mt-4 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white text-sm font-semibold px-6 py-2.5 rounded-lg"
      >
        {starting ? "Starting…" : "I agree, start the assessment"}
      </button>
    </div>
  );
}