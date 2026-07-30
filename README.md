# ربات سیگنال‌یاب هوشمند کریپتو (Binance + Bybit)

فقط سیگنال می‌فرسته تو تلگرام، هیچ معامله‌ای خودش انجام نمی‌ده.
کاملاً روی سرویس‌های رایگان (Render + Supabase) قابل اجراست.

## معماری (طبق طرح خودت پیاده شده)
Trend Engine → MTF Alignment → Smart Money (Liquidity Sweep / BOS / CHOCH / Order Block / FVG)
→ Volume Engine → Momentum Engine → Market Regime → AI Scoring (وزنی، ۰ تا ۱۰۰)
→ Risk/Exit Levels → News Filter → ارسال تلگرام → دکمه Win/Loss → یادگیری ساده

## ساختار فایل‌ها
```
config.py            تنظیمات مرکزی (از .env خوانده می‌شود)
database.py          لایه‌ی Postgres/Supabase
exchange_client.py   اتصال به Binance/Bybit با ccxt
indicators.py        EMA/RSI/MACD/ATR/VWAP و ...
trend_engine.py       تشخیص روند + ساختار سوئینگ
smart_money.py         Liquidity Sweep / BOS-CHOCH / Order Block / FVG
volume_engine.py        تحلیل حجم و Order Book Imbalance
momentum_engine.py       RSI/MACD/ATR Expansion
regime.py                 تشخیص رژیم بازار
mtf_engine.py               همسویی چند تایم‌فریم
scoring_engine.py            امتیازدهی وزنی نهایی
risk_manager.py               محاسبه SL/TP و توقف در صورت ضرر زیاد
news_filter.py                 فیلتر اخبار مهم
telegram_notifier.py            ارسال پیام + دستورات ربات
learning.py                      ثبت آمار برد/باخت هر شرط
pipeline.py                       اتصال همه‌ی مراحل به هم
scheduler.py                       اسکن دوره‌ای بازار
main.py                             نقطه اجرا
```

---

## مرحله ۱: ساخت دیتابیس Supabase (رایگان)

