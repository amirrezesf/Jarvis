<div align="center" dir="rtl">

<img src="assets/banner.png" alt="Jarvis" width="100%"/>

# Jarvis

**شنوندهٔ کلاس و دستیار صوتی محلی — حریم خصوصی حفظ می‌شود**

<br/>

[![Latest Release](https://img.shields.io/github/v/release/amirrezesf/Jarvis?include_prereleases&label=آخرین%20نسخه&color=6a3fff)](https://github.com/amirrezesf/Jarvis/releases/latest)
[![License](https://img.shields.io/github/license/amirrezesf/Jarvis?label=مجوز&color=blue)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/پلتفرم-Linux%20%7C%20Windows-2ea44f)](#نصب)

</div>

---

<div dir="rtl">

## دربارهٔ پروژه

**Jarvis** یک شنوندهٔ کلاس و دستیار صوتی است که کاملاً روی کامپیوتر خودتان اجرا می‌شود. صدای سیستم را ضبط می‌کند، با Whisper به متن تبدیل می‌کند، و با یک مدل زبانی، دستورالعمل‌های استاد را استخراج و در زمان مناسب اجرا می‌کند.

Jarvis قلب حالت **زنده** در [ربات اسکای‌روم](https://github.com/amirrezesf/SkyroomBot) است، اما به‌تنهایی هم کار می‌کند.

---

## دو حالت

**۱. حالت شنونده (Listener)** — برای کلاس‌های آنلاین
صدای کلاس (آنچه از بلندگوها پخش می‌شود) را می‌شنود، استاد را رونویسی می‌کند، و دستورالعمل‌ها را استخراج و به تصمیم تبدیل می‌کند. این حالت بدون رابط گرافیکی است و می‌تواند داخل برنامه‌های دیگر جاسازی شود.

**۲. حالت دستیار (Assistant)** — تعامل مستقیم
با میکروفن خودتان صحبت می‌کنید، Jarvis پاسخ می‌دهد و در یک پنجرهٔ مشکی نمایش می‌دهد.

---

## قابلیت‌ها

| ویژگی | توضیح |
|---|---|
| **ضبط صدای سیستم** | از منبع monitor پایپ‌وایر — بدون نیاز به میکروفن |
| **تشخیص فعالیت صوتی (VAD)** | با silero-vad و ONNX Runtime — سبک و سریع |
| **تبدیل گفتار به متن** | faster-whisper (large-v3 یا turbo) روی CUDA یا CPU |
| **استخراج دستورالعمل** | با مدل محلی (Ollama) یا ابری (9Router) |
| **تشخیص نام** | تطبیق فازی با rapidfuzz و چند نگارش نام |
| **حالت دستورالعمل** | پشتیبانی از دستورات شرطی مانند «بعد از اینکه اسمت رو خوندم...» |
| **صف تأیید** | اقدامات قبل از اجرا در انتظار تایید شما می‌مانند |
| **هشدار صوتی** | فقط برای مواردی که نیاز به توجه شما دارند |
| **تنظیمات قابل ویرایش** | فایل سادهٔ JSON و یک دیالوگ تنظیمات در برنامهٔ میزبان |

---

## نصب

```bash
pip install git+https://github.com/amirrezesf/Jarvis.git@v0.1.0
```

برای نصب از یک محیط توسعهٔ محلی:

```bash
git clone https://github.com/amirrezesf/Jarvis.git
cd Jarvis
pip install -e .
```

### پیش‌نیازها

- Python 3.12 یا جدیدتر
- Linux با PipeWire برای ضبط صدای سیستم
- Google Chrome — فقط برای برنامهٔ میزبان (SkyroomBot)، نه برای Jarvis
- NVIDIA GPU — اختیاری، برای تبدیل سریع‌تر Whisper روی CUDA
- Ollama — اختیاری، اگر می‌خواهید استخراج کاملاً محلی باشد

### مدل‌ها و دانلودها

هیچ‌کدام از این‌ها همراه پکیج نیستند. در زمان نیاز دانلود می‌شوند:

| مورد | حجم | زمان دانلود |
|---|---|---|
| مدل Whisper large-v3 | ~۳ گیگابایت | اولین اجرای حالت شنونده |
| کتابخانه‌های CUDA | ~۱ گیگابایت | اختیاری، در صورت وجود GPU |
| Ollama + مدل qwen2.5 | ~۲ گیگابایت | اختیاری، برای استخراج محلی |

مدل Whisper در `~/.cache/huggingface/hub/` ذخیره می‌شود و بین اجراها حفظ می‌ماند.

---

## تنظیمات

تمام تنظیمات در یک فایل JSON قرار دارند:

```text
~/.jarvis/config.json
```

اگر این فایل وجود نداشته باشد، در اولین اجرا با مقادیر پیش‌فرض ساخته می‌شود. برنامهٔ میزبان (SkyroomBot) یک دیالوگ گرافیکی برای ویرایش این فایل دارد.

### نمونهٔ فایل تنظیمات

```json
{
    "WHISPER_MODEL": "large-v3-turbo",
    "DEVICE": "cuda",
    "COMPUTE_TYPE": "float16",
    "LANGUAGE": "fa",
    "LOOPBACK_DEVICE": "alsa_output.pci-0000_00_1f.3.analog-stereo.monitor",
    "ALARM_ENABLED": true,
    "ALARM_SOUND_PATH": "default",
    "EXTRACTION_BACKEND": "local",
    "LOCAL_LLM_URL": "http://localhost:11434/v1",
    "LOCAL_EXTRACTION_MODEL": "qwen2.5:3b",
    "NINEROUTER_URL": "http://localhost:20128/v1",
    "NINEROUTER_KEY": "",
    "NINEROUTER_COMBO_NAME": "opencode",
    "ACTION_EXECUTION_ENABLED": true,
    "ACTION_DRY_RUN": true,
    "ACTION_REQUIRE_CONFIRM": ["type_number", "send_chat"],
    "ACTION_DISABLED": []
}
```

### نکات مهم

- `WHISPER_MODEL` — یا نام مدل در هاگینگ‌فیس (`large-v3-turbo`) یا مسیر کامل فایل‌های CTranslate2
- `LOOPBACK_DEVICE` — خالی بگذارید تا خودکار تشخیص داده شود
- `EXTRACTION_BACKEND` — `local` (Ollama) یا `cloud` (9Router)
- `ACTION_DRY_RUN` — `true` یعنی فقط لاگ شود، `false` یعنی اجرا شود
- `ACTION_REQUIRE_CONFIRM` — اقداماتی که قبل از اجرا نیاز به تایید دارند

---

## استفاده

### به‌عنوان کتابخانه

```python
from jarvis.core.context import StudentContext
from jarvis.core.listener import Listener

ctx = StudentContext.from_user({
    "user_name": "امیررضا اسفندیاری",
    "field": "Health Information Technology",
})

def on_decision(decision):
    print(f"{decision.action} {decision.args}")

listener = Listener(context=ctx, on_decision=on_decision)
listener.start()
# ... بعداً ...
listener.stop()
```

### به‌صورت مستقل

```bash
python -m jarvis.main              # حالت دستیار با رابط گرافیکی
python -m jarvis.main --listen-ui  # حالت شنونده با نمایش زنده
python -m jarvis.main --text       # حالت متنی، بدون صوت
```

---

## معماری

```text
صوت (monitor یا میکروفن)
    ↓
silero VAD — تقسیم‌بندی گفتار
    ↓
faster-whisper — تبدیل به متن
    ↓
استخراج (مدل زبانی) — تشخیص دستورالعمل
    ↓
صف دستورالعمل — نگهداری کوتاه‌مدت
    ↓
تشخیص نام — تطبیق فازی
    ↓
تصمیم — جفت کردن دستورالعمل با تریگر
    ↓
هشدار + صف تایید
    ↓
اجرا (از طریق برنامهٔ میزبان)
```

Jarvis هیچ‌وقت خودش اقدام نمی‌کند. تصمیم می‌سازد و به برنامهٔ میزبان می‌دهد. برنامهٔ میزبان تصمیم می‌گیرد که چه کند.

---

## یکپارچگی با ربات اسکای‌روم

ربات اسکای‌روم در نسخهٔ full خود این پکیج را وارد می‌کند و از حالت شنونده استفاده می‌کند. در آن حالت:

- به‌جای میکروفن، صدای سیستم ضبط می‌شود
- استاد رونویسی می‌شود، نه شما
- دستورالعمل‌ها در یک صف تایید نمایش داده می‌شوند
- شما با Enter تایید یا با Esc رد می‌کنید

---

## حریم خصوصی

- تمام پردازش صوت به‌صورت محلی انجام می‌شود
- هیچ‌چیزی به‌طور خودکار به سرور خارجی فرستاده نمی‌شود (مگر اینکه `EXTRACTION_BACKEND` را روی `cloud` بگذارید)
- صدای خام هیچ‌وقت ذخیره نمی‌شود
- فقط رونویسی و تصمیمات در `~/.jarvis/logs/` ذخیره می‌شوند

---

## مجوز

به فایل [LICENSE](LICENSE) مراجعه کنید.

</div>
