import os
import sys
import timeit
import subprocess


def get_filename(file_path):
    return os.path.basename(file_path).split('.')[0]


def transcribe(audio_file, output_path="files/transcripts"):
    """
    Transcribes the given audio file using the whisper.cpp local Whisper model. Returns a tuple
    containing the transcription result and the elapsed time in seconds.
    """
    filename_only = get_filename(audio_file)
    model = "/Users/vincent/development/whisper.cpp/models/ggml-medium.en.bin"
    start_time = timeit.default_timer()

    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"WAV file not found: {audio_file}")

    full_command = f"/Users/vincent/development/whisper.cpp/main -m /Users/vincent/development/whisper.cpp/models/ggml-medium.en.bin -f {audio_file} -np -nt"
    process = subprocess.Popen(full_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()

    if error:
        raise Exception(f"Error processing audio: {error.decode('utf-8')}")

    # Process and return the output string
    decoded_str = output.decode('utf-8').strip()
    processed_str = decoded_str.replace('[BLANK_AUDIO]', '').strip()
    end_time = timeit.default_timer()
    elapsed_time = int(end_time - start_time)

    if not os.path.exists(output_path):
        os.makedirs(output_path)
    
    text_path = os.path.join(output_path, f"{filename_only}.txt")
    with open(text_path, "w") as file:
        file.write(processed_str)

    return elapsed_time, text_path


if __name__ == "__main__":
    if len(sys.argv) > 1:
        audio_path = sys.argv[1]
        elapsed_time, transcript_path = transcribe(audio_path)
        print(f"Audio has been transcribed in {elapsed_time} seconds. Path: {transcript_path}")
    else:
        print("Usage: python whisper_transcribe.py <audio_path>")
