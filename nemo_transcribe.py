#!/usr/bin/env python3
"""Multi-speaker meeting transcription using NeMo ASR + Speaker Diarization.

Pipeline:
  1. Diarization: VAD (MarbleNet) → Speaker Embeddings (TitaNet) → Clustering
  2. ASR: Parakeet-TDT-0.6B transcribes the full audio with word timestamps
  3. Merge: Word timestamps aligned to speaker segments → speaker-labeled transcript

Usage:
    python nemo_transcribe.py meeting.m4a
    python nemo_transcribe.py meeting.m4a --max-speakers 5 -o transcript.txt
"""
import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

import torch
from omegaconf import OmegaConf, open_dict
from nemo.collections.asr.models import ClusteringDiarizer
import nemo.collections.asr as nemo_asr


def convert_to_wav(input_path: str, output_path: str) -> str:
    subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", output_path],
        capture_output=True, check=True,
    )
    return output_path


def create_manifest(wav_path: str, manifest_path: str):
    entry = {
        "audio_filepath": os.path.abspath(wav_path),
        "offset": 0, "duration": None, "label": "infer",
        "text": "-", "num_speakers": None,
        "rttm_filepath": None, "uem_filepath": None,
    }
    with open(manifest_path, "w") as f:
        json.dump(entry, f)
        f.write("\n")


def parse_rttm(rttm_path: str):
    """Parse RTTM file into list of (start, end, speaker) tuples."""
    segments = []
    with open(rttm_path) as f:
        for line in f:
            parts = line.strip().split()
            if parts[0] == "SPEAKER":
                start = float(parts[3])
                dur = float(parts[4])
                speaker = parts[7]
                segments.append((start, start + dur, speaker))
    segments.sort(key=lambda x: x[0])
    return segments


def assign_words_to_speakers(words_with_ts, speaker_segments):
    """Assign each word to the speaker whose segment overlaps most, or nearest speaker."""
    result = []
    for word, start, end in words_with_ts:
        mid = (start + end) / 2
        best_speaker = None
        best_dist = float('inf')
        for seg_start, seg_end, speaker in speaker_segments:
            if seg_start <= mid <= seg_end:
                best_speaker = speaker
                break
            # Track nearest segment for fallback
            dist = min(abs(mid - seg_start), abs(mid - seg_end))
            if dist < best_dist:
                best_dist = dist
                best_speaker = speaker
        result.append((word, start, end, best_speaker or "unknown"))
    return result


def format_speaker_transcript(labeled_words):
    """Group consecutive words by speaker into readable transcript."""
    if not labeled_words:
        return "(no transcript generated)"
    lines = []
    current_speaker = None
    current_words = []
    current_start = 0
    for word, start, end, speaker in labeled_words:
        if speaker != current_speaker:
            if current_words:
                ts = f"[{current_start:.1f}s]"
                lines.append(f"{ts} {current_speaker}: {' '.join(current_words)}")
            current_speaker = speaker
            current_words = [word]
            current_start = start
        else:
            current_words.append(word)
    if current_words:
        ts = f"[{current_start:.1f}s]"
        lines.append(f"{ts} {current_speaker}: {' '.join(current_words)}")
    return "\n".join(lines)


