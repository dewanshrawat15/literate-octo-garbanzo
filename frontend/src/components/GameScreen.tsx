import type { GameState, TransportStatus } from "../types";
import { ScoreDisplay } from "./ScoreDisplay";
import { StatusIndicator } from "./StatusIndicator";
import { WordHistory } from "./WordHistory";

interface Props {
  gameState: GameState;
  transport: TransportStatus;
  onEndGame: () => void;
}

export function GameScreen({ gameState, transport, onEndGame }: Props) {
  const { wordIndex, totalWords } = gameState;

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 to-purple-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 max-w-lg w-full">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🐝</span>
            <h1 className="text-xl font-bold text-indigo-700">Spell Bee</h1>
          </div>
          <div className="text-sm text-gray-500 font-medium">
            Word {Math.min(wordIndex, totalWords)} of {totalWords}
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-full bg-gray-100 rounded-full h-2 mb-6">
          <div
            className="bg-indigo-500 h-2 rounded-full transition-all duration-500"
            style={{ width: `${(gameState.history.length / totalWords) * 100}%` }}
          />
        </div>

        {/* Score */}
        <div className="mb-6">
          <ScoreDisplay gameState={gameState} />
        </div>

        {/* Status */}
        <div className="flex justify-center mb-8">
          <StatusIndicator gamePhase={gameState.phase} transport={transport} />
        </div>

        {/* Audio visualizer hint */}
        {transport.userSpeaking && (
          <div className="flex justify-center gap-1 mb-6">
            {[...Array(7)].map((_, i) => (
              <div
                key={i}
                className="w-1.5 bg-green-400 rounded-full animate-pulse"
                style={{
                  height: `${12 + Math.random() * 20}px`,
                  animationDelay: `${i * 80}ms`,
                }}
              />
            ))}
          </div>
        )}

        {/* Word history */}
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            History
          </h2>
          <WordHistory history={gameState.history} />
        </div>

        {/* End game button */}
        <button
          onClick={onEndGame}
          className="w-full mt-2 bg-gray-100 hover:bg-gray-200 text-gray-600 font-medium py-3 px-6 rounded-xl transition-colors duration-200 text-sm"
        >
          End Game
        </button>
      </div>
    </div>
  );
}
