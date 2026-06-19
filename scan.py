#!/usr/bin/env python3
"""
量價 KD 股票篩選 — 參考 tw-stocks 專案的資料取得方式：
- TWSE MI_INDEX 取得上市股票清單、名稱、最新收盤行情、成交量
- yfinance 下載 6 個月日線，計算昨日量、昨日收盤、KD
- 產生 web/data.json 給前端 fetch 使用
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime


def fetch_twse_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))


def n(x):
    if x is None:
        return None
    s = str(x).replace(',', '').replace('--', '').strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def compute_kd(df, n_period=9):
    low_min = df['Low'].rolling(n_period).min()
    high_max = df['High'].rolling(n_period).max()
    rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
    k = rsv.ewm(alpha=1/3, adjust=False).mean()
    d = k.ewm(alpha=1/3, adjust=False).mean()
    return float(k.iloc[-1]), float(d.iloc[-1])


def main():
    import pandas as pd
    import yfinance as yf

    print('⏳ 從 TWSE 取得今日上市收盤行情...', file=sys.stderr)
    mkt = fetch_twse_json('https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?response=json&type=ALLBUT0999')
    trade_date = str(mkt.get('date') or datetime.now().strftime('%Y%m%d'))

    codes = []
    today_rows = {}
    for t in mkt.get('tables', []):
        if '每日收盤行情' not in t.get('title', ''):
            continue
        for r in t.get('data', []):
            code = str(r[0]).strip()
            if not (len(code) == 4 and code.isdigit()):
                continue
            name = str(r[1]).strip()
            volume = n(r[2])  # 成交股數
            close = n(r[8])   # 收盤價
            change = n(r[10]) # 漲跌價差
            if close is None or volume is None:
                continue
            prev_close = close - change if change is not None else None
            codes.append(code)
            today_rows[code] = {
                'symbol': code,
                'name': name,
                'price': close,
                'volume': int(volume),
                'prevClose_twse': prev_close,
            }
        break

    print(f'✅ TWSE {trade_date}: {len(codes)} 檔', file=sys.stderr)
    print('⏳ 從 yfinance 下載 6 個月日線並計算 KD...', file=sys.stderr)

    results = []
    chunk = 50
    for i in range(0, len(codes), chunk):
        part = codes[i:i+chunk]
        tickers = ' '.join(f'{c}.TW' for c in part)
        try:
            data = yf.download(tickers, period='6mo', interval='1d', progress=False, threads=True, auto_adjust=False)
        except Exception as e:
            print(f'⚠️ yfinance chunk failed {i}-{i+len(part)}: {e}', file=sys.stderr)
            continue
        for code in part:
            ticker = f'{code}.TW'
            try:
                if isinstance(data.columns, pd.MultiIndex):
                    df = data.xs(ticker, level=1, axis=1).dropna(subset=['Close', 'Volume'])
                else:
                    df = data.dropna(subset=['Close', 'Volume'])
                if len(df) < 12:
                    continue
                # yfinance 最後一列通常就是最新交易日；若 TWSE 已有更即時 close/volume，以 TWSE 為準。
                prev = df.iloc[-2]
                today = today_rows[code]
                prev_close = float(prev['Close'])
                prev_volume = int(prev['Volume'])
                k, d = compute_kd(df)
                rise_pct = (today['price'] / prev_close - 1) * 100 if prev_close else 0
                vol_ratio = today['volume'] / prev_volume if prev_volume else 0
                hit = vol_ratio >= 2 and rise_pct >= 3 and k < 40 and d < 40
                if hit:
                    results.append({
                        'symbol': code,
                        'name': today['name'],
                        'prevClose': round(prev_close, 2),
                        'price': round(today['price'], 2),
                        'prevVolume': prev_volume,
                        'volume': today['volume'],
                        'k': round(k, 2),
                        'd': round(d, 2),
                        'risePct': round(rise_pct, 2),
                        'volRatio': round(vol_ratio, 2),
                    })
            except Exception:
                continue
        print(f'  ... {min(i+chunk, len(codes))}/{len(codes)}', file=sys.stderr)
        time.sleep(0.2)

    results.sort(key=lambda r: (r['volRatio'], r['risePct']), reverse=True)
    out = {
        'date': trade_date,
        'updated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'source': 'TWSE MI_INDEX + yfinance daily OHLCV, same style as ai-tools-sharing-talk/tw-stocks daily_scan.py',
        'rules': '今日成交量 >= 昨日成交量×2 + 今日價格較昨日收盤 >= 3% + K<40 + D<40',
        'stocks': results,
    }
    web_dir = os.path.abspath(os.path.dirname(__file__))
    os.makedirs(web_dir, exist_ok=True)
    path = os.path.join(web_dir, 'data.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'✅ wrote {path}, hits={len(results)}')


if __name__ == '__main__':
    main()
