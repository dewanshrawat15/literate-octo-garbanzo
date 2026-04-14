import { useEffect, useState } from "react";
import type { MetricsData } from "../types";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";

interface Props {
  token: string;
  onBack: () => void;
}

export function MetricsScreen({ token, onBack }: Props) {
  const [data, setData] = useState<MetricsData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BACKEND_URL}/admin/metrics`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body?.detail ?? `Error ${res.status}`);
        }
        return res.json() as Promise<MetricsData>;
      })
      .then((d) => setData(d))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load metrics"))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 to-purple-50 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold text-indigo-700">Admin Metrics</h1>
          <button onClick={onBack} className="text-sm text-gray-500 hover:underline">
            Back
          </button>
        </div>

        {loading && (
          <div className="text-center text-gray-500 py-20">Loading metrics...</div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {data && (
          <div className="space-y-6">
            {/* Top stat row */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { label: "Total Users", value: data.total_users },
                { label: "Total Sessions", value: data.total_sessions },
                { label: "Completed Sessions", value: data.completed_sessions },
                {
                  label: "Avg Score",
                  value: data.avg_score_pct !== null ? `${data.avg_score_pct}%` : "—",
                },
              ].map((s) => (
                <div key={s.label} className="bg-white rounded-xl shadow p-5 text-center">
                  <p className="text-3xl font-bold text-indigo-700">{s.value}</p>
                  <p className="text-sm text-gray-500 mt-1">{s.label}</p>
                </div>
              ))}
            </div>

            {/* Spelling accuracy */}
            <div className="bg-white rounded-xl shadow p-6">
              <h2 className="text-lg font-semibold text-gray-800 mb-4">Spelling Accuracy</h2>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-2xl font-bold text-gray-800">{data.spelling_stats.total_attempts}</p>
                  <p className="text-sm text-gray-500">Total Attempts</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-green-600">{data.spelling_stats.correct}</p>
                  <p className="text-sm text-gray-500">Correct</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-indigo-600">{data.spelling_stats.accuracy_pct}%</p>
                  <p className="text-sm text-gray-500">Accuracy</p>
                </div>
              </div>
            </div>

            {/* Speed distribution + Command usage side by side */}
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="bg-white rounded-xl shadow p-6">
                <h2 className="text-lg font-semibold text-gray-800 mb-4">Speed Distribution</h2>
                <div className="space-y-2">
                  {(["slow", "normal", "fast"] as const).map((speed) => (
                    <div key={speed} className="flex items-center justify-between">
                      <span className="capitalize text-gray-600">{speed}</span>
                      <span className="font-semibold text-gray-800">
                        {data.speed_distribution[speed] ?? 0}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white rounded-xl shadow p-6">
                <h2 className="text-lg font-semibold text-gray-800 mb-4">Command Usage</h2>
                <div className="space-y-2">
                  {(["repeat", "skip", "quit"] as const).map((cmd) => (
                    <div key={cmd} className="flex items-center justify-between">
                      <span className="capitalize text-gray-600">{cmd}</span>
                      <span className="font-semibold text-gray-800">{data.command_usage[cmd]}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Top 5 hard words */}
            {data.top_hard_words.length > 0 && (
              <div className="bg-white rounded-xl shadow p-6">
                <h2 className="text-lg font-semibold text-gray-800 mb-4">Top 5 Hardest Words</h2>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="pb-2">Word</th>
                      <th className="pb-2 text-right">Attempts</th>
                      <th className="pb-2 text-right">Correct</th>
                      <th className="pb-2 text-right">Accuracy</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_hard_words.map((w) => (
                      <tr key={w.word} className="border-b last:border-0">
                        <td className="py-2 font-medium text-gray-800">{w.word}</td>
                        <td className="py-2 text-right text-gray-600">{w.attempts}</td>
                        <td className="py-2 text-right text-gray-600">{w.correct_count}</td>
                        <td className="py-2 text-right text-red-600 font-semibold">{w.accuracy_pct}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Unhandled interruptions */}
            <div className="bg-white rounded-xl shadow p-6">
              <h2 className="text-lg font-semibold text-gray-800 mb-1">Unhandled Interruptions</h2>
              <p className="text-3xl font-bold text-orange-500 mb-4">{data.unhandled_count}</p>
              {data.top_unhandled.length > 0 && (
                <>
                  <p className="text-sm font-semibold text-gray-600 mb-2">Top phrases</p>
                  <ul className="space-y-1">
                    {data.top_unhandled.map((u) => (
                      <li key={u.raw_text} className="flex justify-between text-sm">
                        <span className="text-gray-700 truncate max-w-xs">"{u.raw_text}"</span>
                        <span className="text-gray-500 ml-4 shrink-0">{u.cnt}x</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
