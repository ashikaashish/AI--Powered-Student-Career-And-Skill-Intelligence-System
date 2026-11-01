import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Sparkles, BrainCircuit } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import client from "../api/client";

export default function Signup() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [stream, setStream] = useState("");
  const [streamOptions, setStreamOptions] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { signup } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    client.get("/profile/streams").then((res) => setStreamOptions(res.data)).catch(() => {});
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await signup(name, email, password, stream);
      navigate("/profile");
    } catch (err) {
      setError(err.response?.data?.error || "Signup failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#eef2f9] flex items-center justify-center p-4 sm:p-6 lg:p-8">
      <div className="max-w-4xl w-full bg-white rounded-3xl shadow-2xl overflow-hidden grid grid-cols-1 md:grid-cols-2 border border-slate-200">
        <div className="bg-gradient-to-br from-[#121c3b] via-[#1a2b5b] to-[#213aa4] p-8 sm:p-10 text-white hidden md:flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-primary-500/20 rounded-full blur-3xl pointer-events-none" />

          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 backdrop-blur border border-white/15 text-xs font-semibold text-primary-300 mb-6">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Join CareerAI</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold leading-tight tracking-tight text-white mb-4">
              Start your journey to the right career
            </h1>
            <p className="text-sm text-slate-300 leading-relaxed font-normal">
              Get personalized recommendations, and close your skill gaps with
              guidance built from real job-market data.
            </p>
          </div>

          <div className="my-8 flex justify-center items-center">
            <div className="w-40 h-40 rounded-2xl bg-gradient-to-tr from-primary-600/40 to-indigo-500/30 border border-white/10 flex items-center justify-center backdrop-blur shadow-2xl">
              <BrainCircuit className="w-14 h-14 text-primary-300" />
            </div>
          </div>

       
        </div>

        <div className="p-8 sm:p-10 flex flex-col justify-center bg-white">
          <div className="mb-6 text-center">
            <h2 className="text-2xl font-bold text-slate-800 tracking-tight">Create your account</h2>
            <p className="text-xs text-slate-500 mt-1">It only takes a minute</p>
          </div>

          {error && (
            <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs font-semibold text-slate-600">Full name</label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter your name"
                className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Email address</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email"
                className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Password</label>
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 6 characters"
                className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">
                Your stream <span className="text-slate-400 font-normal">(optional)</span>
              </label>
              <select
                value={stream}
                onChange={(e) => setStream(e.target.value)}
                className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
              >
                <option value="">Select your stream...</option>
                {streamOptions.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
             
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary-600 hover:bg-primary-700 active:scale-[0.99] text-white font-semibold py-2.5 rounded-xl text-sm shadow-lg shadow-primary-500/25 transition-all disabled:opacity-60"
            >
              {loading ? "Creating account..." : "Sign up"}
            </button>
          </form>

          <p className="text-sm text-slate-500 mt-6 text-center">
            Already have an account?{" "}
            <Link to="/login" className="text-primary-600 font-semibold hover:underline">
              Login
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
