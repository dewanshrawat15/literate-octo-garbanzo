import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusIndicator } from "../../components/StatusIndicator";
import type { GamePhase, TransportStatus } from "../../types";

function makeTransport(overrides: Partial<TransportStatus> = {}): TransportStatus {
  return { status: "connected", botSpeaking: false, userSpeaking: false, ...overrides };
}

describe("StatusIndicator", () => {
  it("shows connecting label when status is connecting", () => {
    render(
      <StatusIndicator
        gamePhase="idle"
        transport={makeTransport({ status: "connecting" })}
      />
    );
    expect(screen.getByText("Connecting to game...")).toBeInTheDocument();
  });

  it("shows bot speaking label when botSpeaking is true", () => {
    render(
      <StatusIndicator
        gamePhase="between_words"
        transport={makeTransport({ botSpeaking: true })}
      />
    );
    expect(screen.getByText("Bot is speaking...")).toBeInTheDocument();
  });

  it("shows listening label when userSpeaking is true", () => {
    render(
      <StatusIndicator
        gamePhase="waiting_for_spelling"
        transport={makeTransport({ userSpeaking: true })}
      />
    );
    expect(screen.getByText("Listening to you...")).toBeInTheDocument();
  });

  it("shows your turn label when phase is waiting_for_spelling", () => {
    render(
      <StatusIndicator
        gamePhase="waiting_for_spelling"
        transport={makeTransport()}
      />
    );
    expect(screen.getByText("Your turn — spell the word!")).toBeInTheDocument();
  });

  it("shows get ready label when phase is between_words", () => {
    render(
      <StatusIndicator
        gamePhase="between_words"
        transport={makeTransport()}
      />
    );
    expect(screen.getByText("Get ready for the next word...")).toBeInTheDocument();
  });

  it("dot has animate-pulse class when bot is speaking", () => {
    const { container } = render(
      <StatusIndicator
        gamePhase="between_words"
        transport={makeTransport({ botSpeaking: true })}
      />
    );
    const dot = container.querySelector("span.rounded-full");
    expect(dot).toHaveClass("animate-pulse");
  });

  it("dot does not have animate-pulse when waiting for spelling and idle", () => {
    const { container } = render(
      <StatusIndicator
        gamePhase="waiting_for_spelling"
        transport={makeTransport()}
      />
    );
    const dot = container.querySelector("span.rounded-full");
    expect(dot).not.toHaveClass("animate-pulse");
  });
});
