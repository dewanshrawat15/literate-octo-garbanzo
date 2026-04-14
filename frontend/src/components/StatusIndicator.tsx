import type { GamePhase, TransportStatus } from "../types";

interface Props {
  gamePhase: GamePhase;
  transport: TransportStatus;
}

export function StatusIndicator({ gamePhase, transport }: Props) {
  const { botSpeaking, userSpeaking, status } = transport;

  let bgColor = "bg-gray-100";
  let textColor = "text-gray-600";
  let dot = "bg-gray-400";
  let label = "Waiting...";
  let animate = false;

  if (status === "connecting" || gamePhase === "connecting") {
    bgColor = "bg-yellow-50";
    textColor = "text-yellow-700";
    dot = "bg-yellow-400";
    label = "Connecting to game...";
    animate = true;
  } else if (botSpeaking) {
    bgColor = "bg-indigo-50";
    textColor = "text-indigo-700";
    dot = "bg-indigo-500";
    label = "Bot is speaking...";
    animate = true;
  } else if (userSpeaking) {
    bgColor = "bg-green-50";
    textColor = "text-green-700";
    dot = "bg-green-500";
    label = "Listening to you...";
    animate = true;
  } else if (gamePhase === "waiting_for_spelling") {
    bgColor = "bg-green-50";
    textColor = "text-green-700";
    dot = "bg-green-400";
    label = "Your turn — spell the word!";
  } else if (gamePhase === "between_words") {
    bgColor = "bg-blue-50";
    textColor = "text-blue-700";
    dot = "bg-blue-400";
    label = "Get ready for the next word...";
  }

  return (
    <div className={`flex items-center gap-3 px-5 py-3 rounded-full ${bgColor} ${textColor} font-medium text-sm`}>
      <span className={`inline-block w-2.5 h-2.5 rounded-full ${dot} ${animate ? "animate-pulse" : ""}`} />
      {label}
    </div>
  );
}
