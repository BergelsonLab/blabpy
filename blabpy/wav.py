import wave

import numpy as np


def apply_log_fade(audio, start_frame, end_frame, length_ms, fade_lower_end):
    """
    Apply logarithmic fade-in and fade-out effects at both ends of an audio segment.

    Args:
        audio: numpy array containing audio data
        start_frame: starting frame index for the segment
        end_frame: ending frame index for the segment
        length_ms: length of fade in frames
        fade_lower_end: minimum volume as fraction (e.g., 0.01 = 1%)
    """
    fade_in = np.logspace(np.log10(fade_lower_end), 0, length_ms, base=10)
    fade_out = np.logspace(0, np.log10(fade_lower_end), length_ms, base=10)
    audio[start_frame:start_frame + length_ms] = (audio[start_frame:start_frame + length_ms].astype(np.float64) * fade_in).astype(np.int16)
    audio[end_frame - length_ms:end_frame] = (audio[end_frame - length_ms:end_frame].astype(np.float64) * fade_out).astype(np.int16)


def blackout(input_wav, output_wav, intervals_ms, fade_ms=500, fade_lower_end=0.01, blackout_intervals=False):
    """
    Modifies audio based on the specified intervals. If blackout_intervals is False (default), the audio is blacked out
    except for the specified intervals. If blackout_intervals is True, the audio is blacked out only within the
    specified intervals.

    :param input_wav: path to the input WAV file
    :param output_wav: path to the output WAV file
    :param intervals_ms: a list of (start_ms, end_ms) tuples
    :param fade_ms: the duration of the fade in and fade out in milliseconds
    :param fade_lower_end: the lower end of the fade (0.01 means 1% of the original volume)
    :param blackout_intervals: if True, blackout the intervals; if False, blackout everything except the intervals
    :return: None

    Example:
    intervals_ms = [(1000, 2000), (3500, 4500)]  # Intervals in milliseconds
    blackout_wav('input.wav', 'output.wav', intervals_ms, fade_ms=10, fade_lower_end=0.01)
    """
    if fade_ms < 0:
        raise ValueError("fade_ms must be non-negative")

    if fade_lower_end <= 0 or fade_lower_end >= 1:
        raise ValueError("fade_lower_end must be between 0 and 1 (exclusive)")

    # Open the input WAV file
    with wave.open(input_wav, 'rb') as wav_in:
        # Get the parameters from the input file
        params = wav_in.getparams()
        n_channels, sampwidth, framerate, n_frames, comptype, compname = params
        audio_data = wav_in.readframes(n_frames)

    # Convert audio data to numpy array
    if not sampwidth == 2:
        raise ValueError("Only 16-bit (sampwidth=2) WAV files are supported.")
        # note: if adding support for other sampwidths, make sure to update apply_log_fade as well
    audio_array = np.frombuffer(audio_data, dtype=np.int16)

    # If blackout_intervals is True, invert the intervals
    if blackout_intervals:
        # Sort intervals
        sorted_intervals = sorted(intervals_ms)
        file_duration_ms = int(n_frames * 1000 / framerate)

        # Create the complementary intervals by pairing each end with the next start
        starts = [0] + [end for _, end in sorted_intervals]
        ends = [start for start, _ in sorted_intervals] + [file_duration_ms]
        intervals_ms = [(start, end) for start, end in zip(starts, ends) if start < end]

    # Convert intervals from milliseconds to frames
    interval_frames = [(int(start_ms * framerate / 1000), int(end_ms * framerate / 1000))
                       for start_ms, end_ms in intervals_ms]

    # Convert fade duration from milliseconds to frames
    fade_length = int(fade_ms * framerate / 1000)

    # Start with silence and copy the audio from the intervals
    blackout_audio = np.zeros_like(audio_array)
    for start_frame, end_frame in interval_frames:
        blackout_audio[start_frame:end_frame] = audio_array[start_frame:end_frame]
        apply_log_fade(blackout_audio, start_frame, end_frame, fade_length, fade_lower_end)

    # Convert the blackout audio array back to bytes
    blackout_audio_bytes = blackout_audio.tobytes()

    # Write the blackout audio to the output WAV file
    with wave.open(output_wav, 'wb') as wav_out:
        wav_out.setparams(params)
        wav_out.writeframes(blackout_audio_bytes)