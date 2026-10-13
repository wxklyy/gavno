# ProjectRise-1.0.ipa — разбор античита

## 1. Что это за билд

| Поле | Значение |
|------|----------|
| Игра | Standoff 2 (Axlebolt), ребренд «Project Rise» |
| Bundle ID | `com.Rise.Rework` |
| CFBundleShortVersion | `0.19.10` (CFBundleVersion 1090) |
| Движок | Unity (IL2CPP, metadata v24), iOS arm64 |
| Входной бинарь | `standoff2` (71 KB) — тонкий лаунчер, cryptid=0 (DRM снят) |
| Основной код | `Frameworks/UnityFramework.framework/UnityFramework` (72.7 MB) |
| IL2CPP метадата | `Data/Managed/Metadata/global-metadata.dat` (10.6 MB) |

Внешних античит-SDK (BattlEye / EAC / Xigncode / ACE) **нет**. Античит — **самописный, Axlebolt**, частично на C# (IL2CPP), частично нативные проверки.

---

## 2. Архитектура античита

Найдены три основных компонента:

### A) `Axlebolt.Standoff.Anitcheat.AntiCheatManager` (Assembly-CSharp)
Клиентский менеджер детекта (typo «Anitcheat» в неймспейсе — у разработчиков).
- Обфусцированные поля: `LIGKLBFLNEN, FFJIMKAILFI, BAHHLAMMDFL, DLCAHFLIMJE, NHCPAHOMDPN, EGBGCDJMHAC, FBBKEBDHEHG, CPEAJJLLJEP, LLPBELGKJPN, HHKNEEMFPGE, FACAPMOOODO, MLKLGODNHEL, PDEOIKKDOMF, ENDLOAMFBHF, OPAHDCBDMEH, IOOLPINHCJG, MPICODIKGID`.
- Обфусцированные методы: `NFIAANGEACF, CLNMOGLLDMN, HJABCADCDMB, BLBHHGOPBCM, DHNPEOIDGED, ECHAHOJDKEB, DKCNABDGPOB, JIHHIOOOIPL, EGJIPKOMIMC, CKIHKHLBKPB, FGDLBIABKOK, BAPICMEIIOA, IIIJDOLJHKB, DMGAOIANFNK`.
- Unity-колбэки: `OnApplicationPause`, `OnDestroy`.
- Вложенные хелперы: `<GetCheatDetector>`, `<GetUnityPlayer>`, `<GetContext>`, `<GetPackageManager>`, `<GetItemFromArray>` — то есть детектор обращается к Android `PackageManager` (для iOS-билда это мёртвый/условный код, класс кроссплатформенный).

### B) `Axlebolt.Standoff.Game.Anticheat.GameAntiCheatManager` (Assembly-CSharp)
Серверно-игровой менеджер.
- Методы: `ReportViaServer`, `PlayerBannedHandler`.
- Строки рядом: `anticheat_enabled_0.10.3`, `Report {0} {1}`, `GameAntiCheatManager`, `ban`, `IsStealer`, `Damage cheat`, `com.axlebolt.standoff2`.
- Тип `ColliderAnitСheat2` (опечатка в имени класса) — детект по коллайдерам.

### C) `Axlebolt.Standoff.Bolt.Anticheat.Android.SystemWatch` (Bolt.Api.dll)
Класс `Observer` — сетевой вотчер (Bolt networking). В iOS-бинаре присутствует только как тип в метаданных; реализация ориентирована на Android (package-manager based).

---

## 3. Категории детектов (из строковых литералов)

### Игровые читы (серверная/клиентская валидация):
- `Aimbot cheat` — аимбот
- `Damage cheat` / `DamageAntiCheat` — невалидный урон
- `Weapon ammo cheat` — бесконечные патроны
- `Collider cheat` — модифицированные коллайдеры (вх)
- `No recol cheat` — отключение отдачи
- `Wallhack`
- `Injection cheat` — инъекция кода
- `time_cheat` — ускорение времени (speedhack)
- `Unknown cheat {0}`
- `HackDetectionCollider` — сущность коллайдера-детектора
- `IsStealer`

### Системные / анти-тампер (собираются в protobuf-пакет, base64 рядом — это descriptor `JS_STRING/JS_NUMBER`):
- `Root` — jailbreak/root
- `Injected` — внедрённые dylib (frida/substrate)
- `IsFromAppStore` — не из App Store (re-sign)
- `IsDebugged` — под отладчиком
- `CydiaUrl` — `cydia://package/com.avl.com`
- `Symlink` — симлинки системных путей
- `WritePermission` — запись в системные каталоги
- `JailAppsExists` — наличие джейл-приложений
- `Mod`, `Null`, `Dylibs`, `ApplicationVersion`

