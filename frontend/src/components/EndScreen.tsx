import type { GameState } from "../types";
import { WordHistory } from "./WordHistory";

interface Props {
  gameState: GameState;
  onPlayAgain: () => void;
}

function getScoreEmoji(score: number, total: number): string {
  const ratio = score / total;
  if (ratio === 1) return "🏆";
  if (ratio >= 0.8) return "🌟";
  if (ratio >= 0.6) return "👍";
  if (ratio >= 0.4) return "📚";
  return "💪";
}

function getScoreMessage(score: number, total: number): string {
  const ratio = score / total;
  if (ratio === 1) return "Perfect score! Outstanding!";
  if (ratio >= 0.8) return "Excellent work!";
  if (ratio >= 0.6) return "Good job!";
  if (ratio >= 0.4) return "Keep practicing!";
  return "Better luck next time!";
}

export function EndScreen({ gameState, onPlayAgain }: Props) {
  const { score, totalWords, history } = gameState;
  const emoji = getScoreEmoji(score, totalWords);
  const message = getScoreMessage(score, totalWords);

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 to-purple-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 max-w-lg w-full text-center">
        {/* Emoji + score */}
        <div className="text-6xl mb-3">{emoji}</div>
        <h1 className="text-3xl font-bold text-indigo-700 mb-1">Game Over!</h1>
        <p className="text-gray-500 mb-6 text-lg">{message}</p>

        {/* Big score */}
        <div className="bg-indigo-50 rounded-2xl p-6 mb-6">
          <div className="text-6xl font-bold text-indigo-700">
            {score}
            <span className="text-3xl text-indigo-400">/{totalWords}</span>
          </div>
          <div className="text-gray-500 text-sm mt-1">words spelled correctly</div>
        </div>

        {/* Word breakdown */}
        {history.length > 0 && (
          <div className="text-left mb-6">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
              Word Summary
            </h2>
            <WordHistory history={history} />
          </div>
        )}

        <button
          onClick={onPlayAgain}
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-4 px-8 rounded-xl text-lg transition-colors duration-200"
        >
          Play Again
        </button>
      </div>
    </div>
  );
}