1. برو به [supabase.com](https://supabase.com) و یک پروژه جدید بساز (رایگان).
2. توی Project Settings → Database → Connection String، حالت **Session Pooler** رو انتخاب کن
   (چون Render IPv6 نداره و پولر برای این حالته).
3. رشته‌ی اتصال شبیه این می‌شه:
   ```
   postgresql://postgres.xxxxx:PASSWORD@aws-0-region.pooler.supabase.com:5432/postgres
   ```
4. این رو بذار توی `DATABASE_URL`.

جدول‌ها خودکار ساخته می‌شن (تابع `database.init_db()` موقع استارت اجرا می‌شه)، نیازی به SQL دستی نیست.

## مرحله ۲: ساخت ربات تلگرام

1. توی تلگرام برو پیش [@BotFather](https://t.me/BotFather) → `/newbot` → یک اسم و یوزرنیم بده.
2. توکن رو بذار توی `TELEGRAM_BOT_TOKEN`.
3. آیدی عددی خودت رو از [@userinfobot](https://t.me/userinfobot) بگیر و بذار توی
   `TELEGRAM_CHAT_ID` و `TELEGRAM_ADMIN_IDS`.

## مرحله ۳: تنظیم فایل .env

فایل `.env.example` رو کپی کن به `.env` و مقادیرش رو پر کن:
```bash
cp .env.example .env
```
برای Binance/Bybit نیازی به کلید API نیست چون ربات فقط دیتای عمومی (قیمت، حجم، اردربوک) می‌خونه.
اگر بعداً خواستی Funding Rate/Open Interest دقیق‌تر از حساب شخصی بخونی، می‌تونی کلید بدی (فقط با دسترسی Read).

## مرحله ۴: اجرای لوکال (تست قبل از دیپلوی)

```bash
python -m venv venv
source venv/bin/activate      # ویندوز: venv\Scripts\activate
pip install -r requirements.txt
```
برای تست لوکال، `WEBHOOK_URL` رو توی `.env` خالی بذار — ربات خودکار می‌ره روی حالت Polling:
```bash
python main.py
```
اگه پیام "✅ ربات سیگنال‌یاب روشن شد" رو توی تلگرام دیدی، یعنی وصله.

## مرحله ۵: دیپلوی روی Render (رایگان)

1. پروژه رو پوش کن به یک ریپازیتوری GitHub.
2. توی [render.com](https://render.com) → New → Web Service → ریپازیتوری رو انتخاب کن.
3. تنظیمات:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`
   - **Plan:** Free
4. همه‌ی متغیرهای `.env` رو توی Render → Environment اضافه کن.
5. `WEBHOOK_URL` رو برابر آدرس سرویس Render بذار، مثلاً:
   `https://trading-signal-bot.onrender.com`
6. Deploy بزن. بعد از بالا اومدن، ربات خودش webhook تلگرام رو ست می‌کنه.

⚠️ **نکته Render Free:** سرویس رایگان بعد از ۱۵ دقیقه بی‌فعالیتی HTTP می‌خوابه.
چون تلگرام هر آپدیت رو با یک POST به webhook می‌فرسته، اولین پیام بعد از خواب کمی کند میاد ولی بیدار می‌شه.
اگه خواستی همیشه بیدار بمونه، یک [Cron-job.org](https://cron-job.org) رایگان بساز که هر ۱۰ دقیقه
آدرس `https://your-app.onrender.com/webhook` رو GET بزنه (فقط برای بیدار نگه داشتن، پاسخ مهم نیست).

## دستورات ربات در تلگرام

| دستور | کاربرد |
|---|---|
| `/start` | معرفی و راهنما |
| `/stats` | آمار وین‌ریت هر شرط (trend, order_block, fvg, ...) |
| `/addnews CPI \| 1404-05-10 14:30` | ثبت خبر مهم (تاریخ شمسی، ساعت تهران) برای فیلتر خبری |
| `/news` | نمایش اخبار ثبت‌شده‌ی پیش‌رو |
| `/pause` | توقف موقت ارسال سیگنال |
| `/resume` | ازسرگیری سیگنال |

هر سیگنال دو دکمه‌ی **✅ برد** و **❌ ضرر** داره — بعد از بسته شدن معامله بزن تا ربات
آمار وین‌ریت هر شرط (Order Block، FVG، Liquidity Sweep و ...) رو یاد بگیره.

## تنظیمات قابل تغییر (در `.env`)

- `SYMBOLS` — لیست نمادها، مثلاً `BTC/USDT,ETH/USDT,SOL/USDT`
- `TIMEFRAMES` — از بزرگ به کوچک، آخری = تایم‌فریم اجرای سیگنال. مثلاً `1d,4h,1h,15m`
- `SCAN_INTERVAL_MINUTES` — هر چند دقیقه بازار اسکن بشه
- `MIN_SCORE_STRONG` / `MIN_SCORE_NORMAL` — آستانه‌ی امتیاز برای سیگنال قوی/معمولی
- `RISK_PER_TRADE_PERCENT`, `MAX_DAILY_LOSS_PERCENT`, `MAX_WEEKLY_LOSS_PERCENT` — فقط جهت نمایش
  در پیام و توقف خودکار سیگنال‌دهی (چون معامله واقعی انجام نمی‌شه، این‌ها بر پایه دکمه‌های Win/Loss محاسبه می‌شن)

وزن‌های امتیازدهی (Trend=20, Order Block=20, ...) توی `config.py` → `SCORE_WEIGHTS` هست،
می‌تونی دستی تغییرشون بدی یا بر اساس خروجی `/stats` تنظیم کنی.

## محدودیت‌های نسخه‌ی فعلی (صادقانه بگم)

- **بدون مدل ML واقعی:** امتیازدهی فعلی قانون‌محورِ وزنی‌ست (دقیقاً طبق طرح خودت)، نه یک مدل
  آموزش‌دیده مثل XGBoost. `learning.py` آمار خام رو جمع می‌کنه؛ وقتی چند صد سیگنال با نتیجه داشتی،
  می‌شه یک مرحله‌ی بعدی اضافه کرد که واقعاً روی `condition_stats` مدل آموزش بده.
- **فیلتر خبر دستی‌ست:** چون API رایگان و پایدار برای کلندر اقتصادی (CPI/FOMC/NFP) وجود نداره،
  خودت یا با یک اسکریپت جدا اخبار رو با `/addnews` وارد می‌کنی.
- **Order Block / FVG / BOS-CHOCH:** پیاده‌سازی‌های رایج و منطقی SMC هستن ولی جایگزین چشم یک
  تریدر حرفه‌ای نیستن — به‌عنوان فیلتر کمکی در امتیازدهی استفاده می‌شن، نه قانون قطعی.
- **بدون معامله خودکار:** طبق خواسته‌ات فقط سیگنال می‌ده؛ اجرای معامله به عهده خودته.

⚠️ این ابزار صرفاً جهت اطلاع‌رسانی است و توصیه مالی محسوب نمی‌شود.
