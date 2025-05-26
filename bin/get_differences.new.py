import ffmpeg
import numpy as np
import librosa
import matplotlib.pyplot as plt
import sys


def load_audio_ffmpeg(path, sr=16000):
	"""Decode audio to mono float32 using ffmpeg."""
	out, _ = (
		ffmpeg
		.input(path)
		.output('pipe:', format='f32le', acodec='pcm_f32le', ac=1, ar=sr)
		.run(capture_stdout=True, capture_stderr=True)
	)
	audio = np.frombuffer(out, np.float32)
	return audio, sr

def get_mel_signatures(audio, sr, chunk_sec=1.0):
	"""Split audio into chunks and return mel spectrogram signatures per chunk."""
	samples_per_chunk = int(sr * chunk_sec)
	n_chunks = len(audio) // samples_per_chunk
	features = []

	for i in range(n_chunks):
		chunk = audio[i * samples_per_chunk: (i + 1) * samples_per_chunk]
		S = librosa.feature.melspectrogram(y=chunk, sr=sr, n_mels=40, fmax=8000)
		S_db = librosa.power_to_db(S, ref=np.max)
		signature = np.mean(S_db, axis=1)  # average over time
		features.append(signature)

	return np.array(features)

def compute_distances(features):
	"""Compute cosine distance between each pair of successive feature vectors."""
	from scipy.spatial.distance import cosine
	distances = [cosine(features[i], features[i + 1]) for i in range(len(features) - 1)]
	return distances

def plot_distances(distances, chunk_sec=1.0):
	times = np.arange(1, len(distances) + 1) * chunk_sec
	plt.figure(figsize=(12, 6))
	plt.plot(times, distances)
	plt.title("Cosine Distance Between 1s Audio Chunks")
	plt.xlabel("Time (s)")
	plt.ylabel("Spectral Distance")
	plt.grid(True)
	plt.show()

if __name__ == "__main__":
	if len(sys.argv) != 2:
		print("Usage: python analyze_audio_signature.py path_to_file.opus")
		sys.exit(1)

	audio, sr = load_audio_ffmpeg(sys.argv[1])
	features = get_mel_signatures(audio, sr)
	distances = compute_distances(features)
	plot_distances(distances)
