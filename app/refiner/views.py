import ast
import os
import glob
from io import BytesIO
import base64
import json

from IPython import display as ipd
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from scipy.misc import imresize
import pretty_midi
import librosa
import PIL.Image
import soundfile as sf
from flask import render_template, flash, url_for, request, redirect, session, Markup, current_app

from . import refiner
from .. import common


def get_paths():
    return {
        'data_AUDIO': os.path.join(current_app.config['dir_mtd'], '03_MTD-medium', 'data_AUDIO'),
        'data_ALIGNMENT': os.path.join(current_app.config['dir_mtd'], '03_MTD-medium', 'data_ALIGNMENT'),
        'data_EDM-corr_MID': os.path.join(current_app.config['dir_mtd'], '03_MTD-medium', 'data_EDM-corr_MID'),
        'data_ALIGNMENT-annotated': os.path.join(common.STATIC_DIR, 'data_ALIGNMENT-annotated'),
        'data_AUDIO_IIRT-annotated': os.path.join(common.STATIC_DIR, 'data_AUDIO_IIRT-annotated'),
        'data_AUDIO_IIRT': os.path.join(common.STATIC_DIR, 'data_AUDIO_IIRT'),
        'data_AUDIO-annotated': os.path.join(common.STATIC_DIR, 'data_AUDIO-annotated'),
    }


def get_mtd_row(mtd_id):
    df_medium = pd.read_csv(os.path.join(current_app.config['dir_mtd'], '03_MTD-medium.csv'), sep=';')
    row = df_medium[df_medium['MTDID'] == mtd_id]
    assert len(row) == 1
    return row


def get_wcm_for_mtd(mtd_id):
    row = get_mtd_row(mtd_id)
    directory = current_app.config['data_AUDIO-WCM']
    if not os.path.exists(directory):
        flash(f'The WCM directory ({directory}) does not exist.')
        return None

    wcm_id = str(row['WCMID'].iloc[0])

    file = glob.glob(os.path.join(directory, '*WCM' + wcm_id + '.wav'))
    assert len(file) == 1, (file, os.path.join(directory, '*WCM' + wcm_id + '.wav'))
    return file[0]


def get_mtd_str(s):
    if '-' in s:
        part1, part2 = s.split('-')
        return 'MTD%04d-%s' % (int(part1), part2)
    else:
        return 'MTD%04d' % int(s)


def check_file_glob(globber, mtd_id_str, entry_type):
    fn = glob.glob(globber)
    if len(fn) != 1:
        flash('There are %d %s-entries for the MTDID "%s".' % (len(fn), entry_type, mtd_id_str))
        return None
    else:
        return fn[0]


def adjust_midi(midi_data, wp):
    f = interp1d(wp[:, 0], wp[:, 1], fill_value='extrapolate')

    for cur_instrument in midi_data.instruments:
        for cur_note in cur_instrument.notes:
            cur_note.start = max(0, f(cur_note.start))
            cur_note.end = max(0, f(cur_note.end))

    return midi_data


def time_str_to_sec(t):
    mm, ss = t.split(':')
    return float(mm) * 60 + float(ss)


def get_start_end_time_duration(mtd_id):
    mtd_row = get_mtd_row(mtd_id)
    path_dict = get_paths()

    fn_wcm_wav = get_wcm_for_mtd(mtd_id)
    with sf.SoundFile(fn_wcm_wav, 'r') as stream:
        duration = len(stream) / stream.samplerate

    mtd_id_str = get_mtd_str(mtd_id)
    fn_json = os.path.join(path_dict['data_AUDIO_IIRT-annotated'], mtd_id_str + '.json')

    if os.path.exists(fn_json):
        with open(fn_json, 'r') as stream:
            data = json.load(stream)
        return data['start'], data['end'], duration

    else:
        start = round(time_str_to_sec(mtd_row.iloc[0]['StartTime']), 1)
        end = round(time_str_to_sec(mtd_row.iloc[0]['EndTime']), 1)
        return start, end, duration


