import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EndScreen } from "../../components/EndScreen";
import type { GameState } from "../../types";

function makeGameState(score: number, totalWords = 10): GameState {
  return {
    phase: "game_over",
    currentWord: "",
    wordIndex: totalWords,
    totalWords,
    score,
    history: [],
  };
}

describe("EndScreen", () => {
  it("shows trophy emoji for a perfect score", () => {
    render(<EndScreen gameState={makeGameState(10, 10)} onPlayAgain={() => {}} />);
    expect(screen.getByText("🏆")).toBeInTheDocument();
  });

  it("shows star emoji for 8/10", () => {
    render(<EndScreen gameState={makeGameState(8, 10)} onPlayAgain={() => {}} />);
    expect(screen.getByText("🌟")).toBeInTheDocument();
  });

  it("displays score as score/totalWords", () => {
    render(<EndScreen gameState={makeGameState(8, 10)} onPlayAgain={() => {}} />);
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("/10")).toBeInTheDocument();
  });

  it("calls onPlayAgain when Play Again button is clicked", async () => {
    const user = userEvent.setup();
    const onPlayAgain = vi.fn();
    render(<EndScreen gameState={makeGameState(5, 10)} onPlayAgain={onPlayAgain} />);
    await user.click(screen.getByRole("button", { name: /play again/i }));
    expect(onPlayAgain).toHaveBeenCalledOnce();
  });
});
