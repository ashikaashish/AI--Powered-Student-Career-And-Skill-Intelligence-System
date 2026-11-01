import { useEffect, useRef, useState } from "react";
import { Clock, X, CheckCircle2, XCircle, BadgeCheck } from "lucide-react";
import client from "../api/client";

/**
 * Full-screen test dialog for verifying one skill.
 * Props: skill (string), onClose(), onPassed() - called after the profile should reload.
 */
export default function SkillTestModal({ skill, onClose, onPassed }) {
  const [test, setTest] = useState(null);        // {session_id, questions, pass_percent, time_limit_seconds}
  const [error, setError] = useState("");
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState({});    // question_id -> chosen option text
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const submittedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    client
      .post("/skill-test/start", { skill_name: skill })
      .then((res) => {
        if (cancelled) return;
        setTest(res.data);
        setSecondsLeft(res.data.time_limit_seconds);
      })
      .catch((err) => !cancelled && setError(err.response?.data?.error || "Couldn't start the test."));
    return () => { cancelled = true; };
  }, [skill]);

  const submit = async (finalAnswers) => {
    if (submittedRef.current || !test) return;
    submittedRef.current = true;
    setSubmitting(true);
    try {
      const res = await client.post("/skill-test/submit", {
        session_id: test.session_id,
        answers: finalAnswers,
      });
      setResult(res.data);
      if (res.data.passed) onPassed?.();
    } catch (err) {
      setError(err.response?.data?.error || "Couldn't submit the test.");
    } finally {
      setSubmitting(false);
    }
  };

  // countdown; auto-submit when time is up
  useEffect(() => {
    if (!test || result || error) return undefined;
    const t = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          clearInterval(t);
          submit(answers);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [test, result, error]);

  const mmss = `${String(Math.floor(secondsLeft / 60)).padStart(2, "0")}:${String(secondsLeft % 60).padStart(2, "0")}`;
  const q = test?.questions[index];
  const isLast = test && index === test.questions.length - 1;

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-600"
          aria-label="Close"
        >
          <X size={18} />
        </button>

        <h3 className="font-bold text-slate-800 mb-1 pr-8">Verify your {skill} skill</h3>

        {error && (
          <div className="mt-4">
            <p className="text-sm text-red-600 mb-4">{error}</p>
            <button onClick={onClose} className="text-sm font-semibold text-primary-700">Close</button>
          </div>
        )}

        {!error && !test && <p className="text-sm text-slate-500 mt-4">Preparing your questions...</p>}

        {!error && test && !result && q && (
          <>
            <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
              <span>Question {index + 1} of {test.questions.length}</span>
              <span className={`flex items-center gap-1 ${secondsLeft < 60 ? "text-red-600 font-semibold" : ""}`}>
                <Clock size={13} /> {mmss}
              </span>
            </div>
            <div className="h-1 bg-slate-100 rounded-full mb-4">
              <div
                className="h-1 bg-primary-600 rounded-full transition-all"
                style={{ width: `${((index + 1) / test.questions.length) * 100}%` }}
              />
            </div>

            <p className="text-slate-800 text-sm font-medium mb-3">{q.question}</p>
            <div className="space-y-2">
              {q.options.map((opt) => {
                const selected = answers[q.id] === opt;
                return (
                  <button
                    key={opt}
                    onClick={() => setAnswers({ ...answers, [q.id]: opt })}
                    className={`w-full text-left text-sm px-3 py-2.5 rounded-lg border transition-colors ${
                      selected
                        ? "border-primary-500 bg-primary-50 text-primary-800"
                        : "border-slate-200 hover:bg-slate-50 text-slate-700"
                    }`}
                  >
                    {opt}
                  </button>
                );
              })}
            </div>

            <div className="flex items-center justify-between mt-5">
              <span className="text-xs text-slate-400">Pass mark: {test.pass_percent}%</span>
              {isLast ? (
                <button
                  onClick={() => submit(answers)}
                  disabled={submitting || !answers[q.id]}
                  className="bg-primary-600 hover:bg-primary-700 text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50"
                >
                  {submitting ? "Submitting..." : "Submit test"}
                </button>
              ) : (
                <button
                  onClick={() => setIndex(index + 1)}
                  disabled={!answers[q.id]}
                  className="bg-primary-600 hover:bg-primary-700 text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50"
                >
                  Next question
                </button>
              )}
            </div>
          </>
        )}

        {result && (
          <div className="mt-4">
            {result.passed ? (
              <div className="flex items-start gap-3 bg-teal-50 border border-teal-100 rounded-lg p-3 mb-4">
                <BadgeCheck className="text-teal-600 shrink-0" size={20} />
                <div>
                  <p className="text-sm font-semibold text-teal-800">{skill} verified - {result.score_percent}%</p>
                  <p className="text-xs text-teal-700">{result.correct} of {result.total} correct. The skill is now on your profile.</p>
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-3 bg-red-50 border border-red-100 rounded-lg p-3 mb-4">
                <XCircle className="text-red-500 shrink-0" size={20} />
                <div>
                  <p className="text-sm font-semibold text-red-800">Not passed - {result.score_percent}%</p>
                  <p className="text-xs text-red-700">
                    You need {result.pass_percent}% to verify {skill}. Learn it in a course, then try again later.
                  </p>
                </div>
              </div>
            )}

            {result.passed && result.results && (
              <ul className="max-h-48 overflow-y-auto space-y-2 mb-4 pr-1">
                {result.results.map((r) => (
                  <li key={r.id} className="text-xs text-slate-600 flex gap-2">
                    {r.is_correct
                      ? <CheckCircle2 size={14} className="text-teal-500 shrink-0 mt-0.5" />
                      : <XCircle size={14} className="text-red-400 shrink-0 mt-0.5" />}
                    <span>{r.question}{!r.is_correct && ` - Answer: ${r.correct_answer}`}</span>
                  </li>
                ))}
              </ul>
            )}

            <div className="flex gap-2">
              {!result.passed && (
                <a
                  href="/courses"
                  className="bg-primary-50 text-primary-700 hover:bg-primary-100 text-sm font-semibold px-4 py-2 rounded-lg"
                >
                  Find a {skill} course
                </a>
              )}
              <button onClick={onClose} className="text-sm font-semibold text-slate-600 px-4 py-2">Close</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}