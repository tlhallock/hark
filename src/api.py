import asyncio
import datetime
import os
import subprocess
from typing import Dict, List, Optional

import asyncpg
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from starlette.requests import Request

import common
import schemas.recordings as schema
import schemas.searches as searches

app = FastAPI()

DIRECTORY = "/work/projects/tracker/mic/auto-sync"
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/recordings"

pool: asyncpg.Pool
searches_by_id: Dict[str, searches.Search] = {}


@app.on_event("startup")
async def startup():
	global pool
	pool = await asyncpg.create_pool(dsn=DATABASE_URL)


@app.on_event("shutdown")
async def shutdown():
	await pool.close()


# TODO: paginate
@app.get("/recordings")
async def list_recordings(
	start: Optional[datetime.datetime] = Query(None),
	end: Optional[datetime.datetime] = Query(None),
):
	query = "SELECT * FROM recording"
	params = []
	if start and end:
		query += " WHERE begin_date BETWEEN %s AND %s"
		params = [start, end]
	elif start:
		query += " WHERE begin_date >= %s"
		params = [start]
	elif end:
		query += " WHERE begin_date <= %s"
		params = [end]

	async with pool.acquire() as conn:
		records = await conn.fetch(query, *params)

	ret = []
	for record in records:
		ret.append(dict(record))
	return ret


@app.get("/recordings/{rec_id}")
async def get_recording(rec_id: str):
	query = "SELECT * FROM recording WHERE id = $1"
	async with pool.acquire() as conn:
		row = await conn.fetchrow(query, rec_id)
	if not row:
		raise HTTPException(status_code=404, detail="Recording not found")
	return dict(row)


# convert back to get, is it possible to use get, because i would like to
# use the pydantic model, but there is no "data" for a get...

# def play_request_from_query(
# 	recording_id: uuid.UUID = Query(...),
# 	offset: Optional[float] = Query(None),  # seconds
# 	duration: Optional[float] = Query(None),  # seconds
# ):
# 	return searches.PlayRecordingRequest(
# 		recording_id=recording_id,
# 		offset=datetime.timedelta(seconds=offset) if offset else None,
# 		duration=datetime.timedelta(seconds=duration) if duration else None
# 	)

# @app.get("/play/")
# async def play_recording(
#     request: Request,
#     play_request: searches.PlayRecordingRequest = Depends(play_request_from_query),
# ):


@app.post("/play/{rec_id}")
async def play_recording(
	request: Request,
	play_request: searches.PlayRecordingRequest,
):
	# if not rec_id:
	# 	raise HTTPException(status_code=400, detail="Recording ID not provided")
	# try:
	# 	uuid.UUID(rec_id)
	# except ValueError:
	# 	raise HTTPException(status_code=400, detail="Recording ID must be a uuid")
	query = "SELECT file_path FROM recording WHERE id = $1"
	async with pool.acquire() as conn:
		row = await conn.fetchrow(query, str(play_request.recording_id))
	if not row:
		raise HTTPException(status_code=404, detail="Recording not in database")
	fname = row["file_path"]
	if not fname:
		raise HTTPException(status_code=404, detail="Recording empty")

	if play_request.offset and play_request.offset < datetime.timedelta(0):
		print("this one")
		raise HTTPException(status_code=400, detail="Offset must be >= 0")

	path = os.path.join(DIRECTORY, fname)
	if not os.path.exists(path):
		raise HTTPException(status_code=404, detail="Recording path does not exist")
	if not os.path.isfile(path):
		raise HTTPException(status_code=404, detail="Recording not a file")
	if not os.access(path, os.R_OK):
		raise HTTPException(status_code=403, detail="Permission denied")

	print(
		f"Playing recording for a total of {play_request.duration.total_seconds()}s\n\n\n\n\n\n\n\n"
	)

	ffmpeg_cmd = ["ffmpeg"]
	if play_request.offset:
		ffmpeg_cmd += ["-ss", str(play_request.offset.total_seconds())]
	ffmpeg_cmd += ["-i", path]
	if play_request.duration:
		ffmpeg_cmd += ["-t", str(play_request.duration.total_seconds())]
	ffmpeg_cmd += ["-f", "mp3", "-"]
	proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)

	# cmd = ["ffmpeg", "-ss", str(offset), "-i", path, "-f", "mp3", "-"]
	# proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)
	# return StreamingResponse(proc.stdout, media_type="audio/mpeg")

	async def stream():
		try:
			while True:
				chunk = await asyncio.get_event_loop().run_in_executor(
					None, proc.stdout.read, 8192
				)
				if not chunk:
					break
				yield chunk
				if await request.is_disconnected():
					print("Client disconnected")
					break
		finally:
			print("Cleaning up")
			proc.kill()
			proc.wait()

	return StreamingResponse(stream(), media_type="audio/mpeg")


def _get_search_status(search: searches.Search) -> str:
	# no need to sort, just get the max
	latest_update = max(search.updates, key=lambda x: x.created_at, default=None)
	if not latest_update:
		return "active"
	if latest_update.result == "exact":
		return "completed"
	return "active"


@app.post("/search", response_model=searches.Search)
async def create_search(
	request: searches.CreateSearchRequest,
) -> searches.Search:
	if request.lower and request.upper and request.lower >= request.upper:
		raise HTTPException(
			status_code=400, detail="Lower bound must be less than upper bound"
		)
	global searches_by_id
	s = searches.Search(
		target_duration=request.duration,
		original_lower_bound=request.lower,
		original_upper_bound=request.upper,
	)
	searches_by_id[s.uuid] = s
	return s


