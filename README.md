# Transcribe and summarize video

Clone repository and cd into the repository

### macOS Installation Guide

Below is the installation process for macOS. 

#### Setting Up the Environment

```
install whisper.cpp
install llama.cpp
pip3 install -r requirements.txt
python3 -m spacy download en_core_web_sm
brew install ffmpeg
source ~/.whisper/bin/activate
```
The default llama.cpp model is mistral-7b-instruct-v0.2.Q4_K_M.gguf. If you want to change it, go to summarize_model.py.

But that means you also have to adjust this as appropriate 
```
MODEL_MAX_TOKENS = 8192  # Maximum tokens for prompt and response
WINDOW_SIZE = 4096  # Maximum tokens for the input
```
Run the whole workflow using
```
python3 main.py --input_path "/path/to/your/video" --title "My Video Title"
```
Remember the longer the video, the more time it might take to summarize.

TODO:
Flaskify
