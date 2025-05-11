

import psycopg2
import tqdm
from dataclasses import dataclass, field
import os
import hashlib


@dataclass
class ChecksumResult:
	root_directory: str
	num_checksums_added: int = field(default=0)
	num_skipped: int = field(default=0)


def calculate_sha256(file_path, chunk_size: int = 4096) -> str:
	sha256 = hashlib.sha256()
	with open(file_path, "rb") as f:
		for chunk in iter(lambda: f.read(chunk_size), b""):
			sha256.update(chunk)
	return sha256.hexdigest()


def calculate_checksums(directory, cur, result: ChecksumResult):
	cur.execute("SELECT uuid, file_path FROM recording where sha256sum IS NULL")
	# WHERE source = 'stationary'
	rows = cur.fetchall()
	print(f"Checksumming {len(rows)} recordings")

	for row in tqdm.tqdm(rows):
		uuid, file_path = row[0], row[1]
		full_path = os.path.join(directory, file_path)
		if not os.path.exists(full_path):
			result.num_skipped += 1
			continue

		sha256sum = calculate_sha256(full_path)

		cur.execute(
			"UPDATE recording SET sha256sum = %s WHERE uuid = %s",
			(sha256sum, uuid)
		)
		if cur.rowcount < 1:
			print(f"That is odd: {uuid} not found in database")
			continue
		result.num_checksums_added += 1


def main():
	root_directory = "/work/projects/tracker/mic/auto-sync"
	result = ChecksumResult(root_directory=root_directory)
	with psycopg2.connect(
		dbname="recordings",
		user="postgres", 
		password="postgres",
		host="localhost", 
		port=5432
	) as conn:
		conn.autocommit = True
		with conn.cursor() as cur:
			calculate_checksums(
				root_directory,
				cur,
				result,
			)
	print(f"result: {result}")


if __name__ == "__main__":
	main()
