
import datetime
from typing import Optional
import schemas.searches as searches
import client
import schemas.recordings as schema
import random


def test_fake_search():
	random.seed(1776)

	statistics: schema.RecordingsSummary = client.get_statistics()
	assert statistics.number_of_recordings > 0
	assert statistics.first_recording_begin is not None
	assert statistics.last_recording_begin is not None
	assert statistics.last_recording_begin > statistics.first_recording_begin

	total_delta = (statistics.last_recording_begin - statistics.first_recording_begin)
	random_seconds = datetime.timedelta(seconds=random.randint(
		0,
		int(total_delta.total_seconds()) - 1
	))
	target_time = statistics.first_recording_begin + random_seconds

	lower = statistics.first_recording_begin + datetime.timedelta(seconds=5)
	upper = statistics.last_recording_begin - datetime.timedelta(seconds=5)
	duration = datetime.timedelta(seconds=10)
	search = client.create_search(duration, lower, upper)

	count = 0
	while search.search_status != 'completed':
		count += 1
		assert count < 100

		prompt = client.get_prompt(search)
		assert prompt.play_request is not None

		print(f"\n\nTarget:\n\t     {target_time}")
		print(f"Prompt:\n\t     {prompt.prompt_timestamp}")
		print(f"Current bounds:\n\tmin: {prompt.current_lower_bound}\n\tmax: {prompt.current_upper_bound}")
		# play_recording(play_request=prompt.play_request)
		
		if target_time > prompt.prompt_timestamp + duration:
			result = "after"
		elif target_time < prompt.prompt_timestamp - duration:
			result = "before"
		else:
			result = "exact"

		search = client.update_search(
			search.uuid,
			searches.SearchUpdate(
				prompt=prompt,
				result=result,
			)
		)
	print("Search completed!")
