# Trading Signal Bot (Analysis-Only — No Execution)

این ربات **هرگز** پوزیشن باز یا بسته نمی‌کند، سفارش ارسال نمی‌کند و به
هیچ API معاملاتی/برداشتی متصل نمی‌شود. خروجی آن فقط **Signal** تحلیلی
است؛ تصمیم نهایی و اجرای دستی همیشه با شماست.

```
Market Data → Data Validation → Feature Engineering → Regime Detection
→ Strategy Engine (Trend/Momentum/Breakout/Mean-Reversion)
→ ML Model (optional) → LLM Sentiment (optional)
→ Signal Aggregator → Risk Analysis (informational) → Signal → Notification
```

## هزینه: $0

همه‌چیز با Python + کتابخانه‌های متن‌باز + داده‌ی عمومی رایگان (از طریق
`ccxt`، بدون نیاز به API Key) کار می‌کند. ML و LLM هر دو **اختیاری**اند
و هسته‌ی اصلی سیگنال بدون آن‌ها هم کاملاً کار می‌کند.

## نصب

```bash
cd trading_signal_bot
python3 -m venv venv
source venv/bin/activate        # ویندوز: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # اختیاری — برای Telegram
```

اگر می‌خواهید ML فعال باشد ولی نمی‌خواهید xgboost/lightgbm نصب کنید،
`config/settings.py` → `MLConfig.model_type = "sklearn"` را تنظیم کنید
(فقط با scikit-learn کار می‌کند، بدون هیچ نصب اضافه).

اگر اصلاً ML/DL/LLM نمی‌خواهید:

```python
# config/settings.py
ml.enabled = False
dl.enabled = False   # از قبل False است
llm.enabled = False  # از قبل False است
```

هسته‌ی Trend/Momentum/Breakout/Mean-Reversion + Risk + Notification
همچنان کامل کار می‌کند.

## تنظیمات اصلی (`config/settings.py`)

| بخش | توضیح |
|---|---|
| `RunConfig.symbols` | نمادها، مثلاً `["BTC/USDT", "ETH/USDT"]` |
| `RunConfig.timeframe` | تایم‌فریم؛ پیش‌فرض `1h` (Intraday/Swing) |
| `RiskConfig.account_equity` | فقط برای محاسبه‌ی Position Size پیشنهادی — پول واقعی لمس نمی‌شود |
| `NotificationConfig.telegram_*` | با ساخت یک بات در `@BotFather` پر کنید (اختیاری) |

## تلگرام (اختیاری، رایگان)

1. در تلگرام به `@BotFather` پیام دهید → `/newbot` → توکن بگیرید.
2. `chat_id` خودتان را با ارسال یک پیام به بات و باز کردن
   `https://api.telegram.org/bot<TOKEN>/getUpdates` پیدا کنید.
3. این دو مقدار را در `.env` بگذارید:
   ```
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_CHAT_ID=...
   ```

این توکن **فقط** اجازه‌ی ارسال پیام دارد — هیچ دسترسی معاملاتی امکان‌پذیر نیست.

## استفاده

### ۱. Backtest (روی داده‌ی تاریخی رایگان)

```bash
python main.py backtest --symbol BTC/USDT --timeframe 1h --bars 3000
```

گزارش شامل Win Rate، Profit Factor، Expectancy، Max Drawdown، Sharpe،
Sortino، Avg Win/Loss، و False Signal Rate است. هزینه‌ی تراکنش و
Slippage به‌صورت پیش‌فرض لحاظ می‌شوند.

### ۲. Walk-Forward Validation (ضد Overfitting)

```bash
python main.py walk-forward --symbol BTC/USDT --timeframe 1h --bars 5000 \
    --train-bars 1500 --oos-bars 300 --step-bars 300
```

اگر Profit Factor در پنجره‌های Out-of-Sample خیلی کمتر از In-Sample بود،
یعنی استراتژی Overfit شده — قبل از اجرای زنده اصلاحش کنید.

### ۳. یک بار اجرا (تست سریع سیگنال زنده)

```bash
python main.py once
```

### ۴. حالت PAPER_SIGNAL (سیگنال مستمر، بدون معامله)

```bash
python main.py paper-signal
```

### ۵. حالت LIVE_SIGNAL (همان، فقط برای استفاده‌ی واقعی)

```bash
python main.py live-signal
```

**نکته:** `live-signal` هم دقیقاً مثل `paper-signal` فقط سیگنال تولید
می‌کند. در این پروژه هیچ حالت اجرای خودکار معامله وجود ندارد.

## جلوگیری از Signal Spam

هر سیگنال با `Signal ID`، زمان، Asset و Timeframe ثبت می‌شود
(`storage/signal_state.json`). پیام جدید فقط در این موارد ارسال می‌شود:

