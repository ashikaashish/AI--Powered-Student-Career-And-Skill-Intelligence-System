import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Compass, ArrowRight, ArrowLeft, RotateCcw, Clock, Target,
  TrendingUp, ShieldAlert, Brain, Heart, AlertCircle,
} from "lucide-react";
import client from "../api/client";
import { Layout, Card, PageHeader, Loading, ProgressBar } from "../components/Layout";

const RATING_LABELS = ["Strongly dislike", "Dislike", "Neutral", "Like", "Strongly like"];

const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

/* ---------- interest hexagon (RIASEC) ---------- */
function Radar({ values, labels }) {
  const keys = Object.keys(labels);
  const size = 260, c = size / 2, r = 90;
  const pt = (i, v) => {
    const a = (Math.PI * 2 * i) / keys.length - Math.PI / 2;
    return [c + Math.cos(a) * r * (v / 100), c + Math.sin(a) * r * (v / 100)];
  };
  const ring = (v) => keys.map((_, i) => pt(i, v).join(",")).join(" ");
  const shape = keys.map((k, i) => pt(i, values[k]).join(",")).join(" ");
  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-[280px] mx-auto">
      {[25, 50, 75, 100].map((v) => (
        <polygon key={v} points={ring(v)} fill="none" stroke="#e2e8f0" strokeWidth="1" />
      ))}
      {keys.map((k, i) => {
        const [x, y] = pt(i, 100);
        return <line key={k} x1={c} y1={c} x2={x} y2={y} stroke="#e2e8f0" />;
      })}
      <polygon points={shape} fill="rgba(46,91,223,0.25)" stroke="#2e5bdf" strokeWidth="2" />
      {keys.map((k, i) => {
        const [x, y] = pt(i, 122);
        return (
          <text key={k} x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontSize="10" fontWeight="600" fill="#475569">
            {labels[k]}
          </text>
        );
      })}
    </svg>
  );
}

