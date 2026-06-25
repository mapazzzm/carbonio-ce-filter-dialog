# carbonio-ce-filter-dialog

[<sup>ru</sup> Русский](#русский) | [<sup>en</sup> English](#english)

---

## Русский

Патч для **Carbonio CE** (Zextras), добавляющий два новых возможности в интерфейс работы с письмами:

1. **«Создать фильтр»** — пункт в контекстном меню и тулбаре превью, открывающий диалог создания фильтра с предзаполнением по отправителю
2. **«Выделять цветом»** — новое действие в редакторе фильтров, подсвечивающее подходящие письма цветом в списке

### Функциональность

#### Создать фильтр

Правый клик на письмо (или кнопка «⋮» в превью) → **«Создать фильтр»**.

Открывается стандартный диалог создания фильтра с предзаполненными полями:

- **Название**: «Обработка писем от user@domain.com»
- **Условие**: «От кого» → точное совпадение → адрес отправителя
- **Действие**: Переместить в папку
- **Активный**: включён

После нажатия «Создать» фильтр сохраняется и появляется диалог подтверждения:

> «Применить условия созданного фильтра для ранее полученных писем?»

- **Нет** → снекбар «Фильтр создан»
- **Да** → стандартный Apply-диалог с предвыбранной папкой «Входящие» и реальным счётчиком писем

#### Выделять цветом

В редакторе фильтров (Настройки → Фильтры) в списке действий появляется пункт **«Выделять цветом»**.

При выборе отображается палитра из 10 цветов. Письма, попавшие под условие фильтра, выделяются полупрозрачным фоном в списке сообщений:

| Цвет | | Цвет | |
|------|---|------|---|
| Красный | 🔴 | Синий | 🔵 |
| Оранжевый | 🟠 | Фиолетовый | 🟣 |
| Жёлтый | 🟡 | Розовый | 🌸 |
| Зелёный | 🟢 | Коричневый | 🟤 |
| Бирюзовый | 💠 | Серый | ⚪ |

Цвет хранится как тег с именем цвета («Красный», «Синий» и т. д.). Теги с цветами:
- видны в панели тегов с соответствующим цветным кружком Zimbra
- **не** показывают иконку тега на строках писем (подсветка строки достаточно информативна)

Чтобы убрать подсветку — удалить или отключить фильтр, затем снять тег с писем.

#### Исправление: отключение безусловного фильтра

Фильтр **без условия** (например, пересылка всех писем — только действие `redirect`) в стандартном Carbonio CE **нельзя отключить**: снимаешь галочку «Активный фильтр» → Сохранить → открываешь снова, галочка опять стоит.

Причина — в **бэкенде** Carbonio, а не в интерфейсе: правило деактивируется оборачиванием в Sieve `disabled_if <условие> { ... }`. Если условия нет — оборачивать нечего, и `GetFilterRules` всегда возвращает `active:true`.

Патч представляет «выключенный безусловный фильтр» через скрытый `trueTest` (Sieve `true` — совпадает со всеми письмами, для пересылки-всех поведение идентично): `disabled_if true { redirect ...; stop; }`. Хелпер `__cuFilterFix` подставляет `trueTest` при сохранении (через `ModifyFilterRules`/`ModifyOutgoingFilterRules`), а билдер условий скрывает `trueTest` от UI — фильтр по-прежнему отображается без условий, без фантомной строки «тема содержит…».

### Языки

Веб-интерфейс автоматически определяет язык из настроек пользователя.

- **Русский**: переводы добавляются в `ru.json` автоматически при установке
- **Английский и другие**: строки встроены в код как значения по умолчанию (`t("key", "English fallback")`); `en.json` дополняется при установке

### Требования

| | |
|---|---|
| Carbonio CE | ≥ 26.x |
| Ubuntu | 22.04 (Jammy) или 24.04 (Noble) |
| Python | 3.6+ |
| carbonio-mails-ui | **1.31.7** (hash `21dee67f…`) |

### Установка

Одной командой:

```bash
curl -fsSL https://raw.githubusercontent.com/mapazzzm/carbonio-ce-filter-dialog/main/install.py | sudo python3
```

Или клонировать репозиторий:

```bash
git clone https://github.com/mapazzzm/carbonio-ce-filter-dialog.git
cd carbonio-ce-filter-dialog
python3 install.py
```

После установки обновите страницу в браузере: **Ctrl+Shift+R**

### Проверка

```bash
python3 install.py check
```

Или без клонирования:

```bash
curl -fsSL https://raw.githubusercontent.com/mapazzzm/carbonio-ce-filter-dialog/main/install.py | sudo python3 - check
```

### Откат

```bash
python3 install.py rollback
```

Перед каждой установкой скрипт автоматически сохраняет бэкап оригинальных файлов.

### После `apt upgrade carbonio-mails-ui`

Обновление пакета перезаписывает JS-файлы — патч нужно переприменить:

```bash
python3 install.py check || python3 install.py
```

Или без клонирования:

```bash
curl -fsSL https://raw.githubusercontent.com/mapazzzm/carbonio-ce-filter-dialog/main/install.py | sudo python3 - check || \
curl -fsSL https://raw.githubusercontent.com/mapazzzm/carbonio-ce-filter-dialog/main/install.py | sudo python3
```

Скрипт поддерживает **инкрементальное обновление**: если предыдущая версия уже установлена, применяются только недостающие части.

### Как это работает

Скрипт вносит точечные изменения в четыре минифицированных JS-файла и два JSON-файла локализации:

**Файлы JS:**

| Файл | Изменения |
|------|-----------|
| `388.*.chunk.js` | Добавляет webpack-модуль 9999 и пункт «Создать фильтр» в тулбар превью |
| `336.*.chunk.js` | Добавляет модуль 9999 и пункт в контекстное меню; добавляет подсветку строк сообщений и скрывает иконку цветового тега |
| `mail-setting-view.*.chunk.js` | Экспортирует компоненты диалогов (Ae, Jy); добавляет действие «Выделять цветом» с палитрой цветов; создаёт теги через SOAP API; внедряет хелпер `__cuFilterFix` (`trueTest`) для отключения безусловных фильтров |
| `folder-panel-view.*.chunk.js` | Добавляет подсветку строк бесед (conversation view) |
| `917.*.chunk.js` | Исправляет `i.tags is not iterable` при оптимистичном тегировании сообщений без тегов |

**Файлы локализации:**

| Файл | Добавляемые ключи |
|------|-------------------|
| `i18n/ru.json` | `action.apply_filter_confirm`, `modals.apply_filters.*`, `label.yes/no`, `settings.set_color`, `settings.set_color_placeholder` |
| `i18n/en.json` | `label.yes/no`, `settings.set_color`, `settings.set_color_placeholder` |

Никаких внешних зависимостей — все React-компоненты и Carbonio Design System уже загружены приложением.

### История изменений

**Фикс: отключение безусловного фильтра** *(текущая версия)*
Добавлен патч в `mail-setting-view.*.chunk.js`, позволяющий деактивировать фильтр без условия (пересылка всех писем). Баг — в бэкенде Carbonio (`disabled_if` требует условие); фикс представляет выключенное состояние через скрытый `trueTest`. Ставится/проверяется/откатывается независимо от остальных функций (маркер `__cuFilterFix`).

**Добавлено «Выделять цветом»** + **Фикс `i.tags is not iterable`**
Интегрирована функция подсветки писем цветом: новое действие в редакторе фильтров, поддержка в списке сообщений и бесед, полная локализация ru/en.

Одновременно исправлен баг Carbonio в `917.*.chunk.js`: функция `optimisticallyHandleMessageActions` падала с `TypeError: i.tags is not iterable` при операции тегирования сообщения, у которого ещё не было тегов (`i.tags === undefined`). Фикс: добавлен fallback `i.tags||[]` в двух местах операций TAG/UNTAG.

**Фикс скроллбара в контекстном меню**
Компонент `Dropdown` из Carbonio Design System имеет дефолтный `maxHeight: 50vh`. После добавления пункта «Создать фильтр» список пунктов правого клика превышал этот лимит и появлялась полоса прокрутки. Фикс: добавлен `maxHeight:"100vh"` в оба Dropdown контекстного меню в `336.*.chunk.js`.

---

## domain_color_filter.py

Отдельный скрипт для управления цветовым выделением писем **на уровне домена** без вмешательства в клиентский JS.

### Принцип работы

Использует `zimbraMailAdminSieveScriptBefore` — административный sieve-скрипт, который Carbonio/Zimbra применяет к входящим письмам **до** пользовательских фильтров. Скрипт устанавливается на домен целиком, **не виден пользователям** и не конфликтует с их собственными фильтрами.

При срабатывании фильтра к письму добавляется тег с именем цвета («Красный», «Зелёный» и т. д.). Если установлен патч `install.py` из этого репозитория, такие теги визуально подсвечивают строку письма цветным фоном в интерфейсе.

### Возможности

- Интерактивно запрашивает целевой домен, домен-отправитель и цвет
- Проверяет, установлен ли уже аналогичный фильтр
- При повторном запуске предлагает добавить ещё один фильтр или удалить существующий
- Поддерживает несколько правил на одном домене

### Запуск

```bash
python3 domain_color_filter.py
```

Скрипт запускается от `root` на сервере Carbonio. Внутри использует `su - zextras -c "zmprov ..."`.

### Пример сеанса

```
Домен Carbonio (для которого применяем): example.com
Получаю текущий zimbraMailAdminSieveScriptBefore для example.com...
  domain-color-filter правил не найдено.

Домен-отправитель (условие «from» contains): external.com

Доступные цвета / Available colors:
   1. Красный (Red)
   2. Оранжевый (Orange)
   3. Жёлтый (Yellow)
   4. Зелёный (Green)
   5. Бирюзовый (Cyan)
   6. Синий (Blue)
   7. Фиолетовый (Purple)
   8. Розовый (Pink)
   9. Коричневый (Brown)
  10. Серый (Gray)
Номер цвета / Color number: 4

Будет применено / Will apply:
  Домен / Domain:          example.com
  От домена / From domain: external.com
  Цвет / Color:            Зелёный (Green)
  Фильтр не виден пользователям / Not visible to users (zimbraMailAdminSieveScriptBefore)
Применить? / Apply? [ДА/нет]: да

✓ Правило применено для example.com.
  Письма от *@external.com будут помечены тегом «Зелёный» (Green).

Для удаления запустите скрипт повторно и выберите «удалить».
To remove: re-run the script and choose «удалить».
```

### Удаление фильтра

Повторный запуск скрипта — если правила найдены, предлагается действие «удалить».

### Ограничения

- `zimbraMailAdminSieveScriptBefore` помечен устаревшим начиная с Zimbra 8.7.8; в актуальных версиях Carbonio CE 26.x атрибут принимается LDAP, но поведение при доставке следует проверить
- Фильтр работает только для **входящей** почты (delivery-time sieve), не применяется к уже полученным письмам
- Тег-цвет применяется к письму навсегда (пока тег не снят вручную или фильтром пользователя)

---

## English

A patch for **Carbonio CE** (Zextras) that adds two new features to the mail interface:

1. **"Create Filter"** — a context menu and toolbar item that opens the filter creation dialog pre-filled with the sender's address
2. **"Highlight with color"** — a new action in the filter editor that highlights matching messages with a color tint in the message list

### Features

#### Create Filter

Right-click on a message (or use the ⋮ button in the preview panel) → **"Create Filter"**.

The standard filter creation dialog opens pre-filled:

- **Name**: "Emails from user@domain.com"
- **Condition**: "From" → exact match → sender's address
- **Action**: Move to folder
- **Active**: enabled

After clicking "Create", the filter is saved and a confirmation dialog appears:

> "Apply the conditions of the created filter to previously received messages?"

- **No** → "Filter created" snackbar
- **Yes** → standard Apply-filter dialog with Inbox pre-selected and real message count

#### Highlight with color

In the filter editor (Settings → Filters), the action list gains a new entry: **"Highlight with color"**.

When selected, a 10-color palette appears. Messages matching the filter condition are highlighted with a semi-transparent background in the message list:

| Color | | Color | |
|-------|---|-------|---|
| Red | 🔴 | Blue | 🔵 |
| Orange | 🟠 | Purple | 🟣 |
| Yellow | 🟡 | Pink | 🌸 |
| Green | 🟢 | Brown | 🟤 |
| Cyan | 💠 | Gray | ⚪ |

The color is stored as a tag named after the color ("Красный", "Синий", etc.). Color tags:
- appear in the tag panel with a matching Zimbra color dot
- do **not** show a tag icon on message rows (the row highlight is already informative enough)

To remove highlighting — delete or disable the filter, then untag the affected messages.

#### Bugfix: disabling an unconditional filter

A filter with **no condition** (e.g. forward-all — only a `redirect` action) **cannot be disabled** in stock Carbonio CE: you un-check "Active filter" → Save → reopen, and it's checked again.

The cause is in the Carbonio **backend**, not the UI: a rule is deactivated by wrapping it in Sieve `disabled_if <condition> { ... }`. With no condition there is nothing to wrap, so `GetFilterRules` always returns `active:true`.

The patch represents a "disabled unconditional filter" via a hidden `trueTest` (Sieve `true` — matches every message, identical behaviour for forward-all): `disabled_if true { redirect ...; stop; }`. A `__cuFilterFix` helper injects `trueTest` on save (through `ModifyFilterRules`/`ModifyOutgoingFilterRules`), and the condition builder hides `trueTest` from the UI so the filter still shows with no condition rows (no phantom "subject contains…").

### Languages

The web UI auto-detects language from user settings.

- **English**: built-in as `t("key", "English fallback")` default values; `en.json` is patched on install
- **Russian**: translations are added to `ru.json` automatically during install

### Requirements

| | |
|---|---|
| Carbonio CE | ≥ 26.x |
| Ubuntu | 22.04 (Jammy) or 24.04 (Noble) |
| Python | 3.6+ |
| carbonio-mails-ui | **1.31.7** (hash `21dee67f…`) |

### Installation

One-liner:

```bash
curl -fsSL https://raw.githubusercontent.com/mapazzzm/carbonio-ce-filter-dialog/main/install.py | sudo python3
```

Or clone the repository:

```bash
git clone https://github.com/mapazzzm/carbonio-ce-filter-dialog.git
cd carbonio-ce-filter-dialog
python3 install.py
```

After installation, hard-refresh the browser: **Ctrl+Shift+R**

### Check

```bash
python3 install.py check
```

Or without cloning:

```bash
curl -fsSL https://raw.githubusercontent.com/mapazzzm/carbonio-ce-filter-dialog/main/install.py | sudo python3 - check
```

### Rollback

```bash
python3 install.py rollback
```

The script automatically backs up the original files before each patch.

### After `apt upgrade carbonio-mails-ui`

Upgrading the package overwrites the JS files — re-apply the patch:

```bash
python3 install.py check || python3 install.py
```

Or without cloning:

```bash
curl -fsSL https://raw.githubusercontent.com/mapazzzm/carbonio-ce-filter-dialog/main/install.py | sudo python3 - check || \
curl -fsSL https://raw.githubusercontent.com/mapazzzm/carbonio-ce-filter-dialog/main/install.py | sudo python3
```

The script supports **incremental upgrades**: if a previous version is already installed, only the missing pieces are applied.

### How it works

The script makes surgical replacements in four minified JS files and two JSON locale files:

**JS files:**

| File | Changes |
|------|---------|
| `388.*.chunk.js` | Adds webpack module 9999 and "Create Filter" item to the preview toolbar |
| `336.*.chunk.js` | Adds module 9999 and item to context menu; adds message row highlight and hides color tag icon |
| `mail-setting-view.*.chunk.js` | Exports dialog components (Ae, Jy); adds "Highlight with color" action with color picker; creates tags via SOAP API; injects the `__cuFilterFix` helper (`trueTest`) so unconditional filters can be disabled |
| `folder-panel-view.*.chunk.js` | Adds conversation row highlight (conversation view) |
| `917.*.chunk.js` | Fixes `i.tags is not iterable` in optimistic tag update for messages with no prior tags |

**Locale files:**

| File | Keys added |
|------|-----------|
| `i18n/ru.json` | `action.apply_filter_confirm`, `modals.apply_filters.*`, `label.yes/no`, `settings.set_color`, `settings.set_color_placeholder` |
| `i18n/en.json` | `label.yes/no`, `settings.set_color`, `settings.set_color_placeholder` |

No external dependencies — all React components and the Carbonio Design System are already loaded by the application.

### Changelog

**Bugfix: disabling an unconditional filter** *(current version)*
Added a `mail-setting-view.*.chunk.js` patch that lets you deactivate a filter with no condition (forward-all). The bug is in the Carbonio backend (`disabled_if` needs a condition); the fix represents the disabled state via a hidden `trueTest`. Installed/checked/rolled back independently of the other features (marker `__cuFilterFix`).

**Added "Highlight with color"** + **Fix `i.tags is not iterable`**
Integrated color-based message highlighting: new action in the filter editor, support in message list and conversation list, full ru/en localization.

Also fixed a Carbonio bug in `917.*.chunk.js`: `optimisticallyHandleMessageActions` threw `TypeError: i.tags is not iterable` when tagging a message that had no prior tags (`i.tags === undefined`). Fix: added `i.tags||[]` fallback in both TAG and UNTAG branches.

**Scrollbar fix in context menu**
The Carbonio Design System `Dropdown` component has a default `maxHeight: 50vh`. After adding the "Create Filter" item the right-click menu exceeded this limit and showed a scrollbar. Fix: `maxHeight:"100vh"` is now passed to both context menu Dropdown instances in `336.*.chunk.js`.

---

## domain_color_filter.py

A standalone script for managing **domain-level** color tagging of incoming messages — no JS patching required.

### How it works

Uses `zimbraMailAdminSieveScriptBefore` — an administrative sieve script that Carbonio/Zimbra applies to incoming messages **before** any user filters. The script is set at the domain level, is **not visible to users**, and does not conflict with their personal filters.

When the filter matches, a color tag ("Красный", "Зелёный", etc.) is added to the message. If the `install.py` patch from this repository is also installed, those tags visually highlight the message row with a colored background in the UI.

### Features

- Interactively prompts for target domain, sender domain and color
- Detects whether a matching filter already exists
- On re-run: offers to add another rule or delete an existing one
- Supports multiple rules on the same domain

### Usage

```bash
python3 domain_color_filter.py
```

Run as `root` on the Carbonio server. The script calls `su - zextras -c "zmprov ..."` internally.

### Example session

```
Домен Carbonio (для которого применяем): example.com
Получаю текущий zimbraMailAdminSieveScriptBefore для example.com...
  domain-color-filter правил не найдено.

Домен-отправитель (условие «from» contains): external.com

Доступные цвета / Available colors:
   1. Красный (Red)
   2. Оранжевый (Orange)
   3. Жёлтый (Yellow)
   4. Зелёный (Green)
   5. Бирюзовый (Cyan)
   6. Синий (Blue)
   7. Фиолетовый (Purple)
   8. Розовый (Pink)
   9. Коричневый (Brown)
  10. Серый (Gray)
Номер цвета / Color number: 4

Будет применено / Will apply:
  Домен / Domain:          example.com
  От домена / From domain: external.com
  Цвет / Color:            Зелёный (Green)
  Фильтр не виден пользователям / Not visible to users (zimbraMailAdminSieveScriptBefore)
Применить? / Apply? [ДА/нет]: да

✓ Правило применено для example.com.
  Письма от *@external.com будут помечены тегом «Зелёный» (Green).

Для удаления запустите скрипт повторно и выберите «удалить».
To remove: re-run the script and choose «удалить».
```

### Removing a filter

Re-run the script — if rules are found, the "delete" action is offered.

### Limitations

- `zimbraMailAdminSieveScriptBefore` has been deprecated since Zimbra 8.7.8; in current Carbonio CE 26.x the attribute is accepted by LDAP, but delivery-time behavior should be verified
- The filter applies to **incoming** mail only (delivery-time sieve); already-received messages are not affected
- The color tag is permanent on the message until removed manually or by a user filter
