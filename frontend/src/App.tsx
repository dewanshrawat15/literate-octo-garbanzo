import { useState } from "react";
import { useAuth } from "./hooks/useAuth";
import { useSpellBeeClient } from "./hooks/useSpellBeeClient";
import { LoginScreen } from "./screens/LoginScreen";
import { SignupScreen } from "./screens/SignupScreen";
import { ProfileScreen } from "./screens/ProfileScreen";
import { MetricsScreen } from "./screens/MetricsScreen";
import { StartScreen } from "./components/StartScreen";
import { GameScreen } from "./components/GameScreen";
import { EndScreen } from "./components/EndScreen";
import type { SpellingSpeed } from "./types";

type AuthView = "login" | "signup";
type AppView = "start" | "profile" | "metrics";

export default function App() {
  const { user, error: authError, loading: authLoading, login, signup, logout, updateSpeed } = useAuth();
  const { gameState, transport, error: gameError, startGame, endGame } = useSpellBeeClient();
  const [authView, setAuthView] = useState<AuthView>("login");
  const [appView, setAppView] = useState<AppView>("metrics");

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

  if (appView === "profile") {
    return (
      <ProfileScreen
        user={user}
        onUpdateSpeed={async (speed) => {
          const ok = await updateSpeed(speed);
          return ok;
        }}
        onBack={() => setAppView("start")}
        error={authError}
        loading={authLoading}
      />
    );
  }

  if (appView === "metrics" && user.is_admin) {
    return (
      <MetricsScreen
        token={user.token}
        onBack={() => setAppView("start")}
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
      isAdmin={user.is_admin}
      onGoToProfile={() => setAppView("profile")}
      onGoToMetrics={() => setAppView("metrics")}
      onLogout={async () => {
        await endGame();
        setAppView("start");
        logout();
      }}
    />
  );
}