- سیگنال جدید (تغییر جهت یا اولین بار)
- به‌روزرسانی Stop Loss یا Take Profit
- Invalidation سیگنال قبلی

## ساختار پروژه

```
config/       تنظیمات مرکزی
data/         دریافت و اعتبارسنجی داده‌ی رایگان بازار (ccxt، بدون کلید)
features/     مهندسی ویژگی (EMA, RSI, MACD, Bollinger, ADX, Donchian, ...)
regime/       تشخیص رژیم بازار (Trend/Range/High-Vol)
strategies/   چهار استراتژی: Trend Following, Momentum, Breakout, Mean Reversion
ml/           مدل ML اختیاری (روشن به‌صورت پیش‌فرض؛ scikit-learn/XGBoost/LightGBM — رایگان و Local)
dl/           مدل Deep Learning اختیاری (PyTorch، خاموش به‌صورت پیش‌فرض، بدون شکست پروژه اگر torch نصب نباشد)
llm/          Sentiment از اخبار رایگان RSS + یک تحلیل‌گر کلیدواژه‌ای رایگان (روشن به‌صورت پیش‌فرض، بدون نیاز به سرور LLM)
aggregator/   ترکیب رای‌ها به یک Signal نهایی + قالب‌بندی پیام
risk/         محاسبات ریسک صرفاً اطلاعاتی (بدون اجرای معامله)
notification/ ارسال به Console / Log / Telegram
backtest/     Backtester + Walk-Forward Validation
storage/      دیتای بازار انباشته‌شده + تاریخچه‌ی اجراها + وضعیت ضد-Spam (جزئیات بالا)
dashboard/    ساخت داشبورد ایستای HTML از روی storage/
docs/         خروجی داشبورد — همینجا را GitHub Pages نمایش می‌دهد
.github/workflows/  فایل زمان‌بندی رایگان GitHub Actions
pipeline.py   اتصال کامل مراحل بالا به هم
main.py       نقطه‌ی ورود: backtest / walk-forward / once / dashboard / paper-signal / live-signal
```

## چرا امن است (بدون قابلیت معامله)

- هیچ‌جای کد `create_order`، `cancel_order`، `withdraw` یا مشابه آن صدا زده نمی‌شود.
- `data/fetcher.py` فقط `fetch_ohlcv` را از ccxt استفاده می‌کند — کاملاً Read-Only.
- اگر API Key بورس را هم وارد کنید (اختیاری)، فقط برای دسترسی عمومی/فقط-خوانده استفاده می‌شود؛ توصیه می‌شود اصلاً Key ندهید چون داده‌ی OHLCV بدون کلید هم در دسترس است.
- توکن تلگرام فقط پیام ارسال می‌کند.

## دیتا کجا ذخیره می‌شود؟ (برای آموزش مدل ML/DL)

- **کندل‌های بازار (OHLCV)**: در `storage/history/<نماد>_<تایم‌فریم>.csv`.
  هر بار که ربات اجرا می‌شود، کندل‌های تازه را می‌گیرد و به همین فایل
  اضافه می‌کند (بدون تکراری) — یعنی دیتا با گذر زمان **انباشته**
  می‌شود، نه اینکه هر بار از صفر شروع شود. مدل ML/DL دقیقاً از همین
  فایل آموزش می‌بیند. حداکثر ۶۰۰۰ کندل آخر برای هر نماد نگه داشته
  می‌شود تا حجم ریپو زیاد نشود (قابل تغییر در `storage/history_store.py`).
- **تاریخچه‌ی کامل هر اجرا** (سیگنال یا NEUTRAL، هر چه پیش آمد): در
  `storage/run_log.jsonl` — همین فایل چیزی است که داشبورد از آن ساخته می‌شود.
- **آخرین سیگنال هر نماد** (برای جلوگیری از Spam): در `storage/signal_state.json`.

در GitHub Actions، چون هر اجرا روی یک ماشین تازه شروع می‌شود، این
فایل‌ها بعد از هر اجرا مستقیماً به خود ریپازیتوری **Commit** می‌شوند
(مرحله‌ی آخر Workflow) — پس چیزی گم نمی‌شود و دفعه‌ی بعد از همان‌جا
ادامه پیدا می‌کند.

## داشبورد (رایگان، روی GitHub Pages)

یک داشبورد ایستا (`docs/index.html`) وجود دارد که بعد از هر اجرای
ربات خودکار بازسازی و Commit می‌شود. نشان می‌دهد:

- وضعیت فعلی هر نماد (جهت، Confidence، Regime، Entry/SL/TP)
- نمودار روند Confidence در اجراهای اخیر
- حجم دیتای ذخیره‌شده برای هر نماد (چند کندل برای آموزش مدل جمع شده)
- تاریخچه‌ی کامل همه‌ی اجراها — حتی آن‌هایی که سیگنالی نداشتند (NEUTRAL) و پیامی ارسال نشد

