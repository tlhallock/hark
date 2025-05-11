
import datetime

from typing import List, Optional, Dict, Tuple

import os
import tqdm
import torch
from transformers import pipeline, AutoProcessor, AutoModelForSpeechSeq2Seq, WhisperProcessor
# from transformers.models.whisper import WhisperTimeStampLogitsProcessor
import subprocess
from mutagen.oggopus import OggOpus
import random
from dataclasses import dataclass, field
import os
import re
import datetime
import psycopg2
from mutagen.oggopus import OggOpus
import tqdm
from common import normalize_datetime
import uuid


EXTENSIONS = {".opus"}


# move to schemas?
@dataclass
class TranscriptionResult:
	uuid: Optional[str] = field(default=None)
	root_directory: str = "/work/projects/tracker/mic/auto-sync"

	# e.g. “openai/whisper-small” or “openai/whisper-medium”
	model_name: str = field(default="openai/whisper-small")
	chunk_length: datetime.timedelta = field(default=datetime.timedelta(seconds=30))
	stride_length_begin: datetime.timedelta = field(default=datetime.timedelta(seconds=6))
	stride_length_end: datetime.timedelta = field(default=datetime.timedelta(seconds=0))
	batch_size: int = field(default=1)


# 
def create_asr():
	processor = AutoProcessor.from_pretrained(MODEL_NAME)
	# It gave a warning: Also make sure WhisperTimeStampLogitsProcessor was used during generation.
	model = AutoModelForSpeechSeq2Seq.from_pretrained(
		MODEL_NAME,
		attn_implementation="eager",
	)

	chunk_length_s = 30
	# ts_processor = WhisperTimeStampLogitsProcessor(
	# 	processor.tokenizer,
	# 	chunk_length_s=chunk_length_s,
	# 	stride_length_s=5,
	# )
	asr = pipeline(
		task="automatic-speech-recognition",
		model=model,

		tokenizer=processor.tokenizer,
		feature_extractor=processor.feature_extractor,
		
		# options: “char”, “word”, or “none”
		# return_timestamps="word",


		# split long files
		# chunk_length_s=chunk_length_s,
		# overlap 5s at start/end of each chunk
		# stride_length_s=(5, 5),
		device=0 if torch.cuda.is_available() else -1,

		# batch_size=1,
		# generate_kwargs={
		# 	# "logits_processors": [ts_processor],
		# 	"task": "transcribe",
		# 	# "language":"<|tr|>",
		# 	# language="en"
		# }
	)
	def ret(*args, **kwargs):
		return asr(
			*args,
			**kwargs,
			return_timestamps=True,
			stride_length_s=(6, 0),
			chunk_length_s=chunk_length_s,
			batch_size=1,
		)
	return ret


# def to_wav16k(src: Path) -> Path:
# 	dst = src.with_suffix(".wav16k.wav")
# 	if dst.exists():
# 		return dst
# 	cmd = [
# 		"ffmpeg", "-y",
# 		"-i", str(src),
# 		"-ar", "16000",
# 		"-ac", "1",
# 		str(dst)
# 	]
# 	subprocess.run(
# 		cmd,
# 		check=True,
# 		# TODO: print to stdout
# 		stdout=subprocess.DEVNULL,
# 		stderr=subprocess.DEVNULL
# 	)
# 	return dst


def list_chunks(output_dir: str, base_name: str) -> List[str]:
	output_files = []
	i = 0
	while True:
		part = os.path.join(output_dir, f"{base_name}.{i:05d}.wav16k.wav")
		if not os.path.exists(part):
			break
		output_files.append(part)
		i += 1
	return output_files


def to_wav16k_split(src: str, destination: str) -> List[str]:
	base_name = os.path.basename(src)
	out_pattern = os.path.join(destination, f"{base_name}.%05d.wav16k.wav")
	segment_duration = datetime.timedelta(minutes=5)
	cmd = [
		"ffmpeg", "-y",
		"-i", str(src),
		"-ar", "16000",
		"-ac", "1",
		"-f", "segment",
		"-segment_time", str(segment_duration.total_seconds()),
		"-c", "pcm_s16le",
		str(out_pattern)
	]
	subprocess.run(
		cmd,
		check=True,
		stdout=subprocess.DEVNULL,
		stderr=subprocess.DEVNULL
	)
	return list_chunks(destination, base_name)


def print_file(asr, path: str):
	if path.suffix.lower() not in EXTENSIONS:
		return

	# Sonically load & run
	result = asr(str(path))

	# result["chunks"] holds a list of {start, end, text}
	print(f"result: {result}")
	for chunk in result.get("chunks", []):
		print(f"chunk: {chunk}")
		start = chunk["timestamp"][0]
		end = chunk["timestamp"][1]
		text = chunk["text"].strip()
		print(f"[{start:06.2f}s → {end:06.2f}s]  {text}")


def test():
	for path in tqdm.tqdm(sorted(AUDIO_DIR.iterdir())):
		print_file(asr, path)


def extract_text(conn, result: TranscriptionResult):
	# random.seed(1776)
	test_file = "/work/projects/tracker/mic/auto-sync/2025-04-13_03-06-44.opus"
	destination = "./outputs/wavs/"

	audio = OggOpus(test_file)
	audio_length = datetime.timedelta(seconds=audio.info.length)
	print(f"Audio length: {audio_length}")

	base_name = os.path.basename(test_file)
	wav16s = list_chunks(destination, base_name)
	if not wav16s:
		print("Splitting file into chunks")
		begin_time = datetime.datetime.now()
		wav16s = to_wav16k_split(test_file, destination)
		end_time = datetime.datetime.now()
		print(f"Conversion took {end_time - begin_time} seconds")
	assert wav16s, "No wav16k files found"

	# num_chunks = len(wav16s)
	# chunk_index = random.randint(0, num_chunks - 1)
	# chunk_index = 0
	# wav16 = wav16s[chunk_index]
	# print(f"Found {num_chunks}, choosing index: {chunk_index}")
	wav16 = "./outputs/wavs/2025-04-13_03-06-44.opus.00020.wav16k.wav"

	asr = create_asr()
	bigin_time = datetime.datetime.now()
	result = asr(wav16)
	end_time = datetime.datetime.now()
	print(f"ASR took {end_time - bigin_time} seconds")

	for chunk in result.get("chunks", []):
		start, end = chunk["timestamp"]
		text = chunk["text"].strip()
		if not text:
			continue
		if not end:
			end = -1
		if not start:
			start = -1
		print(f"[{start:06.2f}s -> {end:06.2f}s] {text}")


def create_job(conn) -> TranscriptionResult:
	result = TranscriptionResult()
	with conn.cursor() as cur:
		cur.execute(
			"""
			INSERT INTO transcription_job (
				root_directory,
				model_name,
				chunk_length,
				stride_length_begin,
				stride_length_end,
				batch_size
			)
			VALUES (%s, %s, %s, %s, %s, %s)
			RETURNING uuid
			""",
			(
				result.root_directory,
				result.model_name,
				result.chunk_length.total_seconds(),
				result.stride_length_begin.total_seconds(),
				result.stride_length_end.total_seconds(),
				result.batch_size,
			)
		)
		job_uuid = cur.fetchone()[0]
	result.uuid = job_uuid
	return result



def main():
	with psycopg2.connect(
		dbname="recordings",
		user="postgres", 
		password="postgres",
		host="localhost", 
		port=5432
	) as conn:
		conn.autocommit = True

		result = create_job(conn)
		extract_text(
			conn,
			result,
		)

if __name__ == "__main__":
	extract_text()