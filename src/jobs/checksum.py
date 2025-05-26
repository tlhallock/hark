import hashlib
import os
from dataclasses import dataclass, field

import tqdm
from jobs.utils import connect_to_db


@dataclass
class ChecksumResult:
	root_directory: str
	num_checksums_added: int = field(default=0)
	num_skipped: int = field(default=0)
	num_errored: int = field(default=0)


def calculate_sha256(file_path, chunk_size: int = 4096) -> str:
	sha256 = hashlib.sha256()
	with open(file_path, "rb") as f:
		for chunk in iter(lambda: f.read(chunk_size), b""):
			sha256.update(chunk)
	return sha256.hexdigest()


def get_files_to_checksum(directory: str, result: ChecksumResult):
	with connect_to_db() as cur:
		cur.execute("SELECT uuid, file_path FROM recording WHERE sha256sum IS NULL")
		# WHERE source = 'stationary'
		rows = cur.fetchall()
	print(f"Checksumming {len(rows)} recordings")

	full_paths = []
	for row in rows:
		uuid, file_path = row[0], row[1]
		full_path = os.path.join(directory, file_path)
		if not os.path.exists(full_path):
			result.num_skipped += 1
			continue
		full_paths.append((uuid, full_path))
	return full_paths


def calcutate_checksum(uuid: str, full_path: str, result: ChecksumResult):
	sha256sum = calculate_sha256(full_path)
	with connect_to_db() as cur:
		cur.execute(
			"UPDATE recording SET sha256sum = %s WHERE uuid = %s",
			(sha256sum, uuid)
		)
	if cur.rowcount < 1:
		print(f"That is odd: {uuid} not found in database")
		return
	result.num_checksums_added += 1


def calculate_checksums(directory: str, result: ChecksumResult):
	full_paths = get_files_to_checksum(directory, result)
	if not full_paths:
		print("No files to checksum")
		return

	for uuid, full_path in tqdm.tqdm(full_paths):
		try:
			calcutate_checksum(uuid, full_path, result)
		except Exception as e:
			print(f"Error calculating checksum for {full_path}: {e}")
			result.num_errored += 1
			continue


def main():
	root_directory = "/work/projects/tracker/mic/auto-sync"
	result = ChecksumResult(root_directory=root_directory)
	calculate_checksums(root_directory, result)
	print(f"result: {result}")


if __name__ == "__main__":
	main()

