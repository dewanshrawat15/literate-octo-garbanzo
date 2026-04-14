import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScoreDisplay } from "../../components/ScoreDisplay";
import type { GameState } from "../../types";

function makeGameState(overrides: Partial<GameState> = {}): GameState {
  return {
    phase: "between_words",
    currentWord: "cat",
    wordIndex: 3,
    totalWords: 10,
    score: 2,
    history: [
      { word: "cat", attempt: "cat", correct: true },
      { word: "dog", attempt: "dog", correct: true },
      { word: "hat", attempt: "bat", correct: false },
    ],
    ...overrides,
  };
}

describe("ScoreDisplay", () => {
  it("shows the correct score count", () => {
    // score=5, wordIndex=3, totalWords=10 → remaining=7; all three numbers are distinct
    render(<ScoreDisplay gameState={makeGameState({ score: 5, wordIndex: 3, totalWords: 10 })} />);
    // "Correct" label's parentElement is the .text-center wrapper containing the score number
    const correctLabel = screen.getByText(/^correct$/i);
    const scoreNumber = correctLabel.parentElement!.querySelector(".text-3xl");
    expect(scoreNumber?.textContent).toBe("5");
  });

  it("shows the attempted count from history length", () => {
    const state = makeGameState();
    render(<ScoreDisplay gameState={state} />);
    // history has 3 entries
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText(/attempted/i)).toBeInTheDocument();
  });

  it("shows remaining count as totalWords minus wordIndex", () => {
    // totalWords=10, wordIndex=3 → remaining=7
    render(<ScoreDisplay gameState={makeGameState({ totalWords: 10, wordIndex: 3 })} />);
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText(/remaining/i)).toBeInTheDocument();
  });
});
