import datetime
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class PlayRecordingRequest(BaseModel):
	model_config = ConfigDict(ser_json_timedelta="float")

	recording_id: uuid.UUID
	offset: Optional[datetime.timedelta] = None
	duration: Optional[datetime.timedelta] = None


class SearchPrompt(BaseModel):
	prompt_timestamp: datetime.datetime
	play_request: Optional[PlayRecordingRequest]
	created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)

	current_lower_bound: Optional[datetime.datetime] = None
	current_upper_bound: Optional[datetime.datetime] = None


class SearchUpdate(BaseModel):
	prompt: SearchPrompt
	result: Literal["before", "after", "exact"]
	created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)


class SearchListResult(BaseModel):
	uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
	search_status: Literal["active", "completed"]
	created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
	updated_at: datetime.datetime = Field(default_factory=datetime.datetime.now)


class Search(BaseModel):
	uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
	created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
	updated_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
	search_status: Literal["active", "completed"] = Field(default="active")

	target_duration: Optional[datetime.timedelta] = None
	original_lower_bound: Optional[datetime.datetime] = None
	original_upper_bound: Optional[datetime.datetime] = None

	updates: list[SearchUpdate] = Field(default_factory=list)


class CreateSearchRequest(BaseModel):
	model_config = ConfigDict(ser_json_timedelta="float")

	duration: Optional[datetime.timedelta] = None
	lower: Optional[datetime.datetime] = None
	upper: Optional[datetime.datetime] = None
