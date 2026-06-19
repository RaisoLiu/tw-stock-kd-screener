# 台股量價 KD 篩選器

篩選條件：

- 今日成交量 >= 昨日成交量 × 2
- 今日價格較昨日收盤上漲 >= 3%
- K < 40 且 D < 40

資料取得方式參考 `ai-tools-sharing-talk/tw-stocks`：

- TWSE `MI_INDEX` 取得上市股票清單、名稱、當日收盤行情與成交量
- `yfinance` 下載日線 OHLCV
- `scan.py` 計算昨日量、昨日收盤、KD，輸出 `data.json`
- `index.html` 用 `fetch('data.json')` 顯示結果

## 本機更新

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scan.py
python -m http.server 8787
```

## 自動更新

GitHub Actions 每天台北時間 04:00 執行 `scan.py`，若 `data.json` 有變更會自動 commit 回 `main`。
