

import psycopg2
from contextlib import contextmanager



@contextmanager
def connect_to_db():
	conn = psycopg2.connect(
		dbname="recordings",
		user="postgres",
		password="postgres",
		host="localhost",
		port=5432,
	)
	conn.autocommit = True
	cur = conn.cursor()
	try:
		yield cur
	finally:
		cur.close()
		conn.close()
