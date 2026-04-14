import { useState } from "react";
import type { SpellingSpeed } from "../types";

interface SpeedOption {
  value: SpellingSpeed;
  label: string;
  description: string;
  example: string;
}

const SPEED_OPTIONS: SpeedOption[] = [
  {
    value: "slow",
    label: "Slow",
    description: "I like to think carefully between letters",
    example: "Comfortable with ~2.5s pauses (e.g. P ... N ... E ... U ...)",
  },
  {
    value: "normal",
    label: "Normal",
    description: "I spell at a comfortable pace",
    example: "Comfortable with ~1.8s pauses — works for most words",
  },
  {
    value: "fast",
    label: "Fast",
    description: "I know my words and spell quickly",
    example: "Comfortable with ~1s pauses — for confident, quick spellers",
  },
];

interface SignupScreenProps {
  onSignup: (
    username: string,
    password: string,
    speed: SpellingSpeed
  ) => Promise<boolean>;
  onGoToLogin: () => void;
  error: string | null;
  loading: boolean;
}

export function SignupScreen({
  onSignup,
  onGoToLogin,
  error,
  loading,
}: SignupScreenProps) {
  const [step, setStep] = useState<"credentials" | "speed">("credentials");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [speed, setSpeed] = useState<SpellingSpeed>("normal");

  const handleCredentialsNext = (e: React.FormEvent) => {
    e.preventDefault();
    setStep("speed");
  };

  const handleSpeedSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSignup(username, password, speed);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
        {step === "credentials" ? (
          <>
            <div className="text-center mb-8">
              <h1 className="text-3xl font-bold text-gray-900">Spell Bee</h1>
              <p className="text-gray-500 mt-1">Create your account</p>
            </div>

            <form onSubmit={handleCredentialsNext} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="Choose a username (3–50 chars)"
                  required
                  minLength={3}
                  maxLength={50}
                  autoComplete="username"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="At least 8 characters"
                  required
                  minLength={8}
                  autoComplete="new-password"
                />
              </div>

              {error && (
                <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={!username || !password || password.length < 8}
                className="w-full bg-indigo-600 text-white rounded-lg py-2.5 font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Next: Set Spelling Speed
              </button>
            </form>

            <div className="mt-6 text-center">
              <p className="text-sm text-gray-500">
                Already have an account?{" "}
                <button
                  onClick={onGoToLogin}
                  className="text-indigo-600 font-medium hover:underline"
                >
                  Sign in
                </button>
              </p>
            </div>
          </>
        ) : (
          <>
            <div className="text-center mb-6">
              <h2 className="text-2xl font-bold text-gray-900">
                How fast do you spell?
              </h2>
              <p className="text-gray-500 mt-2 text-sm">
                This sets how long the bot waits after each letter before it
                decides you&apos;re done spelling. Try thinking through{" "}
                <span className="font-medium text-indigo-600">
                  &quot;necessary&quot;
                </span>{" "}
                — how much time do you need between letters?
              </p>
            </div>

            <form onSubmit={handleSpeedSubmit} className="space-y-3">
              {SPEED_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className={`block border-2 rounded-xl p-4 cursor-pointer transition-colors ${
                    speed === opt.value
                      ? "border-indigo-500 bg-indigo-50"
                      : "border-gray-200 hover:border-indigo-300"
                  }`}
                >
                  <input
                    type="radio"
                    name="speed"
                    value={opt.value}
                    checked={speed === opt.value}
                    onChange={() => setSpeed(opt.value)}
                    className="sr-only"
                  />
                  <div className="flex items-start gap-3">
                    <div
                      className={`mt-0.5 w-4 h-4 rounded-full border-2 flex-shrink-0 ${
                        speed === opt.value
                          ? "border-indigo-600 bg-indigo-600"
                          : "border-gray-400"
                      }`}
                    />
                    <div>
                      <p className="font-semibold text-gray-900">{opt.label}</p>
                      <p className="text-sm text-gray-600">{opt.description}</p>
                      <p className="text-xs text-gray-400 mt-0.5">{opt.example}</p>
                    </div>
                  </div>
                </label>
              ))}

              {error && (
                <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setStep("credentials")}
                  className="flex-1 border border-gray-300 text-gray-700 rounded-lg py-2.5 font-medium hover:bg-gray-50 transition-colors"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="flex-1 bg-indigo-600 text-white rounded-lg py-2.5 font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? "Creating account..." : "Create Account"}
                </button>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
