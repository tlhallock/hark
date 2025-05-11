import datetime
import subprocess
from typing import Optional

import requests

import schemas.recordings as schema
import schemas.searches as searches

BASE_URL = "http://localhost:8000"


def list_recordings(start=None, end=None):
	params = {}
	if start:
		params["start"] = start
	if end:
		params["end"] = end
	resp = requests.get(f"{BASE_URL}/recordings", params=params)
	resp.raise_for_status()
	return resp.json()


def get_recording(rec_id):
	resp = requests.get(f"{BASE_URL}/recordings/{rec_id}")
	resp.raise_for_status()
	return resp.json()


def play_recording(
	play_request: searches.PlayRecordingRequest,
):
	play_request.duration = datetime.timedelta(seconds=5)
	resp = requests.post(
		f"{BASE_URL}/play/{play_request.recording_id}",
		data=play_request.model_dump_json(),
		stream=True,
	)
	resp.raise_for_status()

	# Launch ffplay with stdin from HTTP stream
	# -autoexit: exit when stream ends, -nodisp: no video window
	player = subprocess.Popen(
		["ffplay", "-autoexit", "-nodisp", "-i", "pipe:0"], stdin=subprocess.PIPE
	)

	try:
		for chunk in resp.iter_content(chunk_size=1024 * 8):
			if chunk:
				player.stdin.write(chunk)
	except BrokenPipeError:
		# ffplay closed early (user quit)
		pass
	finally:
		player.stdin.close()
		player.wait()


# just pass the request...
def create_search(
	duration: Optional[datetime.timedelta] = None,
	lower: Optional[datetime.datetime] = None,
	upper: Optional[datetime.datetime] = None,
) -> searches.Search:
	payload = searches.CreateSearchRequest(duration=duration, lower=lower, upper=upper)
	resp = requests.post(f"{BASE_URL}/search", data=payload.model_dump_json())
	resp.raise_for_status()
	return searches.Search.model_validate(resp.json())


def get_prompt(search: searches.Search) -> searches.SearchPrompt:
	resp = requests.get(f"{BASE_URL}/search/{search.uuid}/prompt")
	resp.raise_for_status()
	return searches.SearchPrompt.model_validate(resp.json())


def update_search(search_id: str, update: searches.SearchUpdate) -> searches.Search:
	resp = requests.put(f"{BASE_URL}/search/{search_id}", data=update.model_dump_json())
	resp.raise_for_status()
	return searches.Search.model_validate(resp.json())


def get_statistics() -> schema.RecordingsSummary:
	resp = requests.get(f"{BASE_URL}/statistics")
	resp.raise_for_status()
	return schema.RecordingsSummary.model_validate(resp.json())
