# Wheat-head count review · Open competition

Build a tool that helps a crop researcher **check and correct automated wheat-head counts**. Show the field image, predicted count, and prediction interval side by side. Let the reviewer record a manual count and export it alongside the original prediction and image ID so someone else can audit the correction.

## What you get

The starter uses the **Global Wheat Head Dataset**, with **3,655 training images, 1,476 validation images, and 1,381 held-out cases**. It includes **94 image previews** and cached features for the full split, so you can run the counting baseline on a CPU. A separate script retrieves additional images.

The Python starter produces counts and prediction intervals, exports a review queue as CSV and JSON, and can import manual corrections. It also includes a format checker, saved example output, and a smaller fallback. [Data dictionary](07-wheat/DATA-DICTIONARY.md) · [Source and license notes](07-wheat/NOTICE.md)

## Get started

Clone or download the resource repo. Run these commands from the repo root. The full setup was tested with Python 3.14.6 on Apple silicon.

```sh
cd challenges/wheat-head-count-review
export OPENBLAS_NUM_THREADS=2
export OMP_NUM_THREADS=2
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -I starter.py --route 07-wheat --model domain --output submission.json
.venv/bin/python -I check_submission.py --route 07-wheat --submission submission.json
.venv/bin/python -I workflow.py --route 07-wheat --submission submission.json --output review
```

Open `review/review.csv` and choose a row with a bundled image. The `image` column gives its path under `07-wheat/`. One held-out image group had **87.8% interval coverage against a 90% target**. Use the validation set if you compare methods, and keep your claims tied to visible wheat heads. Estimating crop yield requires separate evidence.

## Record a manual count

Create `corrections.csv` with the header `id,correction`. Add the ID of a case whose image you inspected and the count you observed. Run this command from the challenge folder.

```sh
.venv/bin/python -I workflow.py --route 07-wheat --submission submission.json --corrections corrections.csv --output corrected-review
```

Open `corrected-review/review.csv` to see both counts. The export records the image hash with your correction.

For a case without a bundled image, install `requirements-images.lock` in the same environment and run `retrieve_wheat_image.py --id CASE_ID --output downloaded-images/CASE_ID.jpg` with that Python. Replace `CASE_ID` with the actual case ID. Image retrieval requires internet access and downloads the pinned source archive in memory. To import a correction for that image, add `--image-directory downloaded-images` to the correction command.

## Run a small example

If setup fails or you want a quick preview, run the fallback from the challenge folder with Python’s standard library.

```sh
python3 -I starter.py --route 07-wheat --model fallback --fixture --output fallback.json
python3 -I check_submission.py --route 07-wheat --fixture --submission fallback.json
```

To inspect the saved full baseline output, unpack it from the same folder.

```sh
python3 -c "import gzip,pathlib; pathlib.Path('reference-example.json').write_bytes(gzip.decompress(pathlib.Path('07-wheat/example-submission.json.gz').read_bytes()))"
```

## Submit and demo

Submit your team’s private GitHub repository URL through the team form by **5 PM Pacific**. In your README, explain what you built, how to run it, and what you tested. [Submission steps](../../README.md#set-up-your-project) · [Project README template](../../PROJECT-README-TEMPLATE.md)

At your table demo, open one image, explain why you’d review it, record a manual count, and show both counts in the export. Three judges independently give **1–5 whole stars** for originality and value, evidence and feasibility, and clarity of presentation. [Hackathon judging guide](../../README.md#prepare-your-demo)
