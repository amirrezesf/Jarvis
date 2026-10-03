<div align="center" dir="rtl">

<img src="assets/banner.png" alt="Jarvis" width="100%"/>

# Jarvis

**شنونده‌ی کلاس و دستیار صوتی محلی**

<br/>

[![Latest Release](https://img.shields.io/github/v/release/amirrezesf/Jarvis?include_prereleases\&label=آخرین%20نسخه\&color=6a3fff)](https://github.com/amirrezesf/Jarvis/releases/latest)
[![License](https://img.shields.io/github/license/amirrezesf/Jarvis?label=مجوز\&color=blue)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/پلتفرم-Linux%20%7C%20Windows-2ea44f)](#نصب)

</div>

---

<div dir="rtl">

## درباره‌ی پروژه

**Jarvis** یک شنونده‌ی کلاس و دستیار صوتی است که روی سیستم خودتان اجرا می‌شود. صدای سیستم را می‌گیرد، با Whisper به متن تبدیل می‌کند و بعد با کمک یک مدل زبانی، دستورهایی که استاد می‌دهد را پیدا می‌کند و برای اجرا آماده می‌کند.

Jarvis در اصل برای حالت **زنده** در [ربات اسکای‌روم](https://github.com/amirrezesf/SkyroomBot) ساخته شده، ولی می‌توانید خودش را هم به‌صورت مستقل استفاده کنید یا داخل برنامه‌ی دیگری قرار دهید.

---

## Jarvis چه کار می‌کند؟

Jarvis دو حالت اصلی دارد.

### حالت شنونده (Listener)

این حالت بیشتر برای کلاس‌های آنلاین است.

صدایی که از سیستم پخش می‌شود را می‌گیرد، صحبت‌های استاد را رونویسی می‌کند و اگر در صحبت‌ها دستوری وجود داشته باشد، آن را استخراج می‌کند.

این بخش رابط گرافیکی خاصی ندارد و می‌توانید آن را داخل برنامه‌ی دیگری هم استفاده کنید.

### حالت دستیار (Assistant)

در این حالت مستقیماً با خود Jarvis کار می‌کنید. با میکروفن صحبت می‌کنید، Jarvis صدای شما را پردازش می‌کند و پاسخ یا نتیجه را در یک پنجره‌ی ساده نمایش می‌دهد.

---

## قابلیت‌ها

| قابلیت                 | توضیح                                                                                               |
| ---------------------- | --------------------------------------------------------------------------------------------------- |
| **ضبط صدای سیستم**     | در لینوکس از monitor پایپ‌وایر و در ویندوز از WASAPI loopback استفاده می‌کند؛ نیازی به میکروفن نیست |
| **تشخیص صدا (VAD)**    | با Silero و ONNX Runtime؛ بدون نیاز به PyTorch                                                      |
| **تبدیل گفتار به متن** | با faster-whisper و مدل‌های `large-v3` یا `turbo` روی CUDA یا CPU                                   |
| **استخراج دستور**      | با مدل محلی از طریق Ollama یا مدل ابری از طریق 9Router                                              |
| **تشخیص نام**          | با تطبیق فازی توسط `rapidfuzz` و پشتیبانی از چند شکل مختلف نام                                      |
| **دستورهای شرطی**      | مثلاً دستورهایی مثل «بعد از اینکه اسمت رو خوندم...»                                                 |
| **صف تأیید**           | دستورها قبل از اجرا در صف می‌مانند تا تأیید شوند                                                    |
| **هشدار صوتی**         | برای مواردی که نیاز به توجه شما دارند                                                               |
| **تنظیمات**            | تنظیمات در یک فایل JSON نگهداری می‌شود و برنامه‌ی میزبان هم رابطی برای ویرایش آن دارد               |

---

## نصب

برای نصب آخرین نسخه:

```bash
pip install git+https://github.com/amirrezesf/Jarvis.git@v0.1.0
```

اگر می‌خواهید پروژه را برای توسعه نصب کنید:

```bash
git clone https://github.com/amirrezesf/Jarvis.git
cd Jarvis
pip install -e .
```

### چیزهایی که لازم دارید

* Python 3.12 یا جدیدتر
* در لینوکس، PipeWire برای ضبط صدای سیستم
* در ویندوز 10/11، ضبط صدا از طریق WASAPI loopback انجام می‌شود
* Google Chrome فقط برای برنامه‌ی میزبان مثل SkyroomBot لازم است؛ خود Jarvis به Chrome نیازی ندارد
* کارت گرافیک NVIDIA اختیاری است و برای اجرای سریع‌تر Whisper با CUDA استفاده می‌شود
* Ollama اختیاری است؛ اگر بخواهید استخراج دستورها کاملاً روی سیستم خودتان انجام شود

### مدل‌هایی که دانلود می‌شوند

مدل VAD یعنی `silero` همراه خود پکیج نصب می‌شود. بقیه‌ی موارد در اولین استفاده، در صورت نیاز دانلود می‌شوند:

| مورد                   | حجم تقریبی      | زمان دانلود                |
| ---------------------- | --------------- | -------------------------- |
| Whisper `large-v3`     | حدود ۳ گیگابایت | اولین اجرای حالت شنونده    |
| کتابخانه‌های CUDA      | حدود ۱ گیگابایت | اختیاری، برای GPU انویدیا  |
| Ollama + مدل `qwen2.5` | حدود ۲ گیگابایت | اختیاری، برای استخراج محلی |

مدل Whisper در `~/.cache/huggingface/hub/` ذخیره می‌شود و در اجراهای بعدی دوباره دانلود نمی‌شود.

---

## تنظیمات

تنظیمات Jarvis در یک فایل JSON قرار دارد:

```text
~/.jarvis/config.json
```

اگر فایل وجود نداشته باشد، Jarvis در اولین اجرا آن را با تنظیمات پیش‌فرض می‌سازد.

در صورتی که از SkyroomBot استفاده کنید، تنظیمات Jarvis را می‌توانید از داخل دیالوگ تنظیمات خود برنامه هم تغییر دهید.

### نمونه‌ی تنظیمات

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
    "EXTRACTION_MODEL": "opencode",
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

### چند تنظیم مهم

* `WHISPER_MODEL` — می‌تواند نام مدل در Hugging Face مثل `large-v3-turbo` یا مسیر فایل‌های CTranslate2 باشد.
* `LOOPBACK_DEVICE` — اگر خالی باشد، Jarvis دستگاه مناسب را خودش پیدا می‌کند و نتیجه را در فایل تنظیمات ذخیره می‌کند.
* `EXTRACTION_BACKEND` — با `local` از Ollama استفاده می‌شود و با `cloud` استخراج از طریق 9Router انجام می‌شود.
* `EXTRACTION_MODEL` — نام مدل یا Combo در حالت ابری؛ مثلاً همان مقداری که در 9Router ساخته‌اید.
* `LOCAL_EXTRACTION_MODEL` — مدل مورد استفاده در Ollama، مثلاً `qwen2.5:3b`.
* `ACTION_DRY_RUN` — وقتی روی `true` باشد، دستورها فقط در لاگ ثبت می‌شوند و اجرا نمی‌شوند.
* `ACTION_REQUIRE_CONFIRM` — مشخص می‌کند کدام کارها قبل از اجرا نیاز به تأیید شما دارند.

---

## استفاده

### استفاده به‌عنوان کتابخانه

اگر بخواهید Jarvis را داخل برنامه‌ی خودتان استفاده کنید، می‌توانید Listener را مستقیماً اجرا کنید:

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

### اجرای مستقیم

Jarvis را می‌توانید بدون برنامه‌ی میزبان هم اجرا کنید:

```bash
python -m jarvis.main              # حالت دستیار با رابط گرافیکی
python -m jarvis.main --listen-ui  # حالت شنونده با نمایش زنده
python -m jarvis.main --text       # حالت متنی، بدون صوت
```

---

## معماری

مسیر اصلی پردازش صدا در Jarvis تقریباً این شکلی است:

```text
صدای سیستم / میکروفن
        │
        ▼
   Silero VAD
  تشخیص بخش‌های صوتی
        │
        ▼
  faster-whisper
   تبدیل به متن
        │
        ▼
  Language Model
 استخراج دستورها
        │
        ▼
   Action Queue
  نگهداری موقت دستورها
        │
        ▼
  Name Matching
  تشخیص اینکه دستور
  مربوط به چه کسی است
        │
        ▼
     Decision
   ساخت تصمیم نهایی
        │
        ▼
  تأیید / هشدار
        │
        ▼
  برنامه‌ی میزبان
```

نکته‌ی مهم این است که **Jarvis خودش کاری را اجرا نمی‌کند**. وظیفه‌ی Jarvis این است که از روی صدای ورودی به یک تصمیم برسد و آن تصمیم را به برنامه‌ای که از آن استفاده می‌کند تحویل دهد.

مثلاً در SkyroomBot، Jarvis می‌تواند به این نتیجه برسد که «استاد از امیررضا خواسته شماره‌ای را وارد کند». این تصمیم وارد صف تأیید می‌شود و بعد از تأیید، خود SkyroomBot تصمیم می‌گیرد چه کاری با آن انجام دهد.

این جداسازی باعث شده Jarvis بتواند بدون وابستگی به SkyroomBot هم استفاده شود.

---

## استفاده در SkyroomBot

SkyroomBot در نسخه‌ی `full`، Jarvis را به‌عنوان یک پکیج وارد می‌کند و از حالت Listener آن استفاده می‌کند.

در این حالت:

* به‌جای میکروفن، صدای کلاس از سیستم گرفته می‌شود.
* صحبت‌های استاد با Whisper رونویسی می‌شوند.
* دستورهای مربوط به دانشجو استخراج می‌شوند.
* دستورها قبل از اجرا در صف تأیید قرار می‌گیرند.
* اجرای واقعی کارها را خود SkyroomBot انجام می‌دهد.

---

## حریم خصوصی

Jarvis تا جای ممکن برای پردازش محلی طراحی شده است:

* پردازش و تبدیل صدا به متن روی سیستم خودتان انجام می‌شود.
* صدای خام کلاس یا میکروفن ذخیره نمی‌شود.
* متن رونویسی‌شده و تصمیم‌های استخراج‌شده در لاگ‌ها ذخیره می‌شوند.
* اگر `EXTRACTION_BACKEND` روی `cloud` باشد، متن برای سرویس 9Router ارسال می‌شود.
* در حالت `local`، استخراج دستور هم با Ollama روی سیستم خودتان انجام می‌شود.

---

## مجوز

برای اطلاعات مربوط به مجوز، فایل [LICENSE](LICENSE) را ببینید.

</div>
