

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- base directory as well?

CREATE TABLE IF NOT EXISTS recording (
	uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	file_path TEXT NOT NULL,
	begin_date TIMESTAMPTZ NOT NULL,
	audio_length INTERVAL NOT NULL,
	source TEXT,
	sha256sum TEXT, -- find the actual length of the sha256sum
	-- could have a checksummed_at
	imported_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS unique_file_path ON recording (file_path);


CREATE TABLE IF NOT EXISTS transcription_job (
	uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	model_name TEXT NOT NULL,
	chunk_length INTERVAL NOT NULL,
	stride_length_begin INTERVAL NOT NULL,
	stride_length_end INTERVAL NOT NULL,
	batch_size INT NOT NULL,


	began_at TIMESTAMPTZ DEFAULT now(),
);


CREATE TABLE IF NOT EXISTS transcription (
	uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	recording_uuid UUID NOT NULL REFERENCES recording(uuid) ON DELETE CASCADE,
	transcription_job_uuid UUID NOT NULL REFERENCES transcription_job(uuid) ON DELETE CASCADE,
	created_at TIMESTAMPTZ DEFAULT now(),

	file_chunk_path TEXT,

	begin_date TIMESTAMPTZ NOT NULL,
	end_date TIMESTAMPTZ NOT NULL,
	text TEXT NOT NULL,
);
