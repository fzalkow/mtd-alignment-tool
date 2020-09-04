import os
import argparse
import json
import glob
import multiprocessing as mp

import numpy as np
import librosa
from tqdm import tqdm

from app.common import STATIC_DIR, extract_iir_chroma


def extract_features(fn_audio, fn_out):
    x, sr = librosa.load(fn_audio, sr=22050, mono=True)
    f_chroma, times = extract_iir_chroma(x, sr)
    np.savez_compressed(fn_out, f_chroma=f_chroma, f_chroma_ax_time=times, f_chroma_ax_freq=np.arange(12))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', help='PRODUCTION (=multiprocessing) or DEVELOP', default='PRODUCTION',
                        choices=['PRODUCTION', 'DEVELOP'])
    parser.add_argument('--dir-out', help='Directory to write', default=os.path.join(STATIC_DIR, 'data_AUDIO_IIRT'))
    args = parser.parse_args()

    os.makedirs(args.dir_out, exist_ok=True)

    with open('config.json', 'r') as stream:
        config = json.load(stream)

    files = sorted(glob.glob(os.path.join(config['dir_mtd'], '03_MTD-medium', 'data_AUDIO', '*.wav')))

    if args.mode == 'DEVELOP':
        for fn_audio in tqdm(files):
            fn_out = os.path.join(args.dir_out, os.path.splitext(os.path.basename(fn_audio))[0] + '.npz')
            if not os.path.exists(fn_out):
                extract_features(fn_audio, fn_out)

    else:
        n_workers = mp.cpu_count()
        pool = mp.Pool(n_workers)

        with tqdm(total=len(files), desc='Execute jobs', dynamic_ncols=True) as pbar:
            for fn_audio in files:
                fn_out = os.path.join(args.dir_out, os.path.splitext(os.path.basename(fn_audio))[0] + '.npz')
                if not os.path.exists(fn_out):
                    pool.apply_async(extract_features, args=[fn_audio, fn_out],
                                     callback=lambda _: pbar.update(),
                                     error_callback=lambda x: tqdm.write(str(x)))
                else:
                    pbar.update()

            pool.close()  # no more jobs will be added
            pool.join()