export default function AptitudeQuiz() {
  const [data, setData] = useState(null);
  const [history, setHistory] = useState([]);
  const [phase, setPhase] = useState("intro"); // intro | test | result
  const [idx, setIdx] = useState(0);
  const [abilityAns, setAbilityAns] = useState({});
  const [interestAns, setInterestAns] = useState({});
  const [seconds, setSeconds] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [showHint, setShowHint] = useState(false);

  const loadHistory = () =>
    client.get("/aptitude/history").then((r) => setHistory(r.data)).catch(() => {});

  useEffect(() => {
    client
      .get("/aptitude/questions")
      .then((r) => setData(r.data))
      .catch(() => setError("Couldn't load the test. Check that the backend is running and try again."));
    loadHistory();
  }, []);

  useEffect(() => {
    if (phase !== "test") return;
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [phase]);

  const steps = useMemo(() => {
    if (!data) return [];
    return [
      ...data.ability.map((q) => ({ type: "ability", q })),
      ...data.interest.map((q) => ({ type: "interest", q })),
    ];
  }, [data]);

  const current = steps[idx];
  const answered = current
    ? current.type === "ability"
      ? abilityAns[current.q.id] !== undefined
      : interestAns[current.q.id] !== undefined
    : false;

  const start = () => {
    setAbilityAns({}); setInterestAns({}); setIdx(0); setSeconds(0);
    setResult(null); setError(""); setShowHint(false);
    setPhase("test");
  };

  const next = async () => {
    if (!answered) { setShowHint(true); return; }
    setShowHint(false);
    if (idx < steps.length - 1) { setIdx(idx + 1); return; }
    setSubmitting(true);
    setError("");
    try {
      const res = await client.post("/aptitude/submit", { ability: abilityAns, interest: interestAns });
      setResult(res.data);
      setPhase("result");
      loadHistory();
    } catch (e) {
      setError(
        e.response?.data?.error ||
          (e.request ? "Couldn't reach the server. Check that the backend is running on port 5000." : "Couldn't submit your answers.")
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (!data && !error) return <Layout><Loading /></Layout>;

  /* ---------------- intro ---------------- */
  if (phase === "intro") {
    return (
      <Layout>
        <PageHeader
          title="Aptitude & Interest Test"
          subtitle="Answer real questions and rate what you enjoy - we'll recommend careers that fit both your abilities and your interests."
        />
        {error && (
          <div className="mb-4 flex items-center gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
            <AlertCircle size={16} /> {error}
          </div>
        )}
        <div className="grid md:grid-cols-2 gap-6 mb-6">
          <Card>
            <div className="flex items-center gap-2 text-primary-700 mb-2"><Brain size={18} /><h3 className="font-bold">Part 1 - Ability (20 questions)</h3></div>
            <p className="text-sm text-slate-500 mb-3">Multiple-choice questions with a right answer, 5 in each area:</p>
            <ul className="text-sm text-slate-700 space-y-1">
              <li>- Numerical reasoning (percentages, ratios, speed)</li>
              <li>- Verbal reasoning (vocabulary, analogies, comprehension)</li>
              <li>- Logical reasoning (series, deduction, coding)</li>
              <li>- Spatial reasoning (shapes, directions, 3D)</li>
            </ul>
          </Card>
          <Card>
            <div className="flex items-center gap-2 text-primary-700 mb-2"><Heart size={18} /><h3 className="font-bold">Part 2 - Interests (24 statements)</h3></div>
            <p className="text-sm text-slate-500 mb-3">
              Rate how much you'd enjoy each activity, from "Strongly dislike" to "Strongly like". This uses the
              Holland (RIASEC) model: Realistic, Investigative, Artistic, Social, Enterprising, Conventional.
            </p>
            <p className="text-sm text-slate-500">There are no right or wrong answers here - be honest.</p>
          </Card>
        </div>
        <Card className="mb-6">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-slate-600">
            <span className="flex items-center gap-1.5"><Clock size={15} /> About 10-15 minutes</span>
            <span className="flex items-center gap-1.5"><Target size={15} /> 44 questions, one at a time</span>
            <span>Answer from your first instinct - no need to overthink.</span>
          </div>
          <button
            onClick={start}
            disabled={!data}
            className="mt-5 flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-semibold px-5 py-2.5 rounded-lg transition-colors disabled:opacity-60"
          >
            Start the test <ArrowRight size={15} />
          </button>
        </Card>
        {history.length > 0 && <History history={history} />}
      </Layout>
    );
  }

  /* ---------------- test ---------------- */
  if (phase === "test" && current) {
    const isAbility = current.type === "ability";
    const q = current.q;
    const pct = Math.round((idx / steps.length) * 100);
    const abilityCount = data.ability.length;
    return (
      <Layout>
        <PageHeader title="Aptitude & Interest Test" subtitle={isAbility ? "Part 1 of 2 - Ability" : "Part 2 of 2 - Interests"} />
        <Card className="max-w-2xl">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
            <span className="font-semibold text-primary-700">
              {isAbility ? q.ability_label : "Interest rating"}
            </span>
            <span className="flex items-center gap-1"><Clock size={13} /> {fmt(seconds)}</span>
          </div>
          <ProgressBar value={pct} className="mb-1" />
          <p className="text-[11px] text-slate-400 mb-6">Question {idx + 1} of {steps.length}</p>

          {isAbility ? (
            <>
              <p className="text-base font-semibold text-slate-800 leading-relaxed mb-5">{q.question}</p>
              <div className="space-y-2.5">
                {q.options.map((opt, i) => {
                  const selected = abilityAns[q.id] === i;
                  return (
                    <button
                      key={i}
                      onClick={() => { setAbilityAns((a) => ({ ...a, [q.id]: i })); setShowHint(false); }}
                      className={`w-full text-left text-sm px-4 py-3 rounded-xl border transition-colors ${
                        selected
                          ? "border-primary-600 bg-primary-50 text-primary-800 font-semibold"
                          : "border-slate-200 hover:border-slate-300 text-slate-700"
                      }`}
                    >
                      <span className="inline-block w-6 font-bold text-slate-400">{"ABCD"[i]}.</span> {opt}
                    </button>
                  );
                })}
              </div>
            </>
          ) : (
            <>
              <p className="text-xs text-slate-500 mb-1">How much would you enjoy...</p>
              <p className="text-base font-semibold text-slate-800 leading-relaxed mb-5">{q.statement}</p>
              <div className="grid grid-cols-5 gap-2">
                {RATING_LABELS.map((label, i) => {
                  const val = i + 1;
                  const selected = interestAns[q.id] === val;
                  return (
                    <button
                      key={val}
                      onClick={() => { setInterestAns((a) => ({ ...a, [q.id]: val })); setShowHint(false); }}
                      className={`px-1 py-3 rounded-xl border text-center transition-colors ${
                        selected
                          ? "border-primary-600 bg-primary-50 text-primary-800"
                          : "border-slate-200 hover:border-slate-300 text-slate-600"
                      }`}
                    >
                      <span className="block text-lg font-bold">{val}</span>
                      <span className="block text-[10px] leading-tight mt-0.5">{label}</span>
                    </button>
                  );
                })}
              </div>
            </>
          )}

          {showHint && !answered && (
            <p className="text-xs text-red-600 mt-4">Choose an answer to continue.</p>
          )}
          {error && (
            <div className="mt-4 flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{error} Your answers are still here - press the button again to retry.</span>
            </div>
          )}

          <div className="flex items-center justify-between mt-6">
            <button
              onClick={() => { setIdx(Math.max(0, idx - 1)); setShowHint(false); }}
              disabled={idx === 0}
              className="flex items-center gap-1.5 text-sm font-semibold text-slate-500 hover:text-slate-700 disabled:opacity-40"
            >
              <ArrowLeft size={14} /> Back
            </button>
            <button
              onClick={next}
              disabled={submitting}
              className="flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-semibold px-5 py-2.5 rounded-lg transition-colors disabled:opacity-60"
            >
              {submitting ? "Finding your matches..." : idx === steps.length - 1 ? "See my careers" : "Next"} <ArrowRight size={15} />
            </button>
          </div>
          {idx === abilityCount - 1 && (
            <p className="text-[11px] text-slate-400 mt-4">Next up: Part 2 - the interest questions have no right or wrong answers.</p>
          )}
        </Card>
      </Layout>
    );
  }

  /* ---------------- result ---------------- */
  const r = result;
  if (!r) return null;
  const abilityLabels = data.labels.ability;
  const interestLabels = data.labels.interest;
  const hint = data.labels.interest_hints;
  const topLetters = r.interest_code.split("");
  const best = r.fields[0];

  return (
    <Layout>
      <PageHeader
        title="Your career matches"
        subtitle={`Completed in ${fmt(seconds)}. Your Holland code is ${r.interest_code} - strongest field: ${best.field}.`}
        action={
          <button onClick={start} className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-700">
            <RotateCcw size={13} /> Retake test
          </button>
        }
      />

      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        <Card>
          <h3 className="font-bold text-slate-800 mb-1">Your abilities</h3>
          <p className="text-xs text-slate-400 mb-4">Score = share of questions answered correctly.</p>
          <div className="space-y-4">
            {Object.keys(abilityLabels).map((k) => (
              <div key={k}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-700 font-medium">{abilityLabels[k]}</span>
                  <span className="font-bold text-primary-600">{r.correct[k]}/{r.total[k]} - {r.abilities[k]}%</span>
                </div>
                <ProgressBar value={r.abilities[k]} />
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h3 className="font-bold text-slate-800 mb-1">Your interests</h3>
          <p className="text-xs text-slate-400 mb-2">
            Top types: {topLetters.map((l) => interestLabels[l]).join(", ")}
          </p>
          <Radar values={r.interests} labels={interestLabels} />
          <p className="text-xs text-slate-500 mt-2 text-center">
            {topLetters.slice(0, 2).map((l) => `${interestLabels[l]}: ${hint[l]}`).join("  |  ")}
          </p>
        </Card>
      </div>

      <Card className="mb-6">
        <h3 className="font-bold text-slate-800 mb-4">Best-fit fields</h3>
        <div className="space-y-3">
          {r.fields.map((f, i) => (
            <div key={f.field} className="flex items-center gap-4">
              <span className="w-5 text-xs font-bold text-slate-400">{i + 1}</span>
              <span className="text-sm text-slate-700 w-48 shrink-0">{f.field}</span>
              <ProgressBar value={f.match_score} className="flex-1" />
              <span className="text-xs font-bold text-primary-600 w-10 text-right">{f.match_score}%</span>
            </div>
          ))}
        </div>
      </Card>

      <h3 className="font-bold text-slate-800 mb-3">Recommended careers</h3>
      <div className="grid md:grid-cols-2 gap-4 mb-6">
        {r.careers.map((c, i) => (
          <Card key={c.title} className="flex flex-col">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold text-slate-400">#{i + 1} - {c.category}</p>
                <h4 className="font-bold text-slate-800">{c.title}</h4>
              </div>
              <span className="text-lg font-extrabold text-primary-600">{c.match_score}%</span>
            </div>
            <ProgressBar value={c.match_score} className="my-3" />
            <ul className="text-xs text-slate-600 space-y-1 mb-3">
              {c.reasons.map((t) => <li key={t}>+ {t}</li>)}
              {c.grow_areas.length > 0 && (
                <li className="text-amber-700">Grow: {c.grow_areas.join(", ")}</li>
              )}
            </ul>
            <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500 mb-4">
              {c.job_growth && <span className="flex items-center gap-1"><TrendingUp size={12} /> {c.job_growth} growth</span>}
              {c.automation_risk != null && c.automation_risk !== "" && (
                <span className="flex items-center gap-1"><ShieldAlert size={12} /> {c.automation_risk}% automation risk</span>
              )}
            </div>
            <div className="mt-auto flex gap-2">
              <Link
                to={`/skill-gap?career=${encodeURIComponent(c.title)}`}
                className="flex items-center gap-1.5 text-xs font-semibold border border-slate-200 hover:border-slate-300 text-slate-700 px-3 py-2 rounded-lg"
              >
                <Compass size={13} /> Skill gap
              </Link>
            </div>
          </Card>
        ))}
      </div>

      <p className="text-xs text-slate-400 mb-6">
        This is guidance, not a diagnosis. Matches compare your scores with the typical ability and interest profile of each
        role - use them as a starting point alongside the skills-based Recommendations page.
      </p>

      {history.length > 1 && <History history={history} />}
    </Layout>
  );
}

function History({ history }) {
  return (
    <Card>
      <h3 className="font-bold text-slate-800 mb-3">Past attempts</h3>
      <div className="divide-y divide-slate-100">
        {history.map((h) => (
          <div key={h.id} className="py-2.5 flex items-center justify-between gap-4 text-sm">
            <span className="text-slate-500 w-40 shrink-0">{new Date(h.created_at + "Z").toLocaleDateString()}</span>
            <span className="font-bold text-primary-700 w-14">{h.interest_code}</span>
            <span className="text-slate-700 flex-1 truncate">
              {h.top_matches[0] ? `${h.top_matches[0].title} (${h.top_matches[0].match_score}%)` : "-"}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
