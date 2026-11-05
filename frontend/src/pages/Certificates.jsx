import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Award, Eye, GraduationCap } from "lucide-react";
import client from "../api/client";
import { Layout, Card, PageHeader, Loading } from "../components/Layout";
import Certificate from "../components/Certificate";

const fmt = (v) => {
  if (!v) return "";
  const d = new Date(String(v).includes("T") ? v : String(v).replace(" ", "T") + "Z");
  return Number.isNaN(d.getTime()) ? String(v).slice(0, 10) : d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
};

/** /certificates  -> all earned certificates;  /certificates/:courseId -> one, full size with download. */
export default function Certificates() {
  const { courseId } = useParams();
  const navigate = useNavigate();
  const [list, setList] = useState(null);
  const [one, setOne] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setError(""); setOne(null); setList(null);
    if (courseId) {
      client.get(`/certificates/${courseId}`)
        .then((r) => setOne(r.data.certificate))
        .catch((e) => setError(e.response?.data?.error || "Could not load the certificate"));
    } else {
      client.get("/certificates")
        .then((r) => setList(r.data.certificates))
        .catch(() => setError("Could not load your certificates"));
    }
  }, [courseId]);

  if (courseId) {
    return (
      <Layout>
        <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-primary-600 mb-3">
          <ArrowLeft size={15} /> Back
        </button>
        <PageHeader title="Your certificate" subtitle="Download it as a PDF or image and share it on LinkedIn or with your recruiters" />
        {error ? (
          <Card>
            <p className="text-sm text-slate-600">{error}</p>
            <Link to={`/courses/${courseId}/learn`} className="text-primary-600 text-sm font-semibold">← Back to the course</Link>
          </Card>
        ) : !one ? <Loading /> : (
          <div className="max-w-5xl"><Certificate certificate={one} /></div>
        )}
      </Layout>
    );
  }

  return (
    <Layout>
      <PageHeader title="My Certificates" subtitle="Every course you complete by passing its assessment earns a certificate" />
      {error && <Card><p className="text-sm text-red-600">{error}</p></Card>}
      {!list && !error && <Loading />}
      {list && list.length === 0 && (
        <Card className="text-center py-12">
          <div className="w-14 h-14 rounded-2xl bg-primary-50 text-primary-600 mx-auto flex items-center justify-center mb-3"><GraduationCap size={26} /></div>
          <p className="font-bold text-slate-800">No certificates yet</p>
          <p className="text-sm text-slate-500 mt-1">Watch a course, pass its assessment, and your certificate appears here.</p>
          <Link to="/courses" className="inline-block mt-4 bg-primary-600 hover:bg-primary-700 text-white text-sm font-semibold px-5 py-2.5 rounded-lg">Browse courses</Link>
        </Card>
      )}
      {list && list.length > 0 && (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5">
          {list.map((c) => (
            <Card key={c.cert_code} className="!p-4 flex flex-col">
              <Link to={`/certificates/${c.course_id}`} className="block rounded-xl overflow-hidden ring-1 ring-slate-200 hover:ring-primary-400 transition">
                <Certificate certificate={c} showActions={false} />
              </Link>
              <div className="mt-3 flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-slate-800 truncate flex items-center gap-1.5"><Award size={14} className="text-amber-500 shrink-0" />{c.course_title}</p>
                  <p className="text-xs text-slate-400 mt-0.5">Issued {fmt(c.issued_at)}{c.score_percent != null && ` · Score ${c.score_percent}%`}</p>
                </div>
                <Link to={`/certificates/${c.course_id}`} className="shrink-0 flex items-center gap-1 text-xs font-semibold text-primary-600 hover:underline"><Eye size={13} /> Open</Link>
              </div>
            </Card>
          ))}
        </div>
      )}
    </Layout>
  );
}