import { useState } from "react";
import { useAuth } from "./hooks/useAuth";
import { useSpellBeeClient } from "./hooks/useSpellBeeClient";
import { LoginScreen } from "./screens/LoginScreen";
import { SignupScreen } from "./screens/SignupScreen";
import { StartScreen } from "./components/StartScreen";
import { GameScreen } from "./components/GameScreen";
import { EndScreen } from "./components/EndScreen";
import type { SpellingSpeed } from "./types";

type AuthView = "login" | "signup";

export default function App() {
  const { user, error: authError, loading: authLoading, login, signup, logout } = useAuth();
  const { gameState, transport, error: gameError, startGame, endGame } = useSpellBeeClient();
  const [authView, setAuthView] = useState<AuthView>("login");

  // Auth screens — shown when no user session exists
  if (!user) {
    if (authView === "signup") {
      return (
        <SignupScreen
          onSignup={async (username, password, speed: SpellingSpeed) =>
            signup(username, password, speed)
          }
          onGoToLogin={() => setAuthView("login")}
          error={authError}
          loading={authLoading}
        />
      );
    }
    return (
      <LoginScreen
        onLogin={login}
        onGoToSignup={() => setAuthView("signup")}
        error={authError}
        loading={authLoading}
      />
    );
  }

  const { phase } = gameState;

  if (phase === "game_over") {
    return (
      <EndScreen
        gameState={gameState}
        onPlayAgain={async () => {
          await endGame();
        }}
      />
    );
  }

  if (phase === "waiting_for_spelling" || phase === "between_words") {
    return (
      <GameScreen
        gameState={gameState}
        transport={transport}
        onEndGame={async () => {
          await endGame();
        }}
      />
    );
  }

  // idle or connecting — show start screen
  return (
    <StartScreen
      onStart={() => startGame(user.token)}
      isConnecting={phase === "connecting" || transport.status === "connecting"}
      error={gameError}
      username={user.username}
      onLogout={async () => {
        await endGame();
        logout();
      }}
    />
  );
}
