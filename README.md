# carbonio-ce-filter-dialog

Патч для **Carbonio CE** (Zextras): добавляет пункт **«Создать фильтр»** в контекстное меню письма и диалог применения фильтра к уже полученным письмам.

Patch for **Carbonio CE** (Zextras): adds a **"Create Filter"** item to the message context menu and a confirmation dialog to apply the filter to existing messages.

---

## Что делает / What it does

При нажатии правой кнопкой мыши на письмо (или через кнопку «⋮» в превью) появляется пункт **«Создать фильтр»**.

Right-click on a message (or use the ⋮ button in the preview panel) to get **"Create Filter"**.

### Диалог создания / Create dialog

Открывается стандартный диалог фильтров с предзаполненными полями:

- **Название**: «Обработка писем от user@domain.com» / "Emails from user@domain.com"
- **Условие**: «От кого» → точное совпадение → адрес отправителя
- **Действие**: Переместить в папку
- **Активный**: включён

The standard filter dialog opens pre-filled with the sender's address as an exact-match "From" condition.

### Диалог подтверждения / Confirmation dialog

После нажатия «Создать» фильтр сохраняется и появляется диалог:

> «Применить условия созданного фильтра для ранее полученных писем?»

- **Нет** → снекбар «Фильтр создан»
- **Да** → стандартный Apply-диалог с предвыбранной папкой Входящие и реальным счётчиком писем

After saving the filter, a confirmation dialog appears:

> "Apply the conditions of the created filter to previously received messages?"

- **No** → "Filter created" snackbar
- **Yes** → standard Apply-filter dialog with Inbox pre-selected and real message count

---

## Языки / Languages

Веб-интерфейс автоматически определяет язык из настроек браузера.
- **Русский**: переводы добавляются в `ru.json` автоматически при установке
- **Английский**: встроен в код как значения по умолчанию, дополнительных файлов не требует

The web UI auto-detects language from browser settings.
- **Russian**: translations are added to `ru.json` automatically during install
- **English**: built-in as default values, no additional files needed

---

## Требования / Requirements

| | |
|---|---|
| Carbonio CE | ≥ 26.x |
| Ubuntu | 22.04 (Jammy) или 24.04 (Noble) |
| Python | 3.6+ |
| carbonio-mails-ui | **1.31.7** (commit `21dee67f…`) |

> Скрипт проверяет версию перед установкой.
> The script verifies the version before patching.

---

## Установка / Installation

```bash
git clone https://github.com/mapazzzm/carbonio-ce-filter-dialog.git
cd carbonio-ce-filter-dialog
python3 install.py
```

После установки обновите страницу в браузере: **Ctrl+Shift+R**

After installation, hard-refresh the browser: **Ctrl+Shift+R**

## Проверка / Check

```bash
python3 install.py check
```

## Откат / Rollback

```bash
python3 install.py rollback
```

Перед каждой установкой скрипт автоматически сохраняет бэкап оригинальных файлов.

The script automatically backs up the original files before each patch.

---

## После обновления пакета / After package upgrade

`apt upgrade carbonio-mails-ui` перезаписывает JS-файлы — патч нужно переприменить:

`apt upgrade carbonio-mails-ui` overwrites the JS files — re-apply the patch:

```bash
python3 install.py check || python3 install.py
```

---

## Как это работает / How it works

Скрипт вносит точечные изменения в три минифицированных JS-файла пакета `carbonio-mails-ui`:

- `388.*.chunk.js` — добавляет webpack-модуль 9999 и пункт в тулбар превью
- `336.*.chunk.js` — добавляет тот же модуль и пункт в контекстное меню
- `mail-setting-view.*.chunk.js` — экспортирует внутренние компоненты диалогов (Ae, Jy) и добавляет поддержку предвыбора папки

А также добавляет ключи переводов в `i18n/ru.json`.

The script makes surgical replacements in three minified JS files of the `carbonio-mails-ui` package, and adds translation keys to `i18n/ru.json`. No external dependencies — all React components and the Carbonio Design System are already loaded by the application.
