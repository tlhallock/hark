import datetime

import client
import schemas.searches as searches


def play_a_recording():
	# 1) List all recordings
	print("=== All Recordings ===")
	recs = client.list_recordings()
	for rec in recs:
		print(
			f"{rec['id']} | {rec['file_path']} | {rec['begin_date']} | {rec['audio_length']}"
		)

	if not recs:
		print("No recordings found.")
		return

	first_id = recs[0]["id"]
	print("\n=== Details for first recording ===")
	detail = client.get_recording(first_id)
	for k, v in detail.items():
		print(f"{k}: {v}")

	# choice = input("Select a recording number to play: ")
	choice = 3
	try:
		idx = int(choice) - 1
		sel = recs[idx]
	except (ValueError, IndexError):
		print("Invalid selection.")
		return

	# offset = input("Enter start offset in seconds (default 0): ") or 0
	offset = 2
	client.play_recording(sel["id"], int(offset))


def search_recordings():
	lower = datetime.datetime.now() - datetime.timedelta(hours=2)
	upper = datetime.datetime.now()
	duration = datetime.timedelta(seconds=5)
	search = client.create_search(duration, lower, upper)
	print(f"Search created with ID: {search.uuid} and status: {search.search_status}")

	while search.search_status != "completed":
		prompt = client.get_prompt(search)
		print(f"Playing recording snippet at {prompt}")
		if not prompt.play_request:
			print("No play request found.")
			break
		client.play_recording(play_request=prompt.play_request)
		print(f"Current search: {search}")

		response = input("Was the conversation before/after/exact/longer? ")
		if response == "before":
			result = "before"
		elif response == "after":
			result = "after"
		elif response == "exact":
			result = "exact"
		elif response == "longer":
			pass
			# make another play request
		elif response == "exit":
			print("Exiting search.")
			return
		else:
			print("Invalid response.")
			return

		search = client.update_search(
			search.uuid,
			searches.SearchUpdate(
				prompt=prompt,
				result=result,
			),
		)
	print("Search completed!")


if __name__ == "__main__":
	print(client.get_statistics())
	# search_recordings()
