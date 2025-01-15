import os
import sys
import timeit
import subprocess


def get_filename(file_path):
    return os.path.basename(file_path).split('.')[0]


def validate_audio_file(file_path):
    """
    Checks if the given path points to a valid WAV audio file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"WAV file not found: {file_path}")
    if not file_path.lower().endswith(".wav"):
        raise ValueError(f"Invalid file format, expecting a WAV file.")


def transcribe(audio_file, output_path="files/transcripts", model_path=None):
    """
    Transcribes the given audio file using the whisper.cpp local Whisper model. Returns a tuple
    containing the transcription result, elapsed time in seconds, and the transcript path.
    """
    filename_only = get_filename(audio_file)

    # Validate audio file
    validate_audio_file(audio_file)

    # Use provided model path or default
    if model_path is None:
        model_path = "/Users/vincent/development/whisper.cpp/models/ggml-medium.en.bin"

    start_time = timeit.default_timer()

    full_command = f"/Users/vincent/development/whisper.cpp/main -m {model_path} -f {audio_file} -np -nt"
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

    return elapsed_time, processed_str, text_path


if __name__ == "__main__":
    if len(sys.argv) > 1:
        audio_path = sys.argv[1]
        try:
            elapsed_time, transcript, transcript_path = transcribe(audio_path)
            print(f"Audio transcribed in {elapsed_time} seconds. Transcript saved to: {transcript_path}")
            # Optional: print transcript to console as well
            # print(f"\nTranscript:\n{transcript}")
        except Exception as e:
            print(f"Error transcribing audio: {e}")
    else:
        print("Usage: python whisper_transcribe.py <audio_path> (optional: -m <model_path>)")
