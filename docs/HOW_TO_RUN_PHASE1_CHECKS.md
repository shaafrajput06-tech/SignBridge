# How to run the Phase 1 checks on your Windows laptop [ME]

Two Phase 1 checks need a real computer with a camera, which my workspace does not have:

1. the **full test suite** (including the server tests and a test in a real browser), and
2. the **frame-rate benchmark**: how many camera frames per second your browser can track (both
   hands, body and face). The target is **24 frames per second or more**.

One file, `phase1_checks.bat`, does both. You only need to install two programs first, double-click
the file, sit in front of the camera for 30 seconds, and send me the results folder.

- **Time:** about 30-45 minutes the first time (mostly downloads), about 5 minutes after that.
- **Internet:** needed the first time, about 1 GB of downloads.
- **Disk space:** about 3 GB free.
- **Privacy:** the camera picture stays in the browser tab. Nothing is recorded, saved or uploaded.

---

## Step 1. Install Python 3.13

1. Open <https://www.python.org/downloads/windows/> and click the latest **Python 3.13** "Windows
   installer (64-bit)".
2. Open the downloaded file. On the first screen, **tick "Add python.exe to PATH"** at the bottom.
3. Click **Install Now** and wait until it says "Setup was successful". Click **Close**.
4. Check it worked: press the **Windows key**, type `cmd`, press **Enter**. In the black window type
   `py --version` and press **Enter**. You should see `Python 3.13.` followed by a number.

## Step 2. Install Node.js

1. Open <https://nodejs.org/> and download the **LTS** version for Windows (22.12 or newer).
2. Open the downloaded file and click **Next** through every screen, keeping the default choices.
   On the screen "Tools for Native Modules", leave the box **unticked**; it is not needed.
3. Check it worked: open a **new** `cmd` window (close the old one first) and type `node --version`.
   You should see `v22.` or a higher number. Then type `npm --version`; any number is fine.

## Step 3. Put the project somewhere simple

1. Unzip the SignBridge project I send you. Right-click the zip, choose **Extract All...**, and extract
   to `C:\SignBridge`. You should end up with `C:\SignBridge\SignBridge_Complete`.
2. Avoid the Desktop or Documents folders if OneDrive syncs them: syncing thousands of small files
   makes the installation very slow.

## Step 4. Get the laptop ready

- Plug in the charger (laptops slow down on battery).
- Close Zoom, Teams, the Camera app and anything else that might be using the camera.
- Close other heavy browser tabs and programs.

## Step 5. Run the checks

1. Open `C:\SignBridge\SignBridge_Complete` in File Explorer.
2. Double-click **`phase1_checks.bat`**.
   - If a blue box says **"Windows protected your PC"**, click **More info**, then **Run anyway**.
   - If **Windows Firewall** asks about Node.js, tick **Private networks** only and click **Allow**.
3. A black window opens and works through six steps. You do not need to type anything until step 6.

| You see | What is happening | Time (first run) |
|---|---|---|
| `[1/6] Python environment` | creates a private Python folder (`.venv`) and installs the Python packages | 5-10 min |
| `[2/6] Web packages and test browser` | installs the website's packages and a test browser | 5-15 min |
| `[3/6] MediaPipe pose and face models` | downloads the body and face tracking models | under 1 min |
| `[4/6] Machine details` | writes your processor, memory and graphics card names to a file | seconds |
| `[5/6] Test suites` | runs every automatic test, then prints `===== Test summary =====` | 3-10 min |
| `[6/6] Frame-rate benchmark` | starts the website in a second window and opens the benchmark page | 10 s |

**What a good test summary looks like** (step 5):

```
Python unit tests                PASSED
Licence ledger check             PASSED
Browser v1 parity tests (Node)   PASSED
Browser v2 tests (Node)          PASSED
Browser camera smoke test        PASSED
Flutter tests                    SKIPPED: the Flutter SDK is not installed ...
```

"Flutter tests SKIPPED" is expected. If any line says **FAILED**, carry on anyway: the full log is
saved and I will read it.

## Step 6. Run the frame-rate benchmark

Your browser opens `http://localhost:5173/bench.html`. If it says "This site can't be reached", wait 20
seconds and press **F5**: the website can take a little longer to start the first time.

1. When the browser asks to use the camera, click **Allow**.
2. Sit about an arm's length from the laptop so your **face, shoulders and both hands** are in the
   picture.
3. Leave the settings as they are (Seconds = 30, Face ticked) and click **Start benchmark**.
4. The page shows "Loading models..." and then "Measuring... 5 s, 27.3 fps" and so on. For 30 seconds,
   move both hands naturally in front of you, as if signing.
5. When a block of text appears, click **Copy result**.

## Step 7. Save the result

1. Open **Notepad** (Windows key, type `notepad`, Enter) and press **Ctrl+V** to paste.
2. Click **File > Save as**. Go to `C:\SignBridge\SignBridge_Complete\reports\phase1_checks`.
3. File name: `bench_result.json`. Save as type: **All files (\*.\*)**. Click **Save**.

## Step 8. Close everything

- Close the second black window called **"SignBridge Web (close when done)"**. That stops the website.
- In the first black window, press any key to close it.

## Step 9. Send the results to me

1. Open `C:\SignBridge\SignBridge_Complete\reports`.
2. Right-click the **`phase1_checks`** folder and choose **Compress to ZIP file** (Windows 11) or
   **Send to > Compressed (zipped) folder** (Windows 10).
3. Attach the zip in this chat.

The folder holds `tests_log.txt`, `machine.txt`, `pip_log.txt`, `npm_log.txt`, `models_log.txt` and
your `bench_result.json`. The logs show folder paths, which can include your Windows user name; open
them in Notepad first if you want to check.

---

## What the benchmark number means

- `fps` of **24 or more**: the Phase 1 target is met on your laptop.
- Below 24: try once more with the charger in and other programs closed, and send both results. A
  laptop camera that only delivers 30 frames per second caps the result at about 30.

## If something goes wrong

| Message | What to do |
|---|---|
| `Python 3.10 to 3.14 was not found` | Do Step 1 again and make sure `py --version` works in a new `cmd` window. |
| `Node.js with npm was not found` | Do Step 2, then close the black window and double-click the file again. |
| `Python package installation failed` | Check the internet connection and run the file again. If it fails again, send `reports\phase1_checks\pip_log.txt`. |
| `Web package installation failed` | Same, and send `npm_log.txt`. |
| `Model download failed` | Check the internet connection and run the file again; the benchmark cannot start without these models. Send `models_log.txt` if it keeps failing. |
| The benchmark page says `Benchmark failed: ...` | Another program is probably using the camera, or camera access was blocked. Close other camera apps; click the camera icon in the address bar and choose Allow; press F5. Send me the exact message if it continues. |
| The page never loads | Make sure the "SignBridge Web" window is still open and shows `Local: http://localhost:5173/`. Close any older "SignBridge Web" windows and run the file again. |

## What is still open after this

- The **F12 mirroring check** also needs real videos of signing. Under the fast track you are not asked
  to record them: I will try to run the same check in the Stage 3 notebook on licensed public PSL videos
  (flipping them to create the mirrored version). If the public videos cannot answer the question, I
  will say so in the Stage 3 report.
- **Flutter on a phone** is checked in Stage 6, when the app moves its tracking onto the phone.
