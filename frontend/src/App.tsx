import { useSpellBeeClient } from "./hooks/useSpellBeeClient";
import { StartScreen } from "./components/StartScreen";
import { GameScreen } from "./components/GameScreen";
import { EndScreen } from "./components/EndScreen";

export default function App() {
  const { gameState, transport, error, startGame, endGame } = useSpellBeeClient();

  const { phase } = gameState;

  if (phase === "idle" || phase === "connecting") {
    return (
      <StartScreen
        onStart={startGame}
        isConnecting={phase === "connecting" || transport.status === "connecting"}
        error={error}
      />
    );
  }

  if (phase === "game_over") {
    return <EndScreen gameState={gameState} onPlayAgain={endGame} />;
  }

  // waiting_for_spelling or between_words
  return (
    <GameScreen
      gameState={gameState}
      transport={transport}
      onEndGame={endGame}
    />
  );
}
