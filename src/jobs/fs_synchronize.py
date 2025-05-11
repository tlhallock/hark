import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import psycopg2
import tqdm
from mutagen.oggopus import OggOpus

from common import normalize_datetime

pattern = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})\.opus")


@dataclass
class SynchronizationResult:
	root_directory: str
	# could be the actual filenames...
	num_inserted: int = field(default=0)
	# already exist vs file still present, is there a difference?
	num_unchanged: int = field(default=0)
	num_removed: int = field(default=0)
	# num_updated: int


def add_new_recording(directory, fname, cur, result: SynchronizationResult):
	match = pattern.match(fname)
	if not match:
		return
	date_part, time_part = match.groups()
	ts_str = f"{date_part} {time_part.replace('-', ':')}"
	begin = datetime.fromisoformat(ts_str)
	begin = normalize_datetime(begin)

	path = os.path.join(directory, fname)
	audio = OggOpus(path)
	audio_length = timedelta(seconds=audio.info.length)
	cur.execute(
		"""
		INSERT INTO recording (
			file_path,
			begin_date,
			audio_length,
			source
		)
		VALUES (%s, %s, %s, 'stationary')
		ON CONFLICT (file_path) DO NOTHING;
		""",
		(fname, begin, audio_length),
	)
	if cur.rowcount > 0:
		result.num_inserted += 1
	else:
		result.num_unchanged += 1


def add_new_recordings(directory, cur, result: SynchronizationResult):
	files = os.listdir(directory)
	files = sorted(files)
	print(f"Checking {len(files)} files")
	for fname in tqdm.tqdm(files):
		add_new_recording(directory, fname, cur, result)


def remove_missing_recordings(directory, cur, result: SynchronizationResult):
	cur.execute("SELECT uuid, file_path FROM recording")
	# WHERE source = 'stationary'
	rows = cur.fetchall()
	print(f"Checking {len(rows)} existing recordings")
	for row in tqdm.tqdm(rows):
		# row = dict(row)
		uuid, file_path = row[0], row[1]
		full_path = os.path.join(directory, file_path)
		if os.path.exists(full_path):
			continue
		cur.execute("DELETE FROM recording WHERE uuid = %s", (uuid,))
		result.num_removed += 1


def main():
	root_directory = "/work/projects/tracker/mic/auto-sync"
	result = SynchronizationResult(
		root_directory=root_directory,
		# source="stationary",
	)
	with psycopg2.connect(
		dbname="recordings",
		user="postgres",
		password="postgres",
		host="localhost",
		port=5432,
	) as conn:
		conn.autocommit = True
		with conn.cursor() as cur:
			remove_missing_recordings(
				root_directory,
				cur,
				result,
			)
			add_new_recordings(
				root_directory,
				cur,
				result,
			)
	print(f"result: {result}")


if __name__ == "__main__":
	main()