def run_diarization(manifest_path: str, out_dir: str, max_speakers: int = 8):
    """Run NeMo cascaded diarization (no ASR)."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    cfg = OmegaConf.create({
        "device": device,
        "num_workers": 0,
        "sample_rate": 16000,
        "batch_size": 64,
        "verbose": True,
        "diarizer": {
            "manifest_filepath": manifest_path,
            "out_dir": out_dir,
            "oracle_vad": False,
            "collar": 0.25,
            "ignore_overlap": True,
            "vad": {
                "model_path": "vad_multilingual_marblenet",
                "parameters": {
                    "window_length_in_sec": 0.15,
                    "shift_length_in_sec": 0.01,
                    "smoothing": "median",
                    "overlap": 0.875,
                    "onset": 0.4, "offset": 0.7,
                    "pad_onset": 0.05, "pad_offset": -0.1,
                    "min_duration_on": 0.2, "min_duration_off": 0.2,
                    "filter_speech_first": True,
                },
            },
            "speaker_embeddings": {
                "model_path": "titanet_large",
                "parameters": {
                    "window_length_in_sec": 1.5,
                    "shift_length_in_sec": 0.75,
                    "multiscale_weights": None,
                    "save_embeddings": False,
                },
            },
            "clustering": {
                "parameters": {
                    "oracle_num_speakers": False,
                    "max_num_speakers": max_speakers,
                    "enhanced_count_thres": 80,
                    "max_rp_threshold": 0.25,
                    "sparse_search_volume": 30,
                },
            },
        },
    })
    diarizer = ClusteringDiarizer(cfg=cfg)
    diarizer.diarize()


def run_asr_with_timestamps(wav_path: str):
    """Run Parakeet ASR with word timestamps, chunking long audio."""
    import soundfile as sf

    print("Loading Parakeet ASR model...")
    asr_model = nemo_asr.models.ASRModel.from_pretrained("nvidia/parakeet-tdt-0.6b-v2")
    if torch.cuda.is_available():
        asr_model = asr_model.cuda()
    # Disable CUDA graphs to avoid version mismatch issues
    with open_dict(asr_model.cfg.decoding):
        asr_model.cfg.decoding.greedy.use_cuda_graph_decoder = False
    asr_model.change_decoding_strategy(asr_model.cfg.decoding)

    data, sr = sf.read(wav_path)
    total_dur = len(data) / sr
    chunk_sec = 300  # 5 min chunks to avoid OOM
    all_words = []

    for start in range(0, int(total_dur), chunk_sec):
        end = min(start + chunk_sec, total_dur)
        chunk_data = data[int(start * sr):int(end * sr)]
        chunk_path = wav_path.replace(".wav", f"_chunk_{start}.wav")
        sf.write(chunk_path, chunk_data, sr)

        print(f"  Transcribing {start:.0f}s - {end:.0f}s ...")
        output = asr_model.transcribe([chunk_path], timestamps=True)
        hyp = output[0]

        # Extract word-level timestamps from hypothesis
        # Parakeet uses hyp.timestamp dict with 'word' key, and hyp.words list
        got_words = False
        if hasattr(hyp, 'timestamp') and hyp.timestamp and 'word' in hyp.timestamp:
            for i, ts_entry in enumerate(hyp.timestamp['word']):
                word_text = hyp.words[i] if hasattr(hyp, 'words') and i < len(hyp.words) else str(ts_entry)
                w_start = ts_entry['start'] if isinstance(ts_entry, dict) else ts_entry.start
                w_end = ts_entry['end'] if isinstance(ts_entry, dict) else ts_entry.end
                all_words.append((word_text, w_start + start, w_end + start))
            got_words = True
        if not got_words and hasattr(hyp, 'text') and hyp.text:
            # Fallback: plain text without word timestamps
            all_words.append((hyp.text, start, end))
        os.remove(chunk_path)

    print(f"ASR complete: {len(all_words)} words transcribed")
    return all_words


def main():
    parser = argparse.ArgumentParser(description="Multi-speaker meeting transcription (NeMo)")
    parser.add_argument("audio", help="Path to audio file")
    parser.add_argument("--max-speakers", type=int, default=8)
    parser.add_argument("--output", "-o", help="Output file path")
    args = parser.parse_args()

    audio_path = os.path.abspath(args.audio)
    audio_name = Path(audio_path).stem

    with tempfile.TemporaryDirectory(prefix="nemo_diar_") as tmpdir:
        wav_path = os.path.join(tmpdir, f"{audio_name}.wav")
        print(f"Converting {audio_path} to 16kHz WAV...")
        convert_to_wav(audio_path, wav_path)

        # Step 1: Diarization
        manifest_path = os.path.join(tmpdir, "manifest.json")
        create_manifest(wav_path, manifest_path)
        out_dir = os.path.join(tmpdir, "output")
        os.makedirs(out_dir, exist_ok=True)
        print(f"Running speaker diarization (max {args.max_speakers} speakers)...")
        run_diarization(manifest_path, out_dir, args.max_speakers)

        # Parse RTTM
        rttm_dir = os.path.join(out_dir, "pred_rttms")
        rttm_files = [f for f in os.listdir(rttm_dir) if f.endswith(".rttm")] if os.path.isdir(rttm_dir) else []
        if not rttm_files:
            print("ERROR: No RTTM output from diarization")
            return
        speaker_segments = parse_rttm(os.path.join(rttm_dir, rttm_files[0]))
        n_speakers = len(set(s for _, _, s in speaker_segments))
        print(f"Diarization complete: {n_speakers} speakers, {len(speaker_segments)} segments")

        # Step 2: ASR with timestamps
        words_with_ts = run_asr_with_timestamps(wav_path)

        # Step 3: Merge
        print("Merging ASR words with speaker labels...")
        labeled_words = assign_words_to_speakers(words_with_ts, speaker_segments)
        transcript = format_speaker_transcript(labeled_words)

        # Output
        out_path = args.output or str(Path(audio_path).with_suffix(".transcript.txt"))
        with open(out_path, "w") as f:
            f.write(transcript)
        print(f"\nTranscript saved to: {out_path}")
        print(f"\n{'='*80}\n")
        print(transcript[:3000])
        if len(transcript) > 3000:
            print(f"\n... ({len(transcript)} chars total, see {out_path})")


if __name__ == "__main__":
    main()
