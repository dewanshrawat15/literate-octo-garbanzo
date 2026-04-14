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
  is_admin: boolean;
}

export interface SpellingStats {
  total_attempts: number;
  correct: number;
  incorrect: number;
  accuracy_pct: number;
}

export interface HardWord {
  word: string;
  attempts: number;
  correct_count: number;
  accuracy_pct: number;
}

export interface CommandUsage {
  repeat: number;
  skip: number;
  quit: number;
}

export interface TopUnhandled {
  raw_text: string;
  cnt: number;
}

export interface MetricsData {
  speed_distribution: Record<string, number>;
  total_users: number;
  total_sessions: number;
  completed_sessions: number;
  spelling_stats: SpellingStats;
  top_hard_words: HardWord[];
  command_usage: CommandUsage;
  unhandled_count: number;
  top_unhandled: TopUnhandled[];
  avg_score_pct: number | null;
}
