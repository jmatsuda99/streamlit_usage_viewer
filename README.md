# 30分毎の使用実績 見える化（DB永続化）

GitHub + Streamlit で動くシンプルな可視化アプリです。CSV/Excel をアップロードすると、
**SQLite DB に縦持ちで保存** され、以後は再アップロード不要で可視化できます。

## 主要機能
- CSV/Excel のアップロード（Shift_JIS/UTF-8 自動判定）
- 横持ち（0:00〜23:30）を **縦持ち（ymd, hhmm, usage）** に自動変換
- SQLite に永続化（`usage_data.sqlite`）
- 登録済みデータから **開始日／終了日** を選んで **日毎の曲線を重ね描き**
- 日本語フォントがあれば自動適用（無い場合は英語フォールバック）

## 使い方（ローカル）
```bash
pip install -r requirements.txt
streamlit run app.py
```

## データの前提
- 日付列例：`YYYY/MM/DD`
- 時刻列：`0:00` 〜 `23:30` の 48 列

## GitHub + Streamlit Cloud
- リポジトリにこの一式を push → Streamlit Community Cloud で新規アプリを作成 → `app.py` を指定。