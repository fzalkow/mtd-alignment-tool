# MTD Alignment Website

The repository contains code for an alignment tool used when curating the Musical Theme Dataset (MTD). This web tool is
not a general-purpose product, but its source code may be useful for the MTD users who want to further refine the
alignments or add further themes to the dataset. The MTD is described in the following paper.

```
Frank Zalkow, Stefan Balke, Vlora Arifi-Müller, and Meinard Müller
MTD: A Multimodal Dataset of Musical Themes for MIR Research
Transactions of the International Society for Music Information Retrieval (TISMIR), 3(1): 180–192, 2020.
https://dx.doi.org/10.5334/tismir.68
```

The following website accompanies the paper and presents all links for accessing the MTD.

https://www.audiolabs-erlangen.de/resources/MIR/MTD


## Get Started

* Download the MTD.

* Modify `config.json` to contain valid paths. The `dir_mtd` entry is the path to the MTD. The `data_AUDIO-WCM`
  entry is the path to a directory containing the full audio recordings of the MTD. The latter entry is not necessary
  to run this website. (But it allows for changing the theme occurrence time positions.)

* Create the Python environment, prepare the features, and run the webpage.
```bash
conda env create -f environment.yml
conda activate mtd-alignment-tool

python 01_prepare_features.py

python manage.py run
```

## Results

Using the web interface, you can generate two different kinds of modifications to the MTD.

The first type of modification affects the alignments. After editing and saving the alignments using the web interface,
you find CSV files for each saved alignment in the following directory: `app/static/data_ALIGNMENT-annotated`.

The second type of modification concerns the metadata. In particular, you may change the start and end time positions of the theme
 occurrences.
Furhermore, you may edit transpositions by editing the file `app/static/transposition_corrected.json` or other metadata by editing the file `app/static/03_MTD-medium_new.csv`. To obtain these results, you have to execute the script:
```bash
python 02_use_updates.py
```
Then you find CSV files containing the new data in the directory `generated`.

## Acknowledgements

This work was supported by the German Research Foundation (DFG MU 2686/11-1, DFG MU 2686/12-1). The International
Audio Laboratories Erlangen are a joint institution of the Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU) and
Fraunhofer Institut für Integrierte Schaltungen IIS.
