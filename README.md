# Audio Transcriber

Multi-speaker meeting transcription with speaker diarization, optimized for NVIDIA GPUs.

Uses NeMo's cascaded speaker diarization pipeline + Parakeet ASR:
- **VAD**: MarbleNet (voice activity detection)
- **Speaker Embeddings**: TitaNet-Large
- **Clustering**: Spectral clustering (auto-detects number of speakers)
- **ASR**: Parakeet-TDT-0.6B-v2 (NVIDIA's open-source ASR with word timestamps)

No API keys or HuggingFace tokens required. All models auto-download from NGC/HuggingFace on first run.

## Requirements

- NVIDIA GPU (tested on H100, should work on any CUDA GPU with ≥16GB VRAM)
- Docker with NVIDIA Container Toolkit
- ~4GB disk for model downloads (cached after first run)

## Quick Start (Docker on GPU cluster)

```bash
# 1. Launch the container
bash docker/launch_transcriber.sh

# 2. Inside the container, transcribe an audio file
python nemo_transcribe.py /workspace/data/uploads/meeting.m4a

# With options
python nemo_transcribe.py meeting.m4a --max-speakers 5 -o transcript.txt
```

## Setup

### Docker (recommended)

The Docker image includes all dependencies. Build and launch:

```bash
# Build image (automatic on first launch)
docker build -t transcriber:v2 -f docker/Dockerfile.transcriber-v2 docker/

# Launch container (edit paths in launch_transcriber.sh for your setup)
bash docker/launch_transcriber.sh
```

### Manual install (conda)

```bash
conda create -n transcriber python=3.11 -y
conda activate transcriber
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
pip install "nemo_toolkit[asr]" soundfile pydub
```

## Usage

```bash
# Basic — auto-detects speakers, outputs to <input>.transcript.txt
python nemo_transcribe.py recording.m4a

# Specify max speakers and output path
python nemo_transcribe.py recording.m4a --max-speakers 4 -o notes.txt

# Supports any format ffmpeg can read: m4a, mp3, wav, ogg, flac, etc.
python nemo_transcribe.py podcast.mp3 -o podcast-transcript.txt
```

## Output format

Speaker-labeled transcript with timestamps:

```
[0.2s] speaker_1: So basically our goal is to make sure that our performance is on par.
[15.4s] speaker_0: I think we should test both. That's also something.
[34.2s] speaker_1: Yeah, I think just picking two that are representative is good enough.
[116.2s] speaker_2: Maybe one clarification here...
```

## Performance

On H100 (with cached models):
- 73-min meeting → ~2.5 min processing
- 32-min 1:1 → ~1.5 min processing
- 20-min 1:1 → ~1 min processing

First run downloads ~4GB of models and takes longer.

## Project structure

```
nemo_transcribe.py              # Main transcription script (NeMo pipeline)
docker/
  Dockerfile.transcriber-v2     # GPU Docker image with NeMo + dependencies
  launch_transcriber.sh         # Container launch script
data/
  uploads/                      # Input audio files
  transcripts/                  # Output transcripts
```

## Legacy

The `app.py`, `transcribe.py`, `core/`, and `config.py` files are from an older WhisperX-based implementation. The current recommended approach is `nemo_transcribe.py`.
