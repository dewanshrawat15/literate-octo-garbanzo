import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WordHistory } from "../../components/WordHistory";
import type { WordResult } from "../../types";

describe("WordHistory", () => {
  it("shows empty state placeholder when history is empty", () => {
    render(<WordHistory history={[]} />);
    expect(screen.getByText(/words you spell will appear here/i)).toBeInTheDocument();
  });

  it("shows checkmark and correct styling for a correct entry", () => {
    const history: WordResult[] = [{ word: "cat", attempt: "cat", correct: true }];
    render(<WordHistory history={history} />);
    expect(screen.getByText("✓")).toBeInTheDocument();
    expect(screen.getByText("cat")).toBeInTheDocument();
    expect(screen.getByText("Correct")).toBeInTheDocument();
  });

  it("shows cross and attempt for an incorrect entry", () => {
    const history: WordResult[] = [{ word: "cat", attempt: "bat", correct: false }];
    render(<WordHistory history={history} />);
    expect(screen.getByText("✗")).toBeInTheDocument();
    expect(screen.getByText("bat")).toBeInTheDocument();
    expect(screen.getByText("Wrong")).toBeInTheDocument();
  });

  it("renders newest entry first (reversed order)", () => {
    const history: WordResult[] = [
      { word: "cat", attempt: "cat", correct: true },
      { word: "dog", attempt: "dog", correct: true },
    ];
    render(<WordHistory history={history} />);
    const words = screen.getAllByText(/cat|dog/);
    // "dog" was added last so should appear first in the reversed list
    expect(words[0].textContent).toBe("dog");
    expect(words[1].textContent).toBe("cat");
  });
});
