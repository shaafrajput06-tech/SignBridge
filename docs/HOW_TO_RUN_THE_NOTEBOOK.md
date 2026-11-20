# How to run the PSL training notebook (only if GitHub cannot)

You normally never do this: GitHub trains the PSL model by itself (Actions → *PSL model (Stage 2)*).
Use this only if Claude asks you to, for example when GitHub's free computers are too slow.

1. Open https://colab.research.google.com and sign in with any Google account.
2. Click **File → Open notebook → GitHub**, paste `shaafrajput06-tech/SignBridge`, choose the branch
   `v3/master`, and click `notebooks/train_psl_v3.ipynb`.
3. Click **Runtime → Run all**. If Colab asks "Run anyway?", click **Run anyway** (the notebook is from
   this project).
4. Wait. Each cell shows the expected result in its first comment line. The whole run takes about
   30-60 minutes. Keep the tab open.
5. When cell 6 prints `psl-bundle.zip ready`, open the **Files** panel on the left (folder icon), click
   the three dots next to `psl-bundle.zip` and choose **Download**.
6. Send `psl-bundle.zip` to Claude (attach it in the chat). Claude checks it and adds it to SignBridge.

Nothing is uploaded anywhere by the notebook; it only downloads the licensed SignSpeak dataset.
