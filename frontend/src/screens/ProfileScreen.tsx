import { useState } from "react";
import type { SpellingSpeed, UserProfile } from "../types";

interface SpeedOption {
  value: SpellingSpeed;
  label: string;
  description: string;
}

const SPEED_OPTIONS: SpeedOption[] = [
  {
    value: "slow",
    label: "Slow",
    description: "~2.5s pause between letters — comfortable for careful spellers",
  },
  {
    value: "normal",
    label: "Normal",
    description: "~1.8s pause — works well for most words",
  },
  {
    value: "fast",
    label: "Fast",
    description: "~1s pause — for confident, quick spellers",
  },
];

interface Props {
  user: UserProfile;
  onUpdateSpeed: (speed: SpellingSpeed) => Promise<boolean>;
  onBack: () => void;
  error: string | null;
  loading: boolean;
}

export function ProfileScreen({ user, onUpdateSpeed, onBack, error, loading }: Props) {
  const [selected, setSelected] = useState<SpellingSpeed>(user.spelling_speed);
  const [saved, setSaved] = useState(false);

  async function handleSave() {
    const ok = await onUpdateSpeed(selected);
    if (ok) {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 to-purple-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-10 max-w-md w-full">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold text-indigo-700">My Profile</h1>
          <button onClick={onBack} className="text-sm text-gray-500 hover:underline">
            Back
          </button>
        </div>

        <div className="mb-6">
          <p className="text-sm text-gray-500 mb-1">Username</p>
          <p className="font-medium text-gray-800">{user.username}</p>
        </div>

        <div className="mb-8">
          <p className="text-sm font-semibold text-gray-700 mb-3">Spelling Speed</p>
          <div className="space-y-3">
            {SPEED_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={`flex items-start gap-3 p-4 rounded-xl border-2 cursor-pointer transition-colors ${
                  selected === opt.value
                    ? "border-indigo-500 bg-indigo-50"
                    : "border-gray-200 hover:border-indigo-300"
                }`}
              >
                <input
                  type="radio"
                  name="speed"
                  value={opt.value}
                  checked={selected === opt.value}
                  onChange={() => setSelected(opt.value)}
                  className="mt-0.5 accent-indigo-600"
                />
                <div>
                  <p className="font-medium text-gray-800">{opt.label}</p>
                  <p className="text-sm text-gray-500">{opt.description}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {saved && (
          <div className="mb-4 bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-3 text-sm">
            Speed updated!
          </div>
        )}

        <button
          onClick={handleSave}
          disabled={loading}
          className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white font-semibold py-3 px-6 rounded-xl transition-colors"
        >
          {loading ? "Saving..." : "Save"}
        </button>
      </div>
    </div>
  );
}
