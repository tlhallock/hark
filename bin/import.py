import os
import re
from datetime import datetime, timedelta
import psycopg2
from mutagen.oggopus import OggOpus
import tqdm
from common import normalize_datetime


pattern = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})\.opus")


def import_audio(directory, fname, cur):
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
			source,
			sha1sum
		)
		VALUES (%s, %s, %s, 'stationary', NULL)
		""",
		# ON CONFLICT (file_path) DO NOTHING;
		(fname, begin, audio_length)
	)


def import_audios(directory, conn):
	with conn.cursor() as cur:
		files = os.listdir(directory)
		files = sorted(files)
		for fname in tqdm.tqdm(files):
			import_audio(directory, fname, cur)


def main():
	with psycopg2.connect(
		dbname="recordings",
		user="postgres", 
		password="postgres",
		host="localhost", 
		port=5432
	) as conn:
		conn.autocommit = True
		import_audios(
			"/work/projects/tracker/mic/auto-sync",
			conn
		)


if __name__ == "__main__":
	main()
