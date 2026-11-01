import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Sparkles, BrainCircuit, UserCheck, ShieldCheck } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const [email, setEmail] = useState("ananya@gmail.com");
  const [password, setPassword] = useState("password123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = await login(email, password);
      navigate(user.role === "admin" ? "/admin" : "/dashboard");
    } catch (err) {
      setError(err.response?.data?.error || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = (which) => {
    if (which === "student") {
      setEmail("ananya@gmail.com");
      setPassword("password123");
    } else {
      setEmail("admin@careerai.com");
      setPassword("admin123");
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#eef2f9] flex items-center justify-center p-4 sm:p-6 lg:p-8">
      <div className="max-w-4xl w-full bg-white rounded-3xl shadow-2xl overflow-hidden grid grid-cols-1 md:grid-cols-2 border border-slate-200">
        {/* Left: Branding */}
        <div className="bg-gradient-to-br from-[#121c3b] via-[#1a2b5b] to-[#213aa4] p-8 sm:p-10 text-white hidden md:flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-primary-500/20 rounded-full blur-3xl pointer-events-none" />

          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 backdrop-blur border border-white/15 text-xs font-semibold text-primary-300 mb-6">
              <Sparkles className="w-3.5 h-3.5" />
              <span>AI Career Intelligence</span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold leading-tight tracking-tight text-white mb-4">
              CareerAI — AI-Powered Career Guidance For Your Future
            </h1>

            <p className="text-sm text-slate-300 leading-relaxed font-normal">
              Real job-market data, ML career predictions, and NLP skill-gap analysis
              — all in one platform.
            </p>
          </div>

          <div className="my-8 flex justify-center items-center">
            <div className="w-44 h-44 rounded-2xl bg-gradient-to-tr from-primary-600/40 to-indigo-500/30 border border-white/10 flex items-center justify-center backdrop-blur shadow-2xl p-4 text-center">
              <div className="space-y-2">
                <div className="w-16 h-16 mx-auto rounded-xl bg-white/10 flex items-center justify-center text-primary-300 shadow-inner">
                  <BrainCircuit className="w-9 h-9" />
                </div>
                <p className="text-xs font-bold text-white">Real Job-Postings Data</p>
               
              </div>
            </div>
          </div>

       
        </div>

        {/* Right: Form */}
        <div className="p-8 sm:p-10 flex flex-col justify-center bg-white">
          <div className="mb-6 text-center">
            <h2 className="text-2xl font-bold text-slate-800 tracking-tight">Welcome Back!</h2>
            <p className="text-xs text-slate-500 mt-1">Login to continue your career journey</p>
          </div>

          {error && (
            <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
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
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary-600 hover:bg-primary-700 active:scale-[0.99] text-white font-semibold py-2.5 rounded-xl text-sm shadow-lg shadow-primary-500/25 transition-all disabled:opacity-60"
            >
              {loading ? "Logging in..." : "Login"}
            </button>
          </form>

      

          <p className="text-sm text-slate-500 mt-6 text-center">
            Don't have an account?{" "}
            <Link to="/signup" className="text-primary-600 font-semibold hover:underline">
              Sign up
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
