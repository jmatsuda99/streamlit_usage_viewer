# 30分毎の使用実績 見える化（DB永続化）［軽量デプロイ版］

このバージョンは **requirements のピン止め解除** と **SQLiteファイルの同梱なし** により、
Streamlit Community Cloud での初回デプロイ時間を短縮します。DBは初回起動時に自動生成されます。

## 使い方（ローカル）
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 使い方（Streamlit Community Cloud）
1. このZIPの中身（`app.py`, `requirements.txt`, `README.md`）をGitHubにpush
2. StreamlitでNew app → 対象Repo → `app.py` を指定
3. 初回起動時に `usage_data.sqlite` が自動生成されます

## 機能
- CSV/Excelアップロード（Shift_JIS/UTF-8 自動判定）
- 横持ち（0:00〜23:30）→ 縦持ち（ymd, hhmm, usage）
- SQLite永続化（登録後は再アップ不要）
- 指定範囲の日毎曲線を重ね描き