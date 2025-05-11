

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from typing import List, Optional
from datetime import datetime
import psycopg2
import psycopg2.extras
import os
import subprocess
import asyncpg
import asyncio
import uuid
import datetime
import schemas.searches as searches
from typing import Optional, Literal, Dict
from starlette.requests import Request
import schemas.recordings as schema


def normalize_datetime(dt: datetime.datetime) -> datetime.datetime:
	if dt.tzinfo is None:
		dt = dt.replace(tzinfo=datetime.timezone.utc)
	else:
		dt = dt.astimezone(datetime.timezone.utc)
	return dt