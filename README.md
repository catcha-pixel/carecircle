# CareCircle

**Check a message or a pill before you act.**

CareCircle helps older adults spot scams and understand their medicines. Take a photo or screenshot of a suspicious message and get a clear answer: *Likely a scam*, *Be careful*, or *Looks safe*, with the reasons and what to do. Read a pill bottle, identify a loose pill, and check your medicines for warnings in their official FDA labels. Built for the Congressional App Challenge.

## Features

**Check a message**
- **Choose a screenshot** of a text, or **take a photo** of a letter or screen. Words are read on the phone with Tesseract.js, so photos never leave the device.
- Photos are cleaned up before reading: resized, straightened if tilted, contrast boosted, dark-mode screenshots flipped, and sideways phone photos turned upright.
- **Paste a message** works too.
- Results show how sure the app is, up to 3 plain-language reasons, and what to do. If a photo was hard to read, you can fix the words and check again.

**Pill Check**
- **Read a pill bottle:** photograph the pharmacy label and the app finds the medicine name, strength, and directions. It handles common photo-reading mistakes like `METF0RMIN`.
- **Identify a loose pill:** type the letters and numbers stamped on it (or try reading them from a photo), pick the color and shape, and see possible matches.
- **My medicines:** a list saved only on the phone. **Check for warnings** fetches each medicine's official FDA label and shows the label's own words wherever it mentions another medicine on the list, or its drug group (for example, "NSAIDs" covers ibuprofen).

**Everywhere:** large text and buttons, Read aloud, Share, and it installs to the home screen.

## How it works

```
Phone (web app)                              Server (Python, FastAPI)
------------------------------               -------------------------------------
Photo -> cleaned up -> Tesseract.js          POST /check-message   ML model + red-flag rules
         reads the words ON the phone        POST /meds/read-label find medicine names in text
                         -- words only -->   POST /pills/identify  search the pill database
                                             POST /meds/interactions  FDA labels via openFDA
                                             GET  /meds/suggest    name suggestions while typing
```

### Scam Check
A machine learning model (TF-IDF + logistic regression, scikit-learn) trained on 5,574 public text messages plus modern U.S. scam examples, combined with 13 red-flag rules (gift cards, "don't tell mom," fake links, threats, urgency...).

| Approach (30 modern messages the model never saw) | Accuracy |
|---|---|
| Model alone | 77% |
| Model + red-flag rules | 97%, 0 scams missed |

> These test messages were also used to improve the rules, so 97% is optimistic. A fresh set of real messages is the next test.

### Pill Check
- **Pill identification** uses the National Library of Medicine's **Pillbox** data. Pillbox was retired in January 2021, so newer pills are missing; the app says so.
- **Medicine names** come from a list of common medicines (`server/data/common_drugs.txt`), brand names (`brand_names.csv`), and the pill database.
- **Warnings** come from official FDA drug labels through [openFDA](https://open.fda.gov/apis/drug/label/). The app quotes the label instead of making its own medical judgment, and always says to ask a pharmacist.

## Run it on your computer

You need Python 3.10 or newer.

```bash
cd server
python -m venv .venv
.venv\Scripts\activate             # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt

cd scam_check
uvicorn api:app --reload --host 0.0.0.0
```

Open **http://127.0.0.1:8000** for the app, or **/docs** to try the API.

### The pill database

`server/data/pill_index.json.gz` holds 32,073 pills built from NLM's Pillbox data, and it's already included. To rebuild it from a fresh download:

1. Download the Pillbox CSV: <https://datadiscovery.nlm.nih.gov/api/v3/views/crzr-uvwg/export.csv?accessType=DOWNLOAD>
2. From the `server` folder, run `python -m meds.build_pill_index path/to/export.csv`

Visit `/health` to check: it shows `"pill_database": true` and the number of pills.

### Optional: openFDA API key
Without a key, openFDA allows 1,000 requests per day. For more, get a free key at open.fda.gov and set the environment variable `OPENFDA_API_KEY` (on Render: **Environment → Add Environment Variable**).

## Tests

```bash
cd server
pip install -r requirements-dev.txt
python -m pytest tests          # 37 tests: scam check, pill search, label reading, warnings, API
cd scam_check
python evaluate.py ../data/holdout_test.csv   # scam accuracy on unseen messages
```

The browser was also tested end to end with realistic screenshots and phone photos (tilted, blurry, sideways, dark mode, a pill bottle label, a pill).

## Project layout

```
app/                      Web app (HTML, CSS, JavaScript). No build step.
  index.html              All screens
  styles.css              Design system: card, button, tag, chip
  js/ocr.js               Photo clean-up + reading text on the phone
  js/app.js               Screens, server calls, saving, read aloud, share
  js/scam.js              Check a message
  js/pills.js             Pill Check and My medicines
  vendor/tesseract/       Bundled text reader (so it works without loading code from other sites)
  service-worker.js       Install + offline screens
server/
  scam_check/             API (api.py), scam checker, red-flag rules, training
  meds/                   Pill search, label reading, FDA label warnings, pill database builder
  data/                   Training data, medicine names, drug groups
  tests/                  Automated tests (sample pill data in tests/fixtures is made up, for tests only)
docs/                     Research notes and wireframes
```

## Deploying on Render

Same settings as before:

| Setting | Value |
|---|---|
| Build Command | `pip install -r server/requirements.txt` |
| Start Command | `cd server/scam_check && uvicorn api:app --host 0.0.0.0 --port $PORT` |

## Privacy

- Photos are read on the phone. Only the words are sent to the server.
- Messages are checked in memory and never stored.
- Your medicine list and last result are saved only on your phone.
- Medicine names are sent to openFDA only to look up their public labels.

## Credits

- **SMS Spam Collection** by Tiago A. Almeida and José María Gómez Hidalgo, [UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/228/sms+spam+collection), CC BY 4.0.
- **Pillbox** by the U.S. National Library of Medicine (retired 2021), ODbL.
- **openFDA** drug label data from the U.S. Food and Drug Administration.
- **Tesseract.js** (Apache 2.0) and English language data from tessdata.
- Fonts: Atkinson Hyperlegible and Bricolage Grotesque (SIL Open Font License).

## Disclaimer

CareCircle can make mistakes. It is not medical or financial advice and doesn't replace your pharmacist, doctor, or bank. Never stop or change a medicine on your own. When in doubt about a message, call the company or person using a number you already trust.
