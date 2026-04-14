import { useCallback, useRef, useState } from "react";
import { PipecatClient } from "@pipecat-ai/client-js";
import {
  WebSocketTransport,
  ProtobufFrameSerializer,
} from "@pipecat-ai/websocket-transport";
import type { GameState, TransportStatus } from "../types";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";

function diag(event: string, data: Record<string, unknown> = {}) {
  const payload = { event, ts: Date.now(), ...data };
  console.log("[DIAG]", payload);
  fetch(`${BACKEND_URL}/log`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).catch(() => {});
}

const initialGameState: GameState = {
  phase: "idle",
  currentWord: "",
  wordIndex: 0,
  totalWords: 10,
  score: 0,
  history: [],
};

const initialTransport: TransportStatus = {
  status: "idle",
  botSpeaking: false,
  userSpeaking: false,
};

export function useSpellBeeClient() {
  const clientRef = useRef<PipecatClient | null>(null);
  const [gameState, setGameState] = useState<GameState>(initialGameState);
  const [transport, setTransport] = useState<TransportStatus>(initialTransport);
  const [error, setError] = useState<string | null>(null);

  const startGame = useCallback(async () => {
    diag("startGame.begin");
    setError(null);
    setTransport((t) => ({ ...t, status: "connecting" }));
    setGameState((g) => ({ ...g, phase: "connecting" }));

    try {
      const res = await fetch(`${BACKEND_URL}/connect`);
      if (!res.ok) throw new Error(`Backend returned ${res.status}`);
      const { wsUrl } = await res.json();
      diag("connect.fetched", { wsUrl });

      const client = new PipecatClient({
        transport: new WebSocketTransport({
          serializer: new ProtobufFrameSerializer(),
        }),
        enableMic: true,
        enableCam: false,
        callbacks: {
          onConnected: () => {
            diag("onConnected");
            setTransport((t) => ({ ...t, status: "connected" }));
          },
          onDisconnected: () => {
            diag("onDisconnected");
            setTransport(initialTransport);
          },
          onBotStartedSpeaking: () => {
            diag("onBotStartedSpeaking");
            setTransport((t) => ({ ...t, botSpeaking: true }));
          },
          onBotStoppedSpeaking: () => {
            diag("onBotStoppedSpeaking");
            setTransport((t) => ({ ...t, botSpeaking: false }));
          },
          onUserStartedSpeaking: () => {
            diag("onUserStartedSpeaking");
            setTransport((t) => ({ ...t, userSpeaking: true }));
          },
          onUserStoppedSpeaking: () => {
            diag("onUserStoppedSpeaking");
            setTransport((t) => ({ ...t, userSpeaking: false }));
          },
          onServerMessage: (data: { type: string; payload: GameState }) => {
            diag("onServerMessage", { msgType: data?.type, phase: data?.payload?.phase });
            if (data?.type === "game_state") {
              setGameState(data.payload);
            }
          },
          onBotTtsAudio: (data: unknown) => {
            diag("onBotTtsAudio", {
              bytes: (data as { data?: ArrayBuffer })?.data?.byteLength ?? -1,
            });
          },
          onError: (err: unknown) => {
            diag("onError", { err: String(err) });
            setError("Connection error. Please try again.");
            setTransport((t) => ({ ...t, status: "error" }));
          },
        } as Record<string, (...args: unknown[]) => void>,
      });

      clientRef.current = client;
      await client.connect({ wsUrl });
      diag("client.connect.returned");
    } catch (err) {
      diag("startGame.catch", { err: err instanceof Error ? err.message : String(err) });
      clientRef.current = null;
      const msg = err instanceof Error ? err.message : "Failed to connect";
      setError(msg);
      setTransport(initialTransport);
      setGameState(initialGameState);
    }
  }, []);

  const endGame = useCallback(async () => {
    await clientRef.current?.disconnect();
    clientRef.current = null;
    setGameState(initialGameState);
    setTransport(initialTransport);
    setError(null);
  }, []);

  return { gameState, transport, error, startGame, endGame };
}