def write_sync_csv(wp, fn_out, fn_mid, fn_mtd_wav):
    midi_data = pretty_midi.PrettyMIDI(fn_mid)
    mid_symbol_end = max(note.end for inst in midi_data.instruments for note in inst.notes)

    with sf.SoundFile(fn_mtd_wav, 'r') as stream:
        duration_wav = len(stream) / stream.samplerate
    duration_wav = duration_wav + 0.05  # half frame for safety

    wp = np.concatenate((wp, [[mid_symbol_end, duration_wav]]))

    df = pd.DataFrame(wp, columns=['"MID"', '"WAV"'])
    df.to_csv(fn_out, sep=';', index=False, float_format='%.5f', quoting=3)


@refiner.route('/<mtd_id>.html')
def index(mtd_id):
    mtd_id_str = get_mtd_str(mtd_id)
    df_medium_row = get_mtd_row(mtd_id)
    wcm_id = df_medium_row['WCMID'].values[0]

    path_dict = get_paths()

    # files from original mtd data set
    fn_wav = check_file_glob(os.path.join(path_dict['data_AUDIO'], f'{mtd_id_str}_*.wav'), mtd_id_str, 'wav')
    fn_csv = check_file_glob(os.path.join(path_dict['data_ALIGNMENT'], f'{mtd_id_str}_*.csv'), mtd_id_str, 'sync-csv')
    fn_mid = check_file_glob(os.path.join(path_dict['data_EDM-corr_MID'], f'{mtd_id_str}_*.mid'), mtd_id_str, 'mid')

    # files computed for this interface
    fn_npz = check_file_glob(os.path.join(path_dict['data_AUDIO_IIRT'], f'{mtd_id_str}_*.npz'), mtd_id_str, 'npz')

    # files generated by the interface
    fn_csv_new = os.path.join(path_dict['data_ALIGNMENT-annotated'], os.path.basename(fn_csv))
    fn_npz_new = os.path.join(path_dict['data_AUDIO_IIRT-annotated'], os.path.basename(fn_npz))
    fn_wav_new = os.path.join(path_dict['data_AUDIO-annotated'], os.path.basename(fn_wav))

    cur_transpose = df_medium_row.iloc[0]['MidiTransposition']

    remove_new_annotations = False
    if os.path.exists(fn_csv_new):
        remove_new_annotations = True
        flash('You are using an already modified warping path.')
        fn_csv = fn_csv_new

    if os.path.exists(fn_npz_new) and os.path.exists(fn_wav_new):
        remove_new_annotations = True
        flash('You are using an audio excerpt with changed durations.')
        fn_npz = fn_npz_new
        fn_wav = fn_wav_new

    if remove_new_annotations:
        flash(Markup('<a href="%s">Remove annotations!</a>' % url_for('refiner.remove_annotations', mtd_id=mtd_id)))

    if get_wcm_for_mtd(mtd_id):
        wcm_start_time, wcm_end_time, wcm_duration = get_start_end_time_duration(mtd_id)
        change_duration_url = url_for('refiner.change_duration', mtd_id=mtd_id)
    else:
        wcm_start_time, wcm_end_time, wcm_duration = 0.0, 0.0, 0.0
        change_duration_url = '#'

    if 'wp' in session and session['wp_mtd_id'] == mtd_id:
        wp = np.array(session['wp'])
    elif fn_csv:
        df_sync = pd.read_csv(fn_csv, sep=';')
        wp = df_sync.values
    else:
        wp = np.array([])

    session.pop('wp', None)
    session.pop('wp_mtd_id', None)

    if fn_npz and fn_mid:

        midi_data = pretty_midi.PrettyMIDI(fn_mid)
        x_mid = common.midi_data_to_chroma(midi_data, common.FEATURE_RATE)
        x_mid = np.roll(x_mid, cur_transpose, axis=0)
        x_wav = np.load(fn_npz)['f_chroma']

        x_mid = librosa.util.normalize(x_mid, norm=2, fill=True, axis=0)
        x_wav = librosa.util.normalize(x_wav, norm=2, fill=True, axis=0)

        x_mid_img = np.uint8((1 - x_mid) * ((2 ** 8) - 1))
        x_wav_img = np.uint8((1 - x_wav) * ((2 ** 8) - 1))
        x_mid_img = np.flipud(x_mid_img)
        x_wav_img = np.flipud(x_wav_img)

        scale_fac = np.ceil(1170.0 / min(x_mid.shape[1], x_wav.shape[0]))
        x_mid_img = imresize(x_mid_img, scale_fac, 'nearest')
        x_wav_img = imresize(x_wav_img, scale_fac, 'nearest')

        buffered = BytesIO()
        PIL.Image.fromarray(x_mid_img).save(buffered, 'png')
        img_src_mid = 'data:image/png;base64,' + base64.b64encode(buffered.getvalue()).decode("utf-8")

        buffered = BytesIO()
        PIL.Image.fromarray(x_wav_img).save(buffered, 'png')
        img_src_wav = 'data:image/png;base64,' + base64.b64encode(buffered.getvalue()).decode("utf-8")

    else:
        img_src_mid = ''
        img_src_wav = ''
        scale_fac = 1.0

    if fn_wav:
        x_wav, sr = librosa.load(fn_wav, sr=22050, mono=True)
        audio_wav = ipd.Audio(data=x_wav, rate=sr).src_attr()
    else:
        audio_wav = ''

    if fn_mid and fn_csv:
        midi_data_align = pretty_midi.PrettyMIDI(fn_mid)
        for instrument in midi_data_align.instruments:
            for note in instrument.notes:
                note.pitch += cur_transpose

        wp_strict = common.make_warping_path_strictly_monotonic(wp)
        midi_data_align = adjust_midi(midi_data_align, wp_strict)

        x_audio, sr = librosa.load(fn_wav, sr=22050, mono=True)
        x_midi_align = midi_data_align.synthesize(fs=22050)

        audio_mid_align = ipd.Audio(data=x_midi_align, rate=22050).src_attr()

        if x_midi_align.shape[0] > x_audio.shape[0]:
            x_midi_align = x_midi_align[:x_audio.shape[0]:]
        elif x_audio.shape[0] > x_midi_align.shape[0]:
            x_midi_align = np.concatenate((x_midi_align, np.zeros(x_audio.shape[0] - x_midi_align.shape[0])))

        # normalize
        x_audio = x_audio / np.max(x_audio)
        x_midi_align = x_midi_align / np.max(x_midi_align)

        x = np.stack([x_audio, x_midi_align], axis=0)
        audio_both = ipd.Audio(data=x, rate=22050).src_attr()

        midi_data = pretty_midi.PrettyMIDI(fn_mid)
        for instrument in midi_data.instruments:
            for note in instrument.notes:
                note.pitch += cur_transpose

        x_midi = midi_data.synthesize(fs=22050)
        audio_mid = ipd.Audio(data=x_midi, rate=22050).src_attr()

        f = interp1d(wp_strict[:, 0], wp_strict[:, 1], fill_value='extrapolate')
        wp_display = []
        for cur_instrument in midi_data.instruments:
            for cur_note in cur_instrument.notes:
                wp_display.append([cur_note.start, f(cur_note.start)])
        wp_display = np.array(wp_display) * common.FEATURE_RATE
        wp_display = wp_display.tolist()

    else:
        audio_wav = ''
        audio_mid = ''
        audio_both = ''
        audio_mid = ''
        wp_display = []

    return render_template('refiner.html',
                           mtd_id=str(mtd_id),
                           audio_wav=audio_wav,
                           audio_mid=audio_mid,
                           audio_mid_align=audio_mid_align,
                           audio_both=audio_both,
                           img_src_mid=img_src_mid,
                           img_src_wav=img_src_wav,
                           scale_fac=scale_fac,
                           wp=wp_display,
                           feature_rate=common.FEATURE_RATE,
                           alignment_url=url_for('refiner.process_alignment', mtd_id=mtd_id),
                           save_url=url_for('refiner.save_alignment', mtd_id=mtd_id),
                           duration_url=change_duration_url,
                           linear_url=url_for('refiner.linearize_wp', mtd_id=mtd_id),
                           wcm_start_time=wcm_start_time, wcm_end_time=wcm_end_time, wcm_duration=wcm_duration,
                           wcm_id=wcm_id)


