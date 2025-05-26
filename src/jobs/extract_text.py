import datetime
import os

# from transformers.models.whisper import WhisperTimeStampLogitsProcessor
import subprocess
from typing import List, Optional, Tuple
import random
import tqdm
from pydantic import BaseModel, Field

import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
from jobs.utils import connect_to_db
import shutil
import json


EXTENSIONS = {".opus"}


# move to schemas?
class TranscriptionResult(BaseModel):
	uuid: Optional[str] = Field(default=None)
	root_directory: str = "/work/projects/tracker/mic/auto-sync"

	# e.g. “openai/whisper-small” or “openai/whisper-medium”
	model_name: str = Field(default="openai/whisper-small")
	chunk_length: datetime.timedelta = Field(default=datetime.timedelta(seconds=30))
	stride_length_begin: datetime.timedelta = Field(
		default=datetime.timedelta(seconds=6)
	)
	stride_length_end: datetime.timedelta = Field(default=datetime.timedelta(seconds=0))
	batch_size: int = Field(default=1)


class TimeTaken(BaseModel):
	begin_time: datetime.datetime
	end_time: datetime.datetime


class TranscriptionEntry(BaseModel):
	start: Optional[float]
	end: Optional[float]
	text: Optional[str]


class FileTranscription(BaseModel):
	uuid: str
	begin_date: datetime.datetime

	result: TranscriptionResult
	source_file: str

	wav16k_file: str
	convertion_time: Optional[TimeTaken]

	processing_time: TimeTaken
	entries: List[TranscriptionEntry] = Field(default_factory=list)



def create_asr(result: TranscriptionResult):
	processor = AutoProcessor.from_pretrained(result.model_name)
	# It gave a warning: Also make sure WhisperTimeStampLogitsProcessor was used during generation.
	model = AutoModelForSpeechSeq2Seq.from_pretrained(
		result.model_name,
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


def to_wav16k(source_directory: str, source_subpath: str, temporary_directory: str) -> Tuple[str, TimeTaken]:
	src = os.path.join(source_directory, source_subpath)
	dst = os.path.join(temporary_directory, source_subpath + ".wav16k.wav")
	os.makedirs(os.path.dirname(dst), exist_ok=True)
	if os.path.exists(dst):
		return dst, None

	print(f"Converting {src} to {dst}")

	bigin_time = datetime.datetime.now()
	try:
		cmd = [
			"ffmpeg", "-y",
			"-i", str(src),
			"-ar", "16000",
			"-ac", "1",
			str(dst)
		]
		subprocess.run(
			cmd,
			check=True,
			# TODO: print to stdout
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL
		)
		return dst, TimeTaken(
			begin_time=bigin_time,
			end_time=datetime.datetime.now()
		)
	except subprocess.CalledProcessError as e:
		print(f"Error converting {src} to wav16k: {e}")
		shutil.rmtree(os.path.dirname(dst), ignore_errors=True)
		return None, None


def get_recording(file_path: str) -> Optional[TranscriptionResult]:
	with connect_to_db() as cur:
		cur.execute(
			"""
			SELECT uuid, begin_date, audio_length, source
			FROM recording
			WHERE file_path = %s
			""",
			(file_path,),
		)
		row = cur.fetchone()
	if not row:
		print(f"Recording not found in database: {file_path}")
		return None
	uuid, begin_date, audio_length, source = row
	return uuid, begin_date


def extract_text(result: TranscriptionResult, file_path: str):

	# result: TranscriptionResult
	# source_file: str

	# convert_file: str
	# convert_time: Optional[TimeTaken]

	# processing_time: TimeTaken
	# entries: List[TranscriptionEntry] = field(default_factory=list)

	source_directory = result.root_directory
	uuid, begin_date = get_recording(file_path)
	if not begin_date:
		print(f"Recording not found in database: {file_path}")
		return

	destination = "./outputs/wavs/"

	wav16, convertion_time = to_wav16k(source_directory, file_path, destination)
	if not wav16:
		print(f"Error converting {file_path} to wav16k")
		return

	asr = create_asr(result)
	begin_time = datetime.datetime.now()
	result = asr(wav16)
	processing_time = TimeTaken(
		begin_time=begin_time,
		end_time=datetime.datetime.now()
	)

	transcription = FileTranscription(
		uuid=uuid,
		begin_date=begin_date,
		result=result,
		source_file=file_path,
		wav16k_file=wav16,
		convertion_time=convertion_time,
		processing_time=processing_time,
	)

	with open("./outputs/wavs/log.txt", "a") as f:
		for chunk in result.get("chunks", []):
			start, end = chunk["timestamp"]
			text = chunk["text"]
			transcription.entries.append(
				TranscriptionEntry(
					start=start,
					end=end,
					text=text,
				)
			)
			text = text.strip()
			if not text:
				continue
			if not end:
				end = -1
			if not start:
				start = -1
			f.write(f"[{file_path}][{begin_date}][{processing_time}][{start:06.2f} - {end:06.2f}] {text}\n")
	
	current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
	with open(f"./outputs/wavs/{current_time}.json", "w") as f:
		f.write(transcription.model_dump_json(indent=2))


def create_job() -> TranscriptionResult:
	result = TranscriptionResult()
	return result
	with connect_to_db() as cur:
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
			),
		)
		job_uuid = cur.fetchone()[0]
	result.uuid = job_uuid
	return result


