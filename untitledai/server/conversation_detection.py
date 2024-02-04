#
# conversation_detection.py
#
# Conversation detection and extraction logic. 
#

from dataclasses import dataclass
from datetime import timedelta
import logging
import os
from queue import Queue
import uuid

from pydub import AudioSegment

from ..files import CaptureFile
from ..services import ConversationEndpointDetector


logger = logging.getLogger(__name__)

@dataclass
class ConversationDetectionTask:
    capture_file: CaptureFile
    conversation_endpoint_detector: ConversationEndpointDetector
    samples: AudioSegment | None
    capture_finished: bool

def detect_and_extract_conversations(task: ConversationDetectionTask, conversation_task_queue: Queue):
    # Unpack data we need
    capture_file = task.capture_file
    file_extension = os.path.splitext(capture_file.filepath)[1].lstrip(".")
    detector = task.conversation_endpoint_detector
    samples = task.samples
    capture_finished = task.capture_finished
    
    # Run conversation endpointing to detect conversations and submit for processing
    convos = detector.consume_samples(samples=samples, end_stream=capture_finished)
    if len(convos) > 0:
        audio = AudioSegment.from_file(file=capture_file.filepath, format=file_extension)

        for convo in convos:
            # Create segment file and write audio to disk
            conversation_audio = audio[convo.start:convo.end]
            timestamp = capture_file.timestamp + timedelta(milliseconds=convo.start)
            segment_file = capture_file.create_conversation_segment(
                conversation_uuid=uuid.uuid1().hex,
                timestamp=timestamp,
                file_extension=file_extension
            )
            conversation_audio.export(out_f=segment_file.filepath, format=file_extension)
            logger.info(f"Wrote conversation audio file: {segment_file.filepath}")

            # Enqueue for processing
            processing_task = (capture_file, segment_file)
            conversation_task_queue.put(processing_task)
            logger.info(f"Enqueued conversation capture for processing: {segment_file.filepath}")