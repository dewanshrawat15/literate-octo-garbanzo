import type { GameState } from "../types";

interface Props {
  gameState: GameState;
}

export function ScoreDisplay({ gameState }: Props) {
  const { score, wordIndex, totalWords } = gameState;
  const attempted = gameState.history.length;

  return (
    <div className="flex items-center justify-center gap-6">
      <div className="text-center">
        <div className="text-3xl font-bold text-indigo-700">{score}</div>
        <div className="text-xs text-gray-500 uppercase tracking-wide">Correct</div>
      </div>
      <div className="w-px h-10 bg-gray-200" />
      <div className="text-center">
        <div className="text-3xl font-bold text-gray-700">{attempted}</div>
        <div className="text-xs text-gray-500 uppercase tracking-wide">Attempted</div>
      </div>
      <div className="w-px h-10 bg-gray-200" />
      <div className="text-center">
        <div className="text-3xl font-bold text-gray-400">{totalWords - wordIndex}</div>
        <div className="text-xs text-gray-500 uppercase tracking-wide">Remaining</div>
      </div>
    </div>
  );
}