@app.get("/search/{search_id}", response_model=searches.Search)
async def get_search(search_id: str) -> searches.Search:
	global searches_by_id
	s = searches_by_id.get(search_id, None)
	if not s:
		raise HTTPException(status_code=404, detail="Search not found")
	s.search_status = _get_search_status(s)
	return s


async def _get_lower_bound(search: searches.Search) -> datetime.datetime:
	latest = max(
		filter(lambda x: x.result == "after", search.updates),
		key=lambda x: x.prompt.prompt_timestamp,
		default=None,
	)
	if latest:
		return latest.prompt.prompt_timestamp

	if search.original_lower_bound:
		# what if there is a response that says the
		# target is before the lower bound?
		return search.original_lower_bound

	query = "min(begin_date) FROM recording"
	async with pool.acquire() as conn:
		row = await conn.fetchrow(query)
	if not row:
		# idk
		return datetime.datetime.now() - datetime.timedelta(days=1)
	return row["min"]


async def _get_upper_bound(search: searches.Search) -> datetime.datetime:
	earliest = min(
		filter(lambda x: x.result == "before", search.updates),
		key=lambda x: x.prompt.prompt_timestamp,
		default=None,
	)
	if earliest:
		return earliest.prompt.prompt_timestamp
	if search.original_upper_bound:
		# what if there is a response that says the
		# target is after the upper bound?
		return search.original_upper_bound
	query = "max(begin_date + audio_length) FROM recording"
	async with pool.acquire() as conn:
		row = await conn.fetchrow(query)
	if not row:
		return datetime.datetime.now()
	return row["max"]


async def _get_play_request(
	search: searches.Search,
	prompt_timestamp: datetime.datetime,
) -> Optional[searches.PlayRecordingRequest]:
	prompt_timestamp = common.normalize_datetime(prompt_timestamp)

	query = """
	select
		uuid,
		begin_date,
		audio_length
	from recording
	where begin_date < $1
	order by begin_date desc
	limit 1
	"""
	async with pool.acquire() as conn:
		row = await conn.fetchrow(query, prompt_timestamp)
	if not row:
		return None
	if not row["uuid"]:
		return None
	if not row["begin_date"]:
		return None
	if not row["audio_length"]:
		return None
	if row["begin_date"] > prompt_timestamp:
		raise HTTPException(
			status_code=500, detail="Recording begin date is after prompt timestamp"
		)
	return searches.PlayRecordingRequest(
		recording_id=row["uuid"],
		offset=prompt_timestamp - row["begin_date"],
		duration=None,
	)


@app.get("/search/{search_id}/prompt", response_model=searches.SearchPrompt)
async def get_next_prompt(search_id: str) -> searches.SearchPrompt:
	global searches_by_id
	s = searches_by_id.get(search_id, None)
	if not s:
		raise HTTPException(status_code=404, detail="Search not found")
	if _get_search_status(s) != "active":
		raise HTTPException(status_code=400, detail="Search not active")

	print("Getting next prompt, length of updates: ", len(s.updates))
	lb = await _get_lower_bound(s)
	ub = await _get_upper_bound(s)
	print("updates")
	for update in s.updates:
		print("\tupdate result: ", update.result)
		print("\tupdate prompt: ", update.prompt.prompt_timestamp)
	print("Lower bound: ", lb)
	print("Upper bound: ", ub)

	# TODO: use some sort of audio density
	mid = lb + (ub - lb) / 2
	prompt = searches.SearchPrompt(
		prompt_timestamp=mid,
		duration=None,
		play_request=await _get_play_request(s, mid),
		current_lower_bound=lb,
		current_upper_bound=ub,
	)
	return prompt


@app.get("/search", response_model=List[searches.SearchListResult])
async def list_searches(
	status: Optional[str] = Query(None),
) -> List[searches.SearchListResult]:
	results = []
	for s in searches_by_id.values():
		s.search_status = _get_search_status(s)
		if status and s.search_status != status:
			continue
		results.append(
			searches.SearchListResult(
				uuid=s.uuid, status=s.status, created_at=s.created_at, updated=s.updated
			)
		)
	return results


@app.put("/search/{search_id}", response_model=searches.Search)
async def update_search(
	search_id: str, prompt_result: searches.SearchUpdate
) -> searches.Search:
	s = searches_by_id.get(search_id, None)
	if not s:
		raise HTTPException(status_code=404, detail="Search not found")
	s.updates.append(prompt_result)
	s.updated_at = datetime.datetime.now()
	s.search_status = _get_search_status(s)
	return s


@app.get("/statistics", response_model=schema.RecordingsSummary)
async def get_statistics() -> schema.RecordingsSummary:
	query = """
		SELECT
			count(*) as number_of_recordings,
			sum(audio_length) as sum_of_durations,
			min(begin_date) as first_recording_begin,
			max(begin_date) as last_recording_begin
		FROM recording
	"""
	async with pool.acquire() as conn:
		row = await conn.fetchrow(query)
	if not row:
		raise HTTPException(status_code=404, detail="No recordings found")
	print(dict(row))
	return schema.RecordingsSummary.model_validate(dict(row))
