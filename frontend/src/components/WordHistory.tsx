import type { WordResult } from "../types";

interface Props {
  history: WordResult[];
}

export function WordHistory({ history }: Props) {
  if (history.length === 0) {
    return (
      <div className="text-center text-gray-400 text-sm py-8">
        Words you spell will appear here.
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
      {[...history].reverse().map((result, idx) => (
        <div
          key={idx}
          className={`flex items-center justify-between px-4 py-3 rounded-lg border ${
            result.correct
              ? "bg-green-50 border-green-200"
              : "bg-red-50 border-red-200"
          }`}
        >
          <div className="flex items-center gap-3">
            <span className="text-lg">{result.correct ? "✓" : "✗"}</span>
            <div>
              <span className="font-semibold text-gray-800">{result.word}</span>
              {!result.correct && result.attempt && (
                <span className="text-sm text-gray-500 ml-2">
                  (you spelled: <em>{result.attempt}</em>)
                </span>
              )}
            </div>
          </div>
          <span
            className={`text-xs font-medium px-2 py-1 rounded-full ${
              result.correct
                ? "bg-green-100 text-green-700"
                : "bg-red-100 text-red-700"
            }`}
          >
            {result.correct ? "Correct" : "Wrong"}
          </span>
        </div>
      ))}
    </div>
  );
}
