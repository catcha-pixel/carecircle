# CareCircle

**Point your phone at anything you're unsure about (a text, a letter, a pill) and get a clear, calm answer.**

CareCircle helps older adults spot scams before they click, pay, or reply. It explains *why* something looks risky, in plain words, and tells you what to do next. Built for the Congressional App Challenge.

## What works today

- **Check This:** take a photo of a message. The words are read **on the phone** (the photo never leaves it), then checked for scam warning signs.
- **Paste a message:** paste any text, email, or message to check it.
- **Clear results:** "Likely a scam," "Be careful," or "Looks safe," with how sure we are, the reasons, and what to do.
- **Read aloud:** hear the result.
- **Tell family:** send the result to someone you trust using the phone's share menu.
- **Installs like an app:** add it to your home screen.

Coming next: letter and bill explainer, Pill Check, and Family Circle alerts.

## How it works

```
Phone (web app)                          Server (Python)
---------------------------              ---------------------------------
Photo -> Tesseract.js reads the words    POST /check-message
         (on the phone)          -- text -->  machine learning model
                                              + 13 red-flag rules
Result screen  <-- verdict, reasons, advice --
```

The scam checker combines two things:

1. **A machine learning model** (TF-IDF + logistic regression, scikit-learn) trained on 5,574 public text messages plus modern U.S. scam examples.
2. **Red-flag rules** for the patterns scammers rely on: gift cards, "don't tell mom," fake links, threats, urgency, and more. Each rule has a plain-language explanation.

| Approach (30 modern messages the model never saw) | Accuracy |
|---|---|
| Model alone | 77% |
| Model + red-flag rules | 97%, 0 scams missed |

> These test messages were also used to improve the rules, so the 97% is optimistic. A fresh set of real messages is the next test.

## Run it on your computer

You need Python 3.10 or newer.

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cd scam_check
uvicorn api:app --reload --host 0.0.0.0
```

Open **http://127.0.0.1:8000** for the app, or **http://127.0.0.1:8000/docs** to try the API directly.

**To try it on your phone:** connect your phone to the same Wi-Fi, find your computer's local IP address (for example `192.168.1.20`), and open `http://192.168.1.20:8000` on the phone. Checking pasted text works this way. For the camera and "install as an app," browsers require a secure (`https://`) address. Deploying the server (for example to Render or Fly.io) gives you one.

### Other commands (from `server/scam_check`)

```bash
python3 test_api.py                         # API tests
python3 evaluate.py ../data/holdout_test.csv # accuracy on unseen messages
python3 train.py ../data ../models/scam_model.joblib  # retrain the model
```

## Project layout

```
app/                  Web app (HTML, CSS, JavaScript). No build step.
  index.html          All screens
  styles.css          Design system: card, button, tag
  app.js              Screen flow, photo reading, results, read aloud
  service-worker.js   Lets it install and open offline
server/
  scam_check/         API, checker, red-flag rules, training and tests
  data/               Training and test messages
  models/             Trained model
docs/                 Research notes and wireframes
```

## Privacy

- Photos are read on the phone. Only the words are sent to the checker.
- Messages are checked in memory and never stored.
- The last result is saved only on your own phone.

## Built with

- [FastAPI](https://fastapi.tiangolo.com/) and [scikit-learn](https://scikit-learn.org/) (Python)
- [Tesseract.js](https://tesseract.projectnaptha.com/) for reading text from photos (Apache 2.0)
- Fonts: [Atkinson Hyperlegible](https://fonts.google.com/specimen/Atkinson+Hyperlegible), designed for low-vision readers, and [Bricolage Grotesque](https://fonts.google.com/specimen/Bricolage+Grotesque) (SIL Open Font License)

## Credits

- **SMS Spam Collection** by Tiago A. Almeida and José María Gómez Hidalgo, from the [UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/228/sms+spam+collection), licensed CC BY 4.0.
- Modern scam examples were written for this project, based on public FTC and FBI scam warnings.

## Disclaimer

CareCircle can make mistakes. It is not a replacement for your bank, your pharmacist, or your own judgment. When in doubt, call the company or person using a number you already trust.
