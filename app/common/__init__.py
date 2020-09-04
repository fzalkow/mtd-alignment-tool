import os

import numpy as np
import librosa

FEATURE_RATE = 10
STATIC_DIR = os.path.join('app', 'static')


def midi_data_to_chroma(midi_data, feature_rate, transpose=0):

    start, end = get_start_end_midi(midi_data)
    time_steps = int(np.ceil(end * feature_rate))
    f_chroma = np.zeros((12, time_steps))

    for cur_instrument in midi_data.instruments:
        for cur_note in cur_instrument.notes:
            cur_chroma = (cur_note.pitch + transpose) % 12
            cur_start = int(round(cur_note.start * feature_rate))
            cur_end = int(round(cur_note.end * feature_rate))
            cur_velo = cur_note.velocity / 128.0
            f_chroma[cur_chroma, cur_start:cur_end] = cur_velo

    return f_chroma


def get_start_end_midi(midi_data):
    min_start, max_end = float('inf'), 0

    for cur_instrument in midi_data.instruments:
        for cur_note in cur_instrument.notes:
            if cur_note.start < min_start:
                min_start = cur_note.start
            if cur_note.end > max_end:
                max_end = cur_note.end

    return min_start, max_end


def extract_iir_chroma(x, sr):
    hop_length = sr / FEATURE_RATE
    assert (hop_length).is_integer()

    X = librosa.iirt(x, sr=sr, win_length=hop_length*2, hop_length=hop_length, center=True)
    times = np.arange(X.shape[1]) * (hop_length / sr)

    fmin = librosa.midi_to_hz(24)
    f_chroma = librosa.feature.chroma_cqt(C=X, fmin=fmin, bins_per_octave=12, n_octaves=7)

    return f_chroma, times


def make_warping_path_strictly_monotonic(wp):
    wp = wp.copy()
    w1 = wp[:, 0]
    w2 = wp[:, 1]

    unique1, count1 = np.unique(w1, return_counts=True)
    unique2, count2 = np.unique(w2, return_counts=True)

    while np.any(count1 > 1) or np.any(count2 > 1):

        for val in unique1[count1 > 1]:
            idx = np.where(w1 == val)[0]
            min_idx = max(0, idx[0] - 1)
            max_idx = min(len(w1) - 1, idx[-1] + 1)
            start_val = w1[min_idx]
            end_val = w1[max_idx]

            w1[min_idx:max_idx + 1] = np.linspace(start_val, end_val, max_idx - min_idx + 1)

        for val in unique2[count2 > 1]:
            idx = np.where(w2 == val)[0]
            min_idx = max(0, idx[0] - 1)
            max_idx = min(len(w2) - 1, idx[-1] + 1)
            start_val = w2[min_idx]
            end_val = w2[max_idx]

            w2[min_idx:max_idx + 1] = np.linspace(start_val, end_val, max_idx - min_idx + 1)

        unique1, count1 = np.unique(w1, return_counts=True)
        unique2, count2 = np.unique(w2, return_counts=True)

    return np.stack((w1, w2), axis=1)
