"""Pipecat pipeline factory for the spelling bee bot."""
import os

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import Frame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi.observer import RTVIObserverParams
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from constants import SpellingSpeed
from game_processor import SpellingGameProcessor

load_dotenv()


class TapProcessor(FrameProcessor):
    """Logs every non-audio frame at a given pipeline position for debugging."""

    def __init__(self, tag: str, **kwargs):
        super().__init__(**kwargs)
        self._tag = tag

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        name = type(frame).__name__
        if name not in ("InputAudioRawFrame", "OutputAudioRawFrame"):
            logger.debug(f"[TAP:{self._tag}] {name} dir={direction.name}")
        await self.push_frame(frame, direction)


async def run_bot(
    websocket_client,
    session_id: str = "",
    stop_secs: float = 1.8,
    user_id: int | None = None,
    spelling_speed: SpellingSpeed = SpellingSpeed.NORMAL,
) -> None:
    """Build and run the Pipecat pipeline for one WebSocket session.

    Parameters
    ----------
    websocket_client:
        FastAPI WebSocket accepted by the /ws endpoint.
    session_id:
        UUID string for this session; threaded through to the game processor
        for telemetry logging.
    stop_secs:
        Seconds of silence required before VAD considers an utterance finished.
        Derived from the authenticated user's spelling_speed preference;
        defaults to 1.8 (NORMAL speed).
    user_id:
        Authenticated user's DB id; None for anonymous sessions.
    spelling_speed:
        Resolved SpellingSpeed enum value; stored in game_sessions for metrics.
    """
    transport = FastAPIWebsocketTransport(
        websocket=websocket_client,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=ProtobufFrameSerializer(),
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(
                    # stop_secs is set per user preference (default 1.8s).
                    # A longer silence window prevents premature evaluation of
                    # letter-by-letter spellings where the user pauses between letters.
                    stop_secs=stop_secs,
                    # start_secs=0.3: require 300ms of continuous speech before
                    # triggering VAD. TTS echo bursts are typically shorter.
                    start_secs=0.3,
                    # confidence=0.7: higher threshold reduces echo false-triggers.
                    confidence=0.7,
                )
            ),
        ),
    )

    # Deepgram endpointing is set slightly shorter than VAD stop_secs so that
    # the STT server-side silence detector and the local VAD stay in sync.
    endpointing_ms = max(int(stop_secs * 1000) - 300, 500)

    stt = DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        settings=DeepgramSTTService.Settings(
            model="nova-2-general",
            language="en",
            punctuate=False,
            smart_format=False,
            interim_results=False,
            endpointing=endpointing_ms,
        ),
    )

    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id=os.getenv("CARTESIA_VOICE_ID", "71a7ad14-091c-4e8e-a314-022ece01c121"),
    )

    game_processor = SpellingGameProcessor(
        session_id=session_id,
        user_id=user_id,
        spelling_speed=spelling_speed,
    )

    pipeline = Pipeline([
        transport.input(),
        TapProcessor(tag="post-input"),
        stt,
        TapProcessor(tag="post-stt"),
        game_processor,
        TapProcessor(tag="post-game"),
        tts,
        TapProcessor(tag="post-tts"),
        transport.output(),
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=False,
        ),
        rtvi_observer_params=RTVIObserverParams(
            bot_speaking_enabled=True,
            user_speaking_enabled=True,
            user_transcription_enabled=False,
            bot_tts_enabled=False,
            bot_output_enabled=False,
            bot_llm_enabled=False,
            user_llm_enabled=False,
            metrics_enabled=False,
        ),
    )

    @task.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        logger.info(f"[BOOT] on_client_ready session={session_id}")
        intro = game_processor.get_intro_text()
        logger.info(f"[BOOT] intro={intro!r} word={game_processor._current_word!r}")
        await game_processor._push_game_state()
        await task.queue_frames([TTSSpeakFrame(text=intro)])
        logger.info("[BOOT] queued intro TTSSpeakFrame")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"Client disconnected session={session_id} — cancelling pipeline")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)
