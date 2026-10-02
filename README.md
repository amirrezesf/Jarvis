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
