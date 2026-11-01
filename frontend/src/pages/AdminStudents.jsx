
import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Trash2, Users } from "lucide-react";
import client from "../api/client";
import { Layout, Card, PageHeader, Loading } from "../components/Layout";

export default function AdminStudents() {
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState(null);

  const loadStudents = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await client.get("/admin/students");
      const data = response.data;

      if (!Array.isArray(data)) {
        throw new Error(data?.error || "Invalid student data received.");
      }

      setStudents(data);
    } catch (err) {
      setError(
        err.response?.data?.error ||
          err.message ||
          "Unable to load students. Please check the backend."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStudents();
  }, [loadStudents]);

  const handleDelete = async (student) => {
    if (!window.confirm(`Delete student ${student.name}?`)) return;

    setDeletingId(student.id);
    setError("");

    try {
      await client.delete(`/admin/students/${student.id}`);
      await loadStudents();
    } catch (err) {
      setError(
        err.response?.data?.error || "Failed to delete the student."
      );
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <Layout>
      <PageHeader
        title="Manage Students"
        subtitle="View and manage registered student details"
      />

      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-slate-600">
          <Users size={20} />
          <span>
            Total students: <strong>{students.length}</strong>
          </span>
        </div>

        <button
          type="button"
          onClick={loadStudents}
          disabled={loading}
          className="flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-50"
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      {error && (
        <div
          role="alert"
          className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      <Card className="overflow-hidden p-0">
        {loading ? (
          <div className="p-8 text-center">
            <Loading />
            <p className="mt-3 text-sm text-slate-500">
              Loading student details...
            </p>
          </div>
        ) : students.length === 0 ? (
          <div className="p-10 text-center">
            <Users size={36} className="mx-auto mb-3 text-slate-400" />
            <h3 className="font-semibold text-slate-700">
              No students found
            </h3>
            <p className="mt-1 text-sm text-slate-500">
              Register a student or check the backend database and student
              role.
            </p>
            <button
              type="button"
              onClick={loadStudents}
              className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white"
            >
              Try again
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[850px] text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3 text-left">Name</th>
                  <th className="px-5 py-3 text-left">Email</th>
                  <th className="px-5 py-3 text-left">Education</th>
                  <th className="px-5 py-3 text-left">Stream</th>
                  <th className="px-5 py-3 text-left">Year</th>
                  <th className="px-5 py-3 text-left">Joined</th>
                  <th className="px-5 py-3 text-right">Action</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-slate-100">
                {students.map((student) => (
                  <tr
                    key={student.id}
                    className="hover:bg-slate-50"
                  >
                    <td className="px-5 py-3 font-medium text-slate-800">
                      {student.name || "-"}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {student.email || "-"}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {student.education || "-"}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {student.stream || "-"}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {student.year || "-"}
                    </td>
                    <td className="px-5 py-3 text-slate-500">
                      {student.created_at
                        ? new Date(student.created_at).toLocaleDateString()
                        : "-"}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => handleDelete(student)}
                        disabled={deletingId === student.id}
                        title="Delete student"
                        aria-label={`Delete ${student.name}`}
                        className="rounded p-2 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </Layout>
  );
}
