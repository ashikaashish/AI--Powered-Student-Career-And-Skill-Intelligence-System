import { useEffect, useState } from "react";
import {
  Save, Plus, ClipboardCheck, X, User as UserIcon, Upload, Check, Sparkles,
  GraduationCap, BadgeCheck, AlertCircle,
} from "lucide-react";
import client from "../api/client";
import { useAuth } from "../context/AuthContext";
import { Layout, Card, PageHeader, Loading } from "../components/Layout";
import SkillTestModal from "../components/SkillTestModal";

export default function Profile() {
  const { setUser } = useAuth();
  const [profile, setProfile] = useState(null);
  const [skills, setSkills] = useState([]);
  const [masterSkills, setMasterSkills] = useState([]);
  const [streamOptions, setStreamOptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newSkill, setNewSkill] = useState("");
  const [dirty, setDirty] = useState(false);
  const [testable, setTestable] = useState([]);
  const [testSkill, setTestSkill] = useState(null);
  const [message, setMessage] = useState("");

  const [resumeFile, setResumeFile] = useState(null);
  const [resumeText, setResumeText] = useState("");
  const [parsing, setParsing] = useState(false);
  const [parseError, setParseError] = useState("");
  const [extracted, setExtracted] = useState(null);
  const [selectedExtracted, setSelectedExtracted] = useState({});

  const load = () => {
    Promise.all([
      client.get("/profile/me"),
      client.get("/profile/skills/master"),
      client.get("/profile/streams"),
      client.get("/skill-test/available"),
    ]).then(([profRes, masterRes, streamRes, testRes]) => {
      setProfile(profRes.data.user);
      setSkills(profRes.data.skills);
      setMasterSkills(masterRes.data);
      setStreamOptions(streamRes.data);
      setTestable(testRes.data.skills);
      setDirty(false);
      setLoading(false);
    });
  };

  useEffect(load, []);

  const hasTest = (name) => Boolean(name);

  const handleProfileSave = async () => {
    setSaving(true);
    setMessage("");
    try {
      await client.put("/profile/me", profile);
      setUser((u) => ({ ...u, name: profile.name }));
      localStorage.setItem("careerai_user", JSON.stringify({ ...JSON.parse(localStorage.getItem("careerai_user")), name: profile.name }));
      setMessage("Profile updated successfully!");
    } finally {
      setSaving(false);
    }
  };

  const persistSkills = async () => {
    try {
      await client.put("/profile/skills", { skills });
      return true;
    } catch {
      setMessage("Couldn't save your skills. Please try again.");
      return false;
    }
  };

  const handleSkillsSave = async () => {
    setSaving(true);
    setMessage("");
    const ok = await persistSkills();
    if (ok) {
      setMessage("Skills updated successfully!");
      load();
    }
    setSaving(false);
  };

  const addSkill = () => {
    if (!newSkill) return;
    if (skills.some((s) => s.skill_name.toLowerCase() === newSkill.toLowerCase())) return;
    setSkills([...skills, { skill_name: newSkill, proficiency: 60, source: "manual", verified: 0 }]);
    setNewSkill("");
    setDirty(true);
  };

  const removeSkill = (name) => {
    setSkills(skills.filter((s) => s.skill_name !== name));
    setDirty(true);
  };

  const startTest = async (name) => {
    if (!name) return;
    setMessage("");
    if (dirty) {
      const ok = await persistSkills();
      if (!ok) return;
      setDirty(false);
    }
    setTestSkill(name);
  };

  const handleResumeParse = async () => {
    setParseError("");
    setExtracted(null);
    setParsing(true);
    try {
      let res;
      if (resumeFile) {
        const form = new FormData();
        form.append("resume", resumeFile);
        res = await client.post("/profile/resume-upload", form, {
          headers: { "Content-Type": "multipart/form-data" },
        });
      } else if (resumeText.trim()) {
        res = await client.post("/profile/resume-upload", { text: resumeText });
      } else {
        setParseError("Upload a file or paste resume text first.");
        setParsing(false);
        return;
      }
      setExtracted(res.data);
      const initial = {};
      res.data.extracted_skills.forEach((s) => (initial[s.skill_name] = true));
      setSelectedExtracted(initial);
    } catch (err) {
      const data = err.response?.data || {};
      const parts = [data.error || "Couldn't parse that resume."];
      if (Array.isArray(data.issues) && data.issues.length) {
        parts.push(data.issues.join(" "));
      }
      if (Array.isArray(data.tips) && data.tips.length) {
        parts.push("Tip: " + data.tips[0]);
      }
      setParseError(parts.join(" "));
    } finally {
      setParsing(false);
    }
  };

  const applyExtractedSkills = () => {
    if (!extracted) return;
    const toAdd = extracted.extracted_skills.filter((s) => selectedExtracted[s.skill_name]);
    const merged = [...skills];
    toAdd.forEach((s) => {
      const idx = merged.findIndex((m) => m.skill_name.toLowerCase() === s.skill_name.toLowerCase());
      if (idx >= 0) {
        if (!merged[idx].verified && merged[idx].source !== "course") {
          merged[idx] = { ...merged[idx], proficiency: s.proficiency };
        }
      } else {
        merged.push({ skill_name: s.skill_name, proficiency: s.proficiency, source: "manual", verified: 0 });
      }
    });
    setSkills(merged);
    setDirty(true);
    setExtracted(null);
    setResumeFile(null);
    setResumeText("");
    setMessage(`Added ${toAdd.length} skills from your resume. Click "Save Skills" to keep them, then take a test to verify them.`);
  };

  if (loading) return <Layout><Loading /></Layout>;

  const isSoft = (s) => masterSkills.find((m) => m.skill_name === s.skill_name)?.category === "soft";
  const technical = skills.filter((s) => !isSoft(s));
  const soft = skills.filter((s) => isSoft(s));
  const verifiedSet = new Set(skills.filter((s) => s.verified).map((s) => s.skill_name.toLowerCase()));

  return (
    <Layout>
      <PageHeader
        title="My Profile"
        subtitle="Update your information. Add your skills, then pass a short test to get a Verified badge on each one."
      />

      {message && (
        <div className="mb-4 text-sm text-teal-700 bg-teal-50 border border-teal-100 rounded-lg px-3 py-2">
          {message}
        </div>
      )}

      <div className="grid md:grid-cols-3 gap-6">
        <Card className="md:col-span-1 h-fit">
          <div className="flex flex-col items-center text-center">
            <div className="w-24 h-24 rounded-full bg-primary-100 flex items-center justify-center mb-3">
              <UserIcon size={40} className="text-primary-500" />
            </div>
            <h3 className="font-bold text-slate-800">{profile.name}</h3>
            <p className="text-sm text-slate-500">{profile.email}</p>
          </div>

          <div className="mt-6 space-y-3">
            <Field label="Name" value={profile.name} onChange={(v) => setProfile({ ...profile, name: v })} />
            <Field label="Education" value={profile.education || ""} onChange={(v) => setProfile({ ...profile, education: v })} />
            <div>
              <label className="text-xs font-medium text-slate-500">Stream</label>
              <select
                value={profile.stream || ""}
                onChange={(e) => setProfile({ ...profile, stream: e.target.value })}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
              >
                <option value="">Not set</option>
                {streamOptions.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
            <Field label="Year" value={profile.year || ""} onChange={(v) => setProfile({ ...profile, year: v })} />
            <Field label="Location" value={profile.location || ""} onChange={(v) => setProfile({ ...profile, location: v })} />
            <div>
              <label className="text-xs font-medium text-slate-500">Bio</label>
              <textarea
                value={profile.bio || ""}
                onChange={(e) => setProfile({ ...profile, bio: e.target.value })}
                rows={3}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>

          <button
            onClick={handleProfileSave}
            disabled={saving}
            className="mt-4 w-full flex items-center justify-center gap-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-semibold py-2.5 rounded-lg transition-colors disabled:opacity-60"
          >
            <Save size={15} /> Save Profile
          </button>

          <ResumeUploadPanel
            resumeFile={resumeFile}
            setResumeFile={setResumeFile}
            resumeText={resumeText}
            setResumeText={setResumeText}
            parsing={parsing}
            parseError={parseError}
            extracted={extracted}
            selectedExtracted={selectedExtracted}
            setSelectedExtracted={setSelectedExtracted}
            hasTest={hasTest}
            verifiedSet={verifiedSet}
            onVerify={startTest}
            onParse={handleResumeParse}
            onApply={applyExtractedSkills}
          />
        </Card>

        <Card className="md:col-span-2">
          <h3 className="font-bold text-slate-800 mb-1">Skills</h3>
          <p className="text-xs text-slate-500 mb-4">
            Add a skill, then take its test to prove it. Skills you earn by passing course assessments appear here automatically.
          </p>

          <div className="flex flex-wrap gap-2 mb-4">
            <select
              value={newSkill}
              onChange={(e) => setNewSkill(e.target.value)}
              className="flex-1 min-w-[200px] rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">Select a skill to add...</option>
              {masterSkills
                .filter((m) => !skills.some((s) => s.skill_name.toLowerCase() === m.skill_name.toLowerCase()))
                .map((m) => (
                  <option key={m.skill_name} value={m.skill_name}>
                    {m.skill_name} ({m.category}) - test available
                  </option>
                ))}
            </select>
            <button
              onClick={addSkill}
              disabled={!newSkill}
              className="flex items-center gap-1 bg-primary-50 text-primary-700 px-3 py-2 rounded-lg text-sm font-semibold hover:bg-primary-100 disabled:opacity-50"
            >
              <Plus size={15} /> Add
            </button>
            <button
              onClick={() => { startTest(newSkill); setNewSkill(""); }}
              disabled={!newSkill}
              title="Pass the test to add and verify this skill"
              className="flex items-center gap-1 bg-teal-50 text-teal-700 px-3 py-2 rounded-lg text-sm font-semibold hover:bg-teal-100 disabled:opacity-50"
            >
              <ClipboardCheck size={15} /> Take test
            </button>
          </div>

          {skills.length === 0 && (
            <p className="text-sm text-slate-400 mb-4">No skills yet. Add one above, or take a test to add a verified skill.</p>
          )}
          <SkillGroup title="Technical Skills" items={technical} onRemove={removeSkill} onVerify={startTest} hasTest={hasTest} />
          <SkillGroup title="Soft Skills" items={soft} onRemove={removeSkill} onVerify={startTest} hasTest={hasTest} />

          <div className="mt-2 flex items-center gap-3">
            <button
              onClick={handleSkillsSave}
              disabled={saving || !dirty}
              className="flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-semibold px-4 py-2.5 rounded-lg transition-colors disabled:opacity-60"
            >
              <Save size={15} /> Save Skills
            </button>
            {dirty && <span className="text-xs text-amber-600">You have unsaved changes</span>}
          </div>
        </Card>
      </div>

      {testSkill && (
        <SkillTestModal
          skill={testSkill}
          onClose={() => setTestSkill(null)}
          onPassed={load}
        />
      )}
    </Layout>
  );
}

function Field({ label, value, onChange, placeholder }) {
  return (
    <div>
      <label className="text-xs font-medium text-slate-500">{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
      />
    </div>
  );
}

function SkillGroup({ title, items, onRemove, onVerify, hasTest }) {
  if (!items.length) return null;
  return (
    <div className="mb-5">
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">{title}</p>
      <ul className="flex flex-wrap gap-2">
        {items.map((s) => (
          <li
            key={s.skill_name}
            className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 pl-3 pr-2 py-1.5 text-sm text-slate-700"
          >
            <span>{s.skill_name}</span>
            {s.source === "course" ? (
              <span
                title={s.course_title ? `Verified by passing the "${s.course_title}" assessment` : "Verified by passing a course assessment"}
                className="inline-flex items-center gap-1 text-[10px] font-bold text-teal-700 bg-teal-50 border border-teal-100 rounded-full px-1.5 py-0.5"
              >
                <GraduationCap size={10} /> Assessment passed
              </span>
            ) : (
              <>
                {s.verified ? (
                  <span
                    title="Verified by passing a skill test"
                    className="inline-flex items-center gap-1 text-[10px] font-bold text-teal-700 bg-teal-50 border border-teal-100 rounded-full px-1.5 py-0.5"
                  >
                    <BadgeCheck size={10} /> Verified{s.verified_score ? ` - ${s.verified_score}%` : ""}
                  </span>
                ) : (
                  <button
                    onClick={() => onVerify(s.skill_name)}
                    title="Take the test to verify this skill"
                    className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-700 bg-amber-50 border border-amber-100 rounded-full px-1.5 py-0.5 hover:bg-amber-100"
                  >
                    <AlertCircle size={10} /> Not verified - take test
                  </button>
                )}
                <button onClick={() => onRemove(s.skill_name)} className="text-slate-300 hover:text-red-500" aria-label={`Remove ${s.skill_name}`}>
                  <X size={14} />
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ResumeUploadPanel({
  resumeFile, setResumeFile, resumeText, setResumeText,
  parsing, parseError, extracted, selectedExtracted, setSelectedExtracted,
  hasTest, verifiedSet, onVerify, onParse, onApply,
}) {
  const toggleSkill = (name) =>
    setSelectedExtracted((prev) => ({ ...prev, [name]: !prev[name] }));

  return (
    <div className="mt-6 pt-5 border-t border-slate-100">
      <h4 className="font-semibold text-slate-800 text-sm flex items-center gap-2 mb-1">
        <Upload size={15} /> Import skills from ATS resume
      </h4>
      <p className="text-xs text-slate-500 mb-3">
        Upload a text-based ATS-friendly .pdf, .docx, or .txt with headings like Experience, Education, and Skills.
        Designed, Canva, scanned, or image resumes are rejected and skills will not be extracted.
        Imported skills are marked "Not verified" until you pass their test.
      </p>

      <input
        type="file"
        accept=".pdf,.docx,.txt"
        onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
        className="w-full text-xs text-slate-600 mb-2 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
      />

      <textarea
        value={resumeText}
        onChange={(e) => setResumeText(e.target.value)}
        placeholder="...or paste ATS-friendly resume text here"
        rows={3}
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary-500 mb-2"
      />

      {parseError && <p className="text-xs text-red-600 mb-2">{parseError}</p>}

      <button
        onClick={onParse}
        disabled={parsing}
        className="w-full flex items-center justify-center gap-2 bg-gray-900 hover:bg-gray-800 text-white text-xs font-semibold py-2 rounded-lg transition-colors disabled:opacity-60"
      >
        <Sparkles size={13} /> {parsing ? "Checking ATS & extracting..." : "Extract skills"}
      </button>

      {extracted && (
        <div className="mt-4">
          {extracted.ats_friendly && (
            <p className="text-xs text-teal-700 mb-2">
              ATS-friendly resume detected{typeof extracted.ats_score === "number" ? ` (score ${extracted.ats_score}/100)` : ""}.
            </p>
          )}
          {extracted.suggested_career_family && (
            <p className="text-xs text-slate-600 mb-2">
              Looks closest to: <span className="font-semibold text-primary-700">{extracted.suggested_career_family}</span>
            </p>
          )}
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
            Found {extracted.extracted_skills.length} skills - uncheck any that don't apply
          </p>
          <div className="max-h-56 overflow-y-auto space-y-1.5 pr-1">
            {extracted.extracted_skills.map((s) => {
              const done = verifiedSet.has(s.skill_name.toLowerCase());
              return (
                <div key={s.skill_name} className="flex items-center gap-2 text-xs text-slate-700">
                  <label className="flex items-center gap-2 flex-1 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={!!selectedExtracted[s.skill_name]}
                      onChange={() => toggleSkill(s.skill_name)}
                      className="accent-primary-600"
                    />
                    <span className="flex-1">{s.skill_name}</span>
                  </label>
                  {done ? (
                    <span className="text-teal-700 font-semibold">Verified</span>
                  ) : (
                    <button
                      onClick={() => onVerify(s.skill_name)}
                      className="text-primary-700 font-semibold bg-primary-50 hover:bg-primary-100 rounded-md px-2 py-1"
                    >
                      Take test
                    </button>
                  )}
                </div>
              );
            })}
          </div>
          <button
            onClick={onApply}
            className="mt-3 w-full flex items-center justify-center gap-2 bg-primary-600 hover:bg-primary-700 text-white text-xs font-semibold py-2 rounded-lg transition-colors"
          >
            <Check size={13} /> Add selected skills to profile
          </button>
        </div>
      )}
    </div>
  );
}