import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSpellBeeClient } from "../../hooks/useSpellBeeClient";

// ---------------------------------------------------------------------------
// Mocks — must be hoisted via vi.mock at module scope
// ---------------------------------------------------------------------------

const mockConnect = vi.fn();
const mockDisconnect = vi.fn();

// This ref is set each time PipecatClient is constructed so tests can
// invoke callbacks directly.
let capturedCallbacks: Record<string, (...args: unknown[]) => void> = {};

vi.mock("@pipecat-ai/client-js", () => ({
  // Use a named function (not an arrow fn) so vitest treats it as a
  // constructor-compatible mock.
  PipecatClient: vi.fn(function (opts: { callbacks?: Record<string, (...args: unknown[]) => void> }) {
    capturedCallbacks = opts?.callbacks ?? {};
    return { connect: mockConnect, disconnect: mockDisconnect };
  }),
}));

vi.mock("@pipecat-ai/websocket-transport", () => ({
  WebSocketTransport: vi.fn(function () { return {}; }),
  ProtobufFrameSerializer: vi.fn(function () { return {}; }),
}));

// ---------------------------------------------------------------------------
// fetch helpers
// ---------------------------------------------------------------------------

function mockFetchSuccess() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ wsUrl: "ws://localhost:8000/ws" }),
    })
  );
}

function mockFetchFailure() {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Network error")));
}

beforeEach(() => {
  vi.clearAllMocks();
  capturedCallbacks = {};
  mockConnect.mockResolvedValue(undefined);
  mockDisconnect.mockResolvedValue(undefined);
});

// ---------------------------------------------------------------------------

describe("useSpellBeeClient", () => {
  it("has idle initial state", () => {
    const { result } = renderHook(() => useSpellBeeClient());
    expect(result.current.gameState.phase).toBe("idle");
    expect(result.current.transport.status).toBe("idle");
    expect(result.current.error).toBeNull();
  });

  it("sets status to connecting when startGame is called", async () => {
    mockFetchSuccess();
    const { result } = renderHook(() => useSpellBeeClient());

    // Capture the connecting state before the promise resolves
    act(() => { result.current.startGame(); });
    expect(result.current.transport.status).toBe("connecting");
  });

  it("updates gameState when onServerMessage fires with game_state type", async () => {
    mockFetchSuccess();
    const { result } = renderHook(() => useSpellBeeClient());

    await act(async () => { await result.current.startGame(); });

    // Verify PipecatClient was constructed and callbacks captured
    expect(Object.keys(capturedCallbacks).length).toBeGreaterThan(0);

    act(() => {
      capturedCallbacks.onServerMessage?.({
        type: "game_state",
        payload: {
          phase: "waiting_for_spelling",
          score: 3,
          wordIndex: 3,
          totalWords: 10,
          currentWord: "hat",
          history: [],
        },
      });
    });

    expect(result.current.gameState.phase).toBe("waiting_for_spelling");
    expect(result.current.gameState.score).toBe(3);
  });

  it("resets state after endGame", async () => {
    mockFetchSuccess();
    const { result } = renderHook(() => useSpellBeeClient());

    await act(async () => { await result.current.startGame(); });
    await act(async () => { await result.current.endGame(); });

    expect(result.current.gameState.phase).toBe("idle");
    expect(result.current.transport.status).toBe("idle");
  });

  it("sets error and transport stays idle when fetch throws", async () => {
    mockFetchFailure();
    const { result } = renderHook(() => useSpellBeeClient());

    await act(async () => { await result.current.startGame(); });

    expect(result.current.error).toBeTruthy();
    expect(result.current.transport.status).toBe("idle");
    // Subsequent endGame should not throw (clientRef.current is null)
    await act(async () => { await result.current.endGame(); });
    expect(result.current.error).toBeNull();
  });
});
