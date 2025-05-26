import ffmpeg
import numpy as np
import matplotlib.pyplot as plt
import sys
import tqdm

def load_audio_ffmpeg(path, sr=16000):
	"""Load audio using ffmpeg and return mono float32 numpy array."""
	out, _ = (
		ffmpeg
		.input(path)
		.output('pipe:', format='f32le', acodec='pcm_f32le', ac=1, ar=sr)
		.run(capture_stdout=True, capture_stderr=True)
	)
	audio = np.frombuffer(out, np.float32)
	return audio, sr

def analyze_changes(data, samplerate, window_sec=1.0):
	samples_per_window = int(window_sec * samplerate)
	rms_values = []

	for start in tqdm.tqdm(range(0, len(data), samples_per_window)):
		chunk = data[start:start + samples_per_window]
		if len(chunk) == 0:
			continue
		rms = np.sqrt(np.mean(chunk**2))
		rms_values.append(rms)

	changes = np.abs(np.diff(rms_values))
	return changes, np.arange(1, len(rms_values)) * window_sec

def plot_changes(changes, times, threshold=None):
	plt.figure(figsize=(12, 6))
	plt.plot(times, changes, label="RMS Change")
	if threshold is not None:
		plt.axhline(threshold, color='red', linestyle='--', label="Threshold")
	plt.title("RMS Change Between Successive 1s Windows")
	plt.xlabel("Time (s)")
	plt.ylabel("RMS Change")
	plt.grid(True)
	plt.legend()
	plt.tight_layout()
	plt.show()

if __name__ == "__main__":
	if len(sys.argv) != 2:
		print("Usage: python analyze_opus.py path_to_file.opus")
		sys.exit(1)

	path = sys.argv[1]
	audio, sr = load_audio_ffmpeg(path)
	changes, times = analyze_changes(audio, sr)
	plot_changes(changes, times)
