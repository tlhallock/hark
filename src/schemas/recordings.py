import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RecordingsSummary(BaseModel):
	model_config = ConfigDict(ser_json_timedelta="float")

	number_of_recordings: int
	sum_of_durations: Optional[datetime.timedelta]
	first_recording_begin: Optional[datetime.datetime]
	last_recording_begin: Optional[datetime.datetime]
	# could have the last recording end date
