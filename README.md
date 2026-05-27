# carbonio-ce-filter-dialog

[🇷🇺 Русский](#русский) | [EN English](#english)

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
| Жёлтый | 🟡 | Розовый | 🩷 |
| Зелёный | 🟢 | Коричневый | 🟤 |
| Бирюзовый | 🩵 | Серый | ⚪ |

Цвет хранится как тег с именем цвета («Красный», «Синий» и т. д.). Теги с цветами:
- видны в панели тегов с соответствующим цветным кружком Zimbra
- **не** показывают иконку тега на строках писем (подсветка строки достаточно информативна)

Чтобы убрать подсветку — удалить или отключить фильтр, затем снять тег с писем.

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
| `mail-setting-view.*.chunk.js` | Экспортирует компоненты диалогов (Ae, Jy); добавляет действие «Выделять цветом» с палитрой цветов; создаёт теги через SOAP API |
| `folder-panel-view.*.chunk.js` | Добавляет подсветку строк бесед (conversation view) |

**Файлы локализации:**

| Файл | Добавляемые ключи |
|------|-------------------|
| `i18n/ru.json` | `action.apply_filter_confirm`, `modals.apply_filters.*`, `label.yes/no`, `settings.set_color`, `settings.set_color_placeholder` |
| `i18n/en.json` | `label.yes/no`, `settings.set_color`, `settings.set_color_placeholder` |

Никаких внешних зависимостей — все React-компоненты и Carbonio Design System уже загружены приложением.

### История изменений

**Добавлено «Выделять цветом»** *(текущая версия)*
Интегрирована функция подсветки писем цветом: новое действие в редакторе фильтров, поддержка в списке сообщений и бесед, полная локализация ru/en.

**Фикс скроллбара в контекстном меню**
Компонент `Dropdown` из Carbonio Design System имеет дефолтный `maxHeight: 50vh`. После добавления пункта «Создать фильтр» список пунктов правого клика превышал этот лимит и появлялась полоса прокрутки. Фикс: добавлен `maxHeight:"100vh"` в оба Dropdown контекстного меню в `336.*.chunk.js`.

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
| Yellow | 🟡 | Pink | 🩷 |
| Green | 🟢 | Brown | 🟤 |
| Cyan | 🩵 | Gray | ⚪ |

The color is stored as a tag named after the color ("Красный", "Синий", etc.). Color tags:
- appear in the tag panel with a matching Zimbra color dot
- do **not** show a tag icon on message rows (the row highlight is already informative enough)

To remove highlighting — delete or disable the filter, then untag the affected messages.

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
| `mail-setting-view.*.chunk.js` | Exports dialog components (Ae, Jy); adds "Highlight with color" action with color picker; creates tags via SOAP API |
| `folder-panel-view.*.chunk.js` | Adds conversation row highlight (conversation view) |

**Locale files:**

| File | Keys added |
|------|-----------|
| `i18n/ru.json` | `action.apply_filter_confirm`, `modals.apply_filters.*`, `label.yes/no`, `settings.set_color`, `settings.set_color_placeholder` |
| `i18n/en.json` | `label.yes/no`, `settings.set_color`, `settings.set_color_placeholder` |

No external dependencies — all React components and the Carbonio Design System are already loaded by the application.

### Changelog

**Added "Highlight with color"** *(current version)*
Integrated color-based message highlighting: new action in the filter editor, support in message list and conversation list, full ru/en localization.

**Scrollbar fix in context menu**
The Carbonio Design System `Dropdown` component has a default `maxHeight: 50vh`. After adding the "Create Filter" item the right-click menu exceeded this limit and showed a scrollbar. Fix: `maxHeight:"100vh"` is now passed to both context menu Dropdown instances in `336.*.chunk.js`.