### فعال کردن نمایش آن (یک‌بار، حدود ۱ دقیقه):

1. در ریپازیتوری گیت‌هاب برو به **Settings → Pages**.
2. زیر «Build and deployment» → «Source» را بگذار روی **Deploy from a branch**.
3. Branch را `main` و پوشه را `/docs` انتخاب کن → Save.
4. بعد از چند دقیقه، آدرسی شبیه `https://USERNAME.github.io/REPO_NAME/` فعال می‌شود — این داشبورد توست، همیشه رایگان و به‌روز.

می‌توانی دستی هم بسازیش (برای تست لوکال):
```
python main.py dashboard
```
و فایل `docs/index.html` را در مرورگر باز کنی.

## اجرای رایگان و مستمر با GitHub Actions (بدون سرور، بدون Vercel)

این پروژه طوری طراحی شده که هر بار فقط **یک دور کامل** انجام می‌دهد
(`python main.py once`: گرفتن داده → تحلیل → نوتیف) و تمام می‌شود. این
دقیقاً مدلی است که **GitHub Actions** برایش ساخته شده — رایگان، بدون
سرور، بدون نیاز به Vercel.

مراحل:

1. یک ریپازیتوری روی GitHub بساز و کل این پوشه را در آن Push کن.
2. در تنظیمات ریپو (Settings → Secrets and variables → Actions) این
   Secret ها را اضافه کن (فقط همان‌هایی که لازم داری):
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, و اگر خواستی
   `EXCHANGE_API_KEY` / `EXCHANGE_API_SECRET` (فقط Read-Only).
3. فایل `.github/workflows/signal_bot.yml` از قبل آماده است و هر
   ۱۵ دقیقه یک‌بار ربات را اجرا می‌کند (قابل تغییر).
4. همین. از تب **Actions** در گیت‌هاب می‌توانی اجراها و لاگ‌ها را ببینی،
   یا با دکمه‌ی **"Run workflow"** یک‌بار دستی تستش کنی.

### چرا GitHub Actions و نه Vercel؟

- Vercel برای اپ‌های وب/سرورلس (معمولاً Next.js) ساخته شده. Cron داخلی‌اش
  در پلن رایگان (Hobby) فقط **یک‌بار در روز** اجرا می‌شود؛ برای هر فاصله‌ی
  کمتر (مثلاً هر ۱۵ دقیقه که برای این ربات لازم است) باید پلن Pro
  ($20/ماه) بگیری.
- GitHub Actions می‌تواند حداقل هر **۵ دقیقه** یک‌بار اجرا شود، برای
  ریپوی خصوصی حدود ۲۰۰۰ دقیقه در ماه رایگان دارد (برای ریپوی Public
  کاملاً نامحدود و رایگان)، و مدل «اجرا کن و تمومش کن» پروژه‌ی ما را
  دقیقاً پشتیبانی می‌کند — بدون هیچ تنظیم اضافه.
- نکته: زمان‌بندی گاهی چند دقیقه دیر اجرا می‌شود (وقتی سرورهای گیت‌هاب
  شلوغ‌اند) — برای سیگنال‌های Intraday/Swing این تاخیر بی‌اهمیت است.
- اگر ریپو Public باشد و ۶۰ روز هیچ Commit جدیدی نخورد، گیت‌هاب
  زمان‌بندی خودکار را غیرفعال می‌کند (این یک قانون گیت‌هاب است، نه
  پروژه). چون این Workflow خودش هر بار فایل وضعیت را Commit می‌کند،
  این مشکل عملاً پیش نمی‌آید.

اگر بعداً خواستی یک **داشبورد وب** هم برای دیدن سیگنال‌ها بسازی
(مثلاً یک صفحه‌ی ساده که آخرین سیگنال‌ها را نشان بدهد)، آن بخش وب را
می‌توان جدا روی Vercel دیپلوی کرد؛ اما خودِ ربات تحلیل‌گر بهتر است
همیشه روی GitHub Actions (یا یک VPS/کامپیوتر شخصی) بماند.

## گام بعدی پیشنهادی

1. اول `backtest` و `walk-forward` را روی چند نماد و تایم‌فریم اجرا کنید.
2. اگر نتایج OOS رضایت‌بخش بود، با `paper-signal` چند روز بدون تصمیم واقعی فقط سیگنال‌ها را رصد کنید.
3. وقتی به کیفیت سیگنال‌ها اعتماد کردید، برای معاملات واقعی از `live-signal` استفاده کنید — اما اجرای معامله همیشه دستی و با تصمیم شماست.
