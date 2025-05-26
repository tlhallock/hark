
import datetime
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Recording(BaseModel):
	uuid: uuid.UUID
	file_path: str
	begin_date: datetime.datetime
	audio_length: datetime.timedelta
	source: Optional[str] = None
	sha256sum: Optional[str] = None
	disk_usage: Optional[int] = None


class DatabaseExport(BaseModel):
	model_config = ConfigDict(ser_json_timedelta="float")

	recordings: list[Recording] = Field(default_factory=list)
	created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
	updated_at: datetime.datetime = Field(default_factory=datetime.datetime.now)


# searches
# transcriptions