def main():
	result = create_job()
	random.seed(1776)
	paths = os.listdir(result.root_directory)
	random.shuffle(paths)
	print(f"Found {len(paths)} files")
	# paths = ["2025-04-13_03-06-44.opus"]
	for path in tqdm.tqdm(paths):
		extract_text(result, path)


if __name__ == "__main__":
	main()







# def list_chunks(output_dir: str, base_name: str) -> List[str]:
# 	output_files = []
# 	i = 0
# 	while True:
# 		part = os.path.join(output_dir, f"{base_name}.{i:05d}.wav16k.wav")
# 		if not os.path.exists(part):
# 			break
# 		output_files.append(part)
# 		i += 1
# 	return output_files


# def to_wav16k_split(src: str, destination: str) -> List[str]:
# 	base_name = os.path.basename(src)
# 	out_pattern = os.path.join(destination, f"{base_name}.%05d.wav16k.wav")
# 	segment_duration = datetime.timedelta(minutes=5)
# 	cmd = [
# 		"ffmpeg",
# 		"-y",
# 		"-i",
# 		str(src),
# 		"-ar",
# 		"16000",
# 		"-ac",
# 		"1",
# 		"-f",
# 		"segment",
# 		"-segment_time",
# 		str(segment_duration.total_seconds()),
# 		"-c",
# 		"pcm_s16le",
# 		str(out_pattern),
# 	]
# 	subprocess.run(
# 		cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
# 	)
# 	return list_chunks(destination, base_name)


# def print_file(asr, path: str):
# 	if path.suffix.lower() not in EXTENSIONS:
# 		return

# 	# Sonically load & run
# 	result = asr(str(path))

# 	# result["chunks"] holds a list of {start, end, text}
# 	print(f"result: {result}")
# 	for chunk in result.get("chunks", []):
# 		print(f"chunk: {chunk}")
# 		start = chunk["timestamp"][0]
# 		end = chunk["timestamp"][1]
# 		text = chunk["text"].strip()
# 		print(f"[{start:06.2f}s → {end:06.2f}s]  {text}")


	# audio = OggOpus(test_file)
	# audio_length = datetime.timedelta(seconds=audio.info.length)
	# print(f"Audio length: {audio_length}")

	# base_name = os.path.basename(test_file)
	# wav16s = list_chunks(destination, base_name)
	# if not wav16s:
	# 	print("Splitting file into chunks")
	# 	begin_time = datetime.datetime.now()
	# 	wav16s = to_wav16k_split(test_file, destination)
	# 	end_time = datetime.datetime.now()
	# 	print(f"Conversion took {end_time - begin_time} seconds")
	# assert wav16s, "No wav16k files found"
