interface Props {
  onStart: () => void;
  isConnecting: boolean;
  error: string | null;
  username?: string;
  isAdmin?: boolean;
  onLogout?: () => void;
  onGoToProfile?: () => void;
  onGoToMetrics?: () => void;
}

export function StartScreen({ onStart, isConnecting, error, username, isAdmin, onLogout, onGoToProfile, onGoToMetrics }: Props) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 to-purple-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-10 max-w-md w-full text-center">
        {username && (
          <div className="flex items-center justify-between mb-4 text-sm text-gray-500">
            <span>Hi, <span className="font-medium text-gray-700">{username}</span></span>
            <div className="flex items-center gap-3">
              {onGoToProfile && (
                <button onClick={onGoToProfile} className="text-indigo-600 hover:underline">
                  My Profile
                </button>
              )}
              {isAdmin && onGoToMetrics && (
                <button onClick={onGoToMetrics} className="text-purple-600 hover:underline">
                  Admin Metrics
                </button>
              )}
              {onLogout && (
                <button onClick={onLogout} className="text-gray-500 hover:underline">
                  Sign out
                </button>
              )}
            </div>
          </div>
        )}
        <div className="text-6xl mb-4">🐝</div>
        <h1 className="text-4xl font-bold text-indigo-700 mb-2">Spell Bee</h1>
        <p className="text-gray-500 mb-8 text-lg">
          Listen to the word, then spell it out loud — letter by letter.
        </p>

        <div className="text-left bg-indigo-50 rounded-xl p-5 mb-8 space-y-2 text-sm text-gray-600">
          <p className="font-semibold text-indigo-700 text-base mb-3">How to play</p>
          <p>1. Click <strong>Start Game</strong> and allow microphone access.</p>
          <p>2. The bot will say a word and use it in a sentence.</p>
          <p>3. Spell the word aloud, letter by letter (e.g. "C, A, T").</p>
          <p>4. The bot will tell you if you're correct and move to the next word.</p>
          <p className="pt-1">You'll get <strong>10 words</strong> per game.</p>
        </div>

        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
            {error}
          </div>
        )}

        <button
          onClick={onStart}
          disabled={isConnecting}
          className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white font-semibold py-4 px-8 rounded-xl text-lg transition-colors duration-200 flex items-center justify-center gap-3"
        >
          {isConnecting ? (
            <>
              <svg className="animate-spin h-5 w-5 text-white" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Connecting...
            </>
          ) : (
            <>
              <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clipRule="evenodd" />
              </svg>
              Start Game
            </>
          )}
        </button>
      </div>
    </div>
  );
}