@refiner.route('/<mtd_id>/alignment', methods=['POST'])
def process_alignment(mtd_id):
    wp = ast.literal_eval(request.form['alignment'])

    wp = np.array(wp).astype(float) / common.FEATURE_RATE
    sort_idx = wp[:, 0].argsort()
    wp = wp[sort_idx, :]

    session['wp'] = wp.tolist()
    session['wp_mtd_id'] = mtd_id

    return redirect(url_for('refiner.index', mtd_id=mtd_id))


@refiner.route('/<mtd_id>/save', methods=['POST'])
def save_alignment(mtd_id):
    mtd_id_str = get_mtd_str(mtd_id)
    path_dict = get_paths()

    fn_wav = check_file_glob(os.path.join(path_dict['data_AUDIO'], f'{mtd_id_str}_*.wav'), mtd_id_str, 'wav')
    fn_mid = check_file_glob(os.path.join(path_dict['data_EDM-corr_MID'], f'{mtd_id_str}_*.mid'), mtd_id_str, 'mid')
    fn_wav_new = os.path.join(path_dict['data_AUDIO-annotated'], os.path.basename(fn_wav))

    old_csv_dir = path_dict['data_ALIGNMENT']
    new_csv_dir = path_dict['data_ALIGNMENT-annotated']

    fn_csv = check_file_glob(os.path.join(old_csv_dir, f'{mtd_id_str}_*.csv'), mtd_id_str, 'sync-csv')
    fn_out = os.path.join(new_csv_dir, os.path.basename(fn_csv))

    wp = ast.literal_eval(request.form['alignment'])

    wp = np.array(wp).astype(float) / common.FEATURE_RATE
    sort_idx = wp[:, 0].argsort()
    wp = wp[sort_idx, :]

    write_sync_csv(wp, fn_out, fn_mid, fn_wav_new if os.path.exists(fn_wav_new) else fn_wav)

    return redirect(url_for('refiner.index', mtd_id=mtd_id))


