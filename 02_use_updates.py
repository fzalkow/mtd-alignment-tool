import os
import json
import glob
from itertools import chain

import pandas as pd
from tqdm import tqdm
from app.common import STATIC_DIR


def format_time(ss):
    ss_check = ss
    mm = ss // 60
    ss = ss - (mm * 60)
    assert ss_check == (ss + mm * 60)
    if int(ss) == ss:
        return '%02d:%02d' % (mm, ss)
    else:
        return '%02d:%04.1f' % (mm, ss)


if __name__ == '__main__':
    with open('config.json', 'r') as stream:
        config = json.load(stream)

    fn_new_df_rows = os.path.join(STATIC_DIR, '03_MTD-medium_new.csv')
    fn_new_transpositions = os.path.join(STATIC_DIR, 'transposition_corrected.json')
    dir_start_end_json = os.path.join(STATIC_DIR, 'data_AUDIO_IIRT-annotated')

    fn_mini = os.path.join(config['dir_mtd'], '01_MTD-mini.csv')
    fn_small = os.path.join(config['dir_mtd'], '02_MTD-small.csv')
    fn_medium = os.path.join(config['dir_mtd'], '03_MTD-medium.csv')

    fn_mini_new = os.path.join('generated', '01_MTD-mini.csv')
    fn_small_new = os.path.join('generated', '02_MTD-small.csv')
    fn_medium_new = os.path.join('generated', '03_MTD-medium.csv')

    # collect update data
    updates1 = {}
    new_df_rows = pd.read_csv(fn_new_df_rows, sep=';', dtype=object, keep_default_na=False)
    for i, row in tqdm(new_df_rows.iterrows(), total=len(new_df_rows.index)):
        row_dict = row.to_dict()
        cur_mtd_id = row_dict['MTDID']
        assert cur_mtd_id not in updates1.keys()
        updates1[cur_mtd_id] = row_dict
        del updates1[cur_mtd_id]['MTDID']

    updates2 = {}
    with open(fn_new_transpositions, 'r') as stream:
        for cur_mtd_id, val in tqdm(json.load(stream).items()):
            assert cur_mtd_id not in updates2.keys()
            updates2[cur_mtd_id] = {'MidiTransposition': val}

    updates3 = {}
    for fn_json in tqdm(glob.glob(os.path.join(dir_start_end_json, '*.json'))):
        with open(fn_json, 'r') as stream:
            cur_dict = json.load(stream)
        cur_mtd_id = cur_dict['mtd_id']
        cur_start = format_time(cur_dict['start'])
        cur_end = format_time(cur_dict['end'])
        assert cur_end > cur_start
        assert cur_mtd_id not in updates3.keys()
        updates3[cur_mtd_id] = {'StartTime': cur_start, 'EndTime': cur_end}

    # check consistency
    all_updates = (updates1, updates2, updates3)
    joined_updates = {}
    all_updated_mtd_ids = set(chain(*[list(u.keys()) for u in all_updates]))
    break_later = False

    for cur_mtd_id in tqdm(all_updated_mtd_ids):
        matching_updates = [u[cur_mtd_id] for u in all_updates if cur_mtd_id in u]
        joined_updates[cur_mtd_id] = {}
        for key in set(chain(*[list(u.keys()) for u in matching_updates])):
            values_for_key = set([u[key] for u in matching_updates if key in u])

            # for start/end, updates3 has the best information
            if key == 'StartTime' and cur_mtd_id in updates3 and key in updates3[cur_mtd_id]:
                joined_updates[cur_mtd_id][key] = updates3[cur_mtd_id][key]
            elif key == 'EndTime' and cur_mtd_id in updates3 and key in updates3[cur_mtd_id]:
                joined_updates[cur_mtd_id][key] = updates3[cur_mtd_id][key]
            # don't continue when having different information
            elif len(values_for_key) != 1:
                tqdm.write(f'Different update values! MTD-ID: {cur_mtd_id}. Key: {key}, Values: {values_for_key}.')
                break_later = True
            # update joined updates dict
            else:
                joined_updates[cur_mtd_id][key] = next(iter(values_for_key))

    if break_later:
        exit()

    # print(json.dumps(joined_updates, indent=2))
    df_mini = pd.read_csv(fn_mini, sep=';', dtype=object, keep_default_na=False)
    df_small = pd.read_csv(fn_small, sep=';', dtype=object, keep_default_na=False)
    df_medium = pd.read_csv(fn_medium, sep=';', dtype=object, keep_default_na=False)

    # update csv
    for cur_mtd_id, updates in tqdm(joined_updates.items()):

        mask = df_mini['MTDID'] == cur_mtd_id
        row = df_mini[mask]
        assert len(row) in [0, 1], cur_mtd_id
        if len(row) == 1:
            for key, val in updates.items():
                df_mini.loc[mask, key] = val

        mask = df_small['MTDID'] == cur_mtd_id
        row = df_small[mask]
        assert len(row) in [0, 1], cur_mtd_id
        if len(row) == 1:
            for key, val in updates.items():
                df_small.loc[mask, key] = val

        mask = df_medium['MTDID'] == cur_mtd_id
        row = df_medium[mask]
        assert len(row) == 1, cur_mtd_id  # needs to be there
        for key, val in updates.items():
            df_medium.loc[mask, key] = val

    df_mini.to_csv(fn_mini_new, sep=';', index=False)
    df_small.to_csv(fn_small_new, sep=';', index=False)
    df_medium.to_csv(fn_medium_new, sep=';', index=False)
