export interface WordResult {
  word: string;
  attempt: string;
  correct: boolean;
}

export type GamePhase =
  | "idle"
  | "connecting"
  | "waiting_for_spelling"
  | "between_words"
  | "game_over";

export interface GameState {
  phase: GamePhase;
  currentWord: string;
  wordIndex: number;
  totalWords: number;
  score: number;
  history: WordResult[];
}

export interface TransportStatus {
  status: "idle" | "connecting" | "connected" | "error";
  botSpeaking: boolean;
  userSpeaking: boolean;
}

export type SpellingSpeed = "slow" | "normal" | "fast";

export interface UserProfile {
  token: string;
  username: string;
  spelling_speed: SpellingSpeed;
}