@refiner.route('/<mtd_id>/startend', methods=['POST'])
def change_duration(mtd_id):
    mtd_id_str = get_mtd_str(mtd_id)
    path_dict = get_paths()

    start_time_old, _, _ = get_start_end_time_duration(mtd_id)

    fn_mid = check_file_glob(os.path.join(path_dict['data_EDM-corr_MID'], f'{mtd_id_str}_*.mid'), mtd_id_str, 'mid')
    fn_npz_old = check_file_glob(os.path.join(path_dict['data_AUDIO_IIRT'], f'{mtd_id_str}_*.npz'), mtd_id_str, 'npz')
    fn_wav_old = check_file_glob(os.path.join(path_dict['data_AUDIO'], f'{mtd_id_str}_*.wav'), mtd_id_str, 'wav')
    fn_csv_old = check_file_glob(os.path.join(path_dict['data_ALIGNMENT'], f'{mtd_id_str}_*.csv'), mtd_id_str, 'sync-csv')

    fn_npz_new = os.path.join(path_dict['data_AUDIO_IIRT-annotated'], os.path.basename(fn_npz_old))
    fn_wav_new = os.path.join(path_dict['data_AUDIO-annotated'], os.path.basename(fn_wav_old))
    fn_json = os.path.join(path_dict['data_AUDIO_IIRT-annotated'], mtd_id_str + '.json')
    fn_csv_new = os.path.join(path_dict['data_ALIGNMENT-annotated'], os.path.basename(fn_csv_old))

    start_time = round(float(request.form['StartTime']), 1)
    end_time = round(float(request.form['EndTime']), 1)

    if not (start_time < end_time):
        flash('Start time (%.1f) must be smaller than end time (%.1f)!' % (start_time, end_time))
        return redirect(url_for('refiner.index', mtd_id=mtd_id))

    if not os.path.exists(current_app.config['data_AUDIO-WCM']):
        flash('data_AUDIO-WCM is not reachable: %s' % current_app.config['data_AUDIO-WCM'])
        return redirect(url_for('refiner.index', mtd_id=mtd_id))

    fn_wav = get_wcm_for_mtd(mtd_id)
    if not os.path.exists(fn_wav):
        flash('Could not find wav file: %s' % fn_wav)
        return redirect(url_for('refiner.index', mtd_id=mtd_id))

    x, sr = librosa.load(fn_wav, sr=22050, mono=True)
    x = x[int(round(start_time * sr)):int(round(end_time * sr))]

    with open(fn_json, 'w') as stream:
        json.dump({'start': start_time, 'end': end_time, 'mtd_id': mtd_id}, stream, indent=4)

    f_chroma, times = common.extract_iir_chroma(x, sr)
    np.savez_compressed(fn_npz_new, f_chroma=f_chroma, f_chroma_ax_time=times, f_chroma_ax_freq=np.arange(12))

    sf.write(fn_wav_new, x, sr)

    # need to adjust wapring path if start has changed!
    if 'wp' in session and session['wp_mtd_id'] == mtd_id:
        wp = np.array(session['wp'])
        session.pop('wp', None)
        session.pop('wp_mtd_id', None)
    else:
        if os.path.exists(fn_csv_new):
            fn_csv = fn_csv_new
        else:
            fn_csv = fn_csv_old
        wp = pd.read_csv(fn_csv, sep=';').values

    wp[:, 1] += (start_time_old - start_time)

    write_sync_csv(wp, fn_csv_new, fn_mid, fn_wav_new)

    return redirect(url_for('refiner.index', mtd_id=mtd_id))


