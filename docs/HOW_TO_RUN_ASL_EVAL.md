# How to measure ASL mode's accuracy on Kaggle [ME]

This runs `notebooks/asl_mode_eval.ipynb` on Kaggle's free computers. It **trains nothing**: it runs
the ready-made ASL model on the competition's hidden test signers and writes down how often it is
right. You click a few buttons, wait, and send me one file.

- **Time:** about 10 minutes of clicking, then 30-90 minutes of waiting (you can close the browser).
- **Cost:** free.
- **You need:** a Kaggle account with a verified phone number (Kaggle asks for this before a notebook
  may use the internet).

---

## Step 1. Make a Kaggle account (skip if you have one)

1. Go to <https://www.kaggle.com> and click **Register**. Sign up with Google or an email address.
2. Click your profile picture (top right), then **Settings**.
3. Find **Phone verification**, enter your phone number and type in the code Kaggle texts you.

## Step 2. Open the notebook on Kaggle

1. Click **+ Create** (top left), then **New Notebook**.
2. In the notebook, click **File > Import Notebook**.
3. Click **Browse Files**, open `Downloads\SignBridge_Complete\notebooks` and choose
   **`asl_mode_eval.ipynb`**. Click **Import**. You should see cells that start with
   "SignBridge ASL mode: accuracy on signers the model never saw".

## Step 3. Add the test data

1. In the right-hand panel, find **Input** and click **+ Add Input**.
2. In the search box type **ASL Isolated Sign Recognition Rerun Set**.
3. Click the result by *sohier* (about 14 GB, licence CC0) and click the **+** button next to it.
   It appears under Input after a few seconds.
4. Optional but useful: search **Google - Isolated Sign Language Recognition**, open it, accept the
   competition rules if Kaggle asks, and add it as well. The notebook then checks that none of the
   test signers were used to train the model.

## Step 4. Let the notebook download the model

1. In the right-hand panel, open **Settings** (it may be under a "⋮" or "Session options" menu).
2. Switch **Internet** to **On**.

No internet option? Then add the model as a file instead: after `start_signbridge.bat` has run
once, your project has `models\asl\model.tflite`. In **+ Add Input** choose **Upload**, then
**New Dataset**, drop in `model.tflite` and `sign_to_prediction_index_map.json` from
`Downloads\SignBridge_Complete\models\asl`, name it `signbridge-asl-model`, keep it private and
click **Create**. The notebook finds it and checks it is the same file (by its SHA-256).

## Step 5. Run it in the background

1. Click **Save Version** (top right).
2. Choose **Save & Run All (Commit)** and click **Save**.
3. Kaggle now runs every cell on its own computer. You can close the tab. It sends you a
   notification when the run finishes, usually in 30-90 minutes.

(You can press **Run All** instead to watch it, but then the run stops if the tab sits idle too long.)

## Step 6. Download the result and send it to me

1. Open the notebook again (Kaggle: **Code > Your Work**) and click the finished version.
2. Open the **Output** tab and download **`asl_eval_results.json`**.
3. Attach that file in this chat. It holds only numbers: accuracy, timings and settings. It holds no
   video and no personal data.

## What the notebook prints (so you know it is working)

| Cell | You should see |
|---|---|
| Model | `Using the attached model.tflite ...` or `Downloading model.tflite ...`, then `Model ready: ...  input [-1 543 3]` |
| Data | `Samples: ... signs: 250 signers: ...` |
| Layout | `Row order checked on 5 files: face, left_hand, pose, right_hand` |
| Run | a line every 1,000 samples, such as `3000/... samples, 412 s, top-1 so far 0.8...` |
| Results | a block of numbers, then `Saved /kaggle/working/asl_eval_results.json` |

## If something goes wrong

| Message | What to do |
|---|---|
| `No CSV with 'path' and 'sign' columns was found` | The rerun dataset is not attached: do Step 3 again. |
| `needs Internet switched on` or a download error | Do Step 4: switch Internet on, or upload the model as a dataset. |
| `is not the pinned file` | The model is a different file. Use the files from your SignBridge folder or the Hugging Face link. Do not change the hash in the notebook. |
| The run takes too long | In the first code cell change `MAX_SAMPLES = None` to `MAX_SAMPLES = 5000`, then save a new version. The report will say it used a subset. |
| Anything else | Send me a screenshot of the red error text. |