### Virtual space / клонеры (Android-наследие):
- `virtual_space`, `virtual_space_packages`, `Anticheat/VirtualSpaceWarning`

### Управление/конфиг:
- `anticheat.disable.checkpermission` — пермишен на отключение (для разработчиков)
- `anticheat_{0}_enabled` — пер-функциональные флаги
- `anticheat_aim_new_enabled2`
- `Init AntiCheatDetector {0}, IsEnabled: {1}`
- `Please restart game!`

### Реакция на детект (UI/сервер):
- `cheat_activities`, `block_cheat_activities`, `detected_cheat_activities`
- `Uninstall cheat`, `Exit`, `Warning`
- `ReportViaServer`, `Report {0} {1}` — отправка репорта на сервер
- `PlayerBannedHandler`, `was banned (`
- `YOUR ACCOUNT IS BANNED. TIME LEFT {0} seconds`
- `Auth/YouAccountIsBanned`, `Auth/YouDeviceIsBanned`
- `RankedMatchmaking/BannedForLeaving`, `RankedMatchmaking/RankedGamesBanned`, `RankedIsBanned`, `ranked_banned_until`, `BanedForVoteKicking`
- `Ex/HackingAppDetectedRpcException`

---

## 4. Нативный джейлбрейк-детект (в UnityFramework)

Файл исходника: `ios_jailbreak.mm`, функция выдаёт `isJailBroken`, `isDebugged`, `embedded.mobileprovision`.

Пути, которые проверяются:
```
/Applications/Cydia.app
/Applications/blackra1n.app
/Applications/FakeCarrier.app
/Applications/IntelliScreen.app
/Applications/Snoop-itConfig.app
/Library/MobileSubstrate/MobileSubstrate.dylib
/Library/MobileSubstrate/DynamicLibraries/Veency.plist
/Library/MobileSubstrate/DynamicLibraries/LiveClock.plist
/System/Library/LaunchDaemons/com.saurik.Cydia.Startup.plist
/System/Library/LaunchDaemons/com.ikey.bbot.plist
/usr/libexec/ssh-keysign
/usr/libexec/cydia/
/usr/sbin/frida-server
/private/var/lib/cydia
/private/var/tmp/cydia.log
/var/lib/cydia
/private/jailbreak.txt          (тест записи)
cydia://package/com.avl.com     (canOpenURL)
```
Часть этого блока относится к рекламному SDK (IronSource рядом собирает `isJailBroken = %@` в аналитику), но строки `ios_jailbreak.mm`, `isDebugged`, `Jailbreak test string` — это код приложения.

---

## 5. Выводы

1. **Античит самописный Axlebolt**, состоит из двух уровней:
   - **клиентский** `AntiCheatManager` — системные проверки (root/jailbreak/injection/debug/AppStore), сбор «cheat_activities» и блокировка/репорт;
   - **игровой/серверный** `GameAntiCheatManager` — валидация урона, патронов, коллайдеров, аимбота, wallhack, спидхака (`time_cheat`), с `ReportViaServer` и баном.
2. Имена методов/полей обфусцированы (11-символьные `AAAAAAAABCD`), но строки-литералы и названия типов/неймспейсов **не обфусцированы**, что даёт полную карту функций.
3. Флаги детектов сериализуются protobuf'ом (`JS_STRING/JS_NUMBER` descriptor) и отправляются через `ReportViaServer`.
4. В iOS-билде остались Android-специфичные классы (`Bolt.Anticheat.Android.SystemWatch`, `GetPackageManager`) — код кроссплатформенный, условно компилируемый.
5. Серверные баны: аккаунт и девайс (`YouAccountIsBanned`, `YouDeviceIsBanned`, `ranked_banned_until`, `banCode`).

## 6. Артефакты анализа (в `native/_analysis/`)
- `extracted/` — вытащенные `Info.plist`, `standoff2`, `UnityFramework`, `global-metadata.dat`
- `unityframework_strings.txt` — 233k строк из нативного бинаря
- `meta_strings.txt` — 78.5k строк таблицы строк IL2CPP
- `meta_literals.txt` — 15.5k строковых литералов C#
- `ac_final.txt`, `ac_types.txt`, `ac_class.txt` — дампы типов/методов античита
- скрипты: `parse_macho.py`, `dump_meta_strings.py`, `parse_ac*.py`, `find_ac*.py`