@refiner.route('/<mtd_id>/removeannotations')
def remove_annotations(mtd_id):
    mtd_id_str = get_mtd_str(mtd_id)
    path_dict = get_paths()

    # files from original mtd data set
    fn_wav = check_file_glob(os.path.join(path_dict['data_AUDIO'], f'{mtd_id_str}_*.wav'), mtd_id_str, 'wav')
    fn_csv = check_file_glob(os.path.join(path_dict['data_ALIGNMENT'], f'{mtd_id_str}_*.csv'), mtd_id_str, 'sync-csv')

    # files computed for this interface
    fn_npz = check_file_glob(os.path.join(path_dict['data_AUDIO_IIRT'], f'{mtd_id_str}_*.npz'), mtd_id_str, 'npz')

    # files generated by the interface
    fn_csv_new = os.path.join(path_dict['data_ALIGNMENT-annotated'], os.path.basename(fn_csv))
    fn_npz_new = os.path.join(path_dict['data_AUDIO_IIRT-annotated'], os.path.basename(fn_npz))
    fn_wav_new = os.path.join(path_dict['data_AUDIO-annotated'], os.path.basename(fn_wav))
    fn_json = os.path.join(path_dict['data_AUDIO_IIRT-annotated'], mtd_id_str + '.json')

    if os.path.exists(fn_csv_new):
        os.remove(fn_csv_new)

    if os.path.exists(fn_npz_new):
        os.remove(fn_npz_new)

    if os.path.exists(fn_wav_new):
        os.remove(fn_wav_new)

    if os.path.exists(fn_json):
        os.remove(fn_json)

    return redirect(url_for('refiner.index', mtd_id=mtd_id))


@refiner.route('/<mtd_id>/linear')
def linearize_wp(mtd_id):
    mtd_id_str = get_mtd_str(mtd_id)
    path_dict = get_paths()

    fn_mid = check_file_glob(os.path.join(path_dict['data_EDM-corr_MID'], f'{mtd_id_str}_*.mid'), mtd_id_str, 'mid')
    fn_wav = check_file_glob(os.path.join(path_dict['data_AUDIO'], f'{mtd_id_str}_*.wav'), mtd_id_str, 'wav')
    fn_wav_new = os.path.join(path_dict['data_AUDIO-annotated'], os.path.basename(fn_wav))

    midi_data = pretty_midi.PrettyMIDI(fn_mid)
    max_midi = max(note.end for instrument in midi_data.instruments for note in instrument.notes)

    start_audio, end_audio, _ = get_start_end_time_duration(mtd_id)

    duration_audio = end_audio - start_audio
    duration_midi = max_midi

    fn_csv = check_file_glob(os.path.join(path_dict['data_ALIGNMENT'], f'{mtd_id_str}_*.csv'), mtd_id_str, 'sync-csv')
    fn_csv_new = os.path.join(path_dict['data_ALIGNMENT-annotated'], os.path.basename(fn_csv))

    if os.path.exists(fn_csv_new):
        fn_csv = fn_csv_new

    df_sync = pd.read_csv(fn_csv, sep=';')
    wp = df_sync.values
    num_wp_points = wp.shape[0]  # min(100, wp.shape[0])  # somewhat arbitrary

    wp0 = np.linspace(wp[0, 0], wp[-1, 0], num_wp_points)
    wp1 = wp0 * (duration_audio / duration_midi)
    wp_new = np.stack((wp0, wp1), axis=1)

    write_sync_csv(wp_new, fn_csv_new, fn_mid, fn_wav_new if os.path.exists(fn_wav_new) else fn_wav)

    return redirect(url_for('refiner.index', mtd_id=mtd_id))
