import datetime


def normalize_datetime(dt: datetime.datetime) -> datetime.datetime:
	if dt.tzinfo is None:
		dt = dt.replace(tzinfo=datetime.timezone.utc)
	else:
		dt = dt.astimezone(datetime.timezone.utc)
	return dt
