#!/usr/bin/env python3
"""
domain_color_filter.py — управление цветовым выделением писем на уровне домена Carbonio CE.

Устанавливает фильтр zimbraMailAdminSieveScriptBefore для всего домена.
Фильтр применяется ко всем входящим письмам домена, пользователям не виден.

Использование:
    python3 domain_color_filter.py
"""
import subprocess
import re
import sys

COLORS = [
    ("Красный",     "red"),
    ("Оранжевый",   "orange"),
    ("Жёлтый",      "yellow"),
    ("Зелёный",     "green"),
    ("Бирюзовый",   "cyan"),
    ("Синий",       "blue"),
    ("Фиолетовый",  "purple"),
    ("Розовый",     "pink"),
    ("Коричневый",  "brown"),
    ("Серый",       "gray"),
]

REQUIRE = ('require ["fileinto", "copy", "reject", "tag", "flag", "variables", '
           '"log", "enotify", "envelope", "body", "ereject", "reject", '
           '"relational", "comparator-i;ascii-numeric"];')

RULE_COMMENT_PREFIX = "# domain-color-filter:"


def zmprov(*args):
    cmd = ["su", "-", "zextras", "-c", " ".join(f"'{a}'" if " " in a else a for a in args)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def get_current_script(domain):
    out, err, rc = zmprov("zmprov", "gd", domain, "zimbraMailAdminSieveScriptBefore")
    if rc != 0:
        return None, err
    script = ""
    in_attr = False
    for line in out.splitlines():
        if line.startswith("zimbraMailAdminSieveScriptBefore:"):
            script = line[len("zimbraMailAdminSieveScriptBefore:"):].lstrip()
            in_attr = True
        elif in_attr:
            if line.startswith(" "):
                script += "\n" + line.strip()
            else:
                break
    return script.strip(), None


def set_script(domain, script):
    import tempfile, os
    shfile = f"/tmp/dcf_{domain.replace('.', '_')}.sh"
    valfile = f"/tmp/dcf_{domain.replace('.', '_')}_val.txt"
    with open(shfile, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write(f"cat > {valfile} << 'SIEVEEOF'\n")
        f.write(script.rstrip() + "\n")
        f.write("SIEVEEOF\n")
        f.write(f"zmprov md '{domain}' zimbraMailAdminSieveScriptBefore \"$(cat {valfile})\"\n")
        f.write(f"rm -f {valfile}\n")
    r = subprocess.run(["su", "-", "zextras", "-c", f"bash {shfile}"],
                       capture_output=True, text=True)
    os.unlink(shfile)
    return r.returncode, r.stderr.strip()


def make_rule(from_domain, color_ru):
    comment = f"{RULE_COMMENT_PREFIX} {from_domain} → {color_ru}"
    rule = (
        f"{comment}\n"
        f'if anyof (address :domain :contains :comparator "i;ascii-casemap" ["from"] "{from_domain}") {{\n'
        f'    tag "{color_ru}";\n'
        f'}}'
    )
    return comment, rule


def parse_existing_rules(script):
    """Найти все domain-color-filter правила в скрипте."""
    rules = []
    lines = script.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(RULE_COMMENT_PREFIX):
            block = [line]
            j = i + 1
            depth = 0
            while j < len(lines):
                block.append(lines[j])
                depth += lines[j].count("{") - lines[j].count("}")
                j += 1
                if depth <= 0 and len(block) > 1:
                    break
            rules.append((line, "\n".join(block), i))
            i = j
        else:
            i += 1
    return rules


def remove_rule(script, comment_line):
    """Удалить правило с указанным комментарием."""
    lines = script.split("\n")
    result = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == comment_line.strip():
            depth = 0
            i += 1
            while i < len(lines):
                depth += lines[i].count("{") - lines[i].count("}")
                i += 1
                if depth <= 0:
                    break
            # Убрать лишнюю пустую строку после правила
            while result and result[-1] == "":
                result.pop()
        else:
            result.append(lines[i])
            i += 1
    return "\n".join(result).strip()


def add_rule(script, rule):
    """Добавить правило к скрипту."""
    if not script or not script.strip():
        return REQUIRE + "\n\n" + rule
    if REQUIRE not in script:
        return REQUIRE + "\n\n" + script + "\n\n" + rule
    return script.rstrip() + "\n\n" + rule


def ask(prompt, options=None, default=None):
    while True:
        if options:
            display = "/".join(
                o.upper() if o == default else o for o in options
            )
            ans = input(f"{prompt} [{display}]: ").strip().lower()
            if not ans and default:
                return default
            if ans in options:
                return ans
        else:
            ans = input(f"{prompt}: ").strip()
            if ans:
                return ans
        print("  Пожалуйста, введите корректное значение.")


def main():
    print("=" * 55)
    print("  Цветовое выделение писем — уровень домена")
    print("  Carbonio CE / zimbraMailAdminSieveScriptBefore")
    print("=" * 55)
    print()

    # 1. Домен получателей
    target_domain = ask("Домен Carbonio (для которого применяем)").strip().lower()
    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", target_domain):
        print("Ошибка: некорректный домен.")
        sys.exit(1)

    # 2. Получить текущий скрипт
    print(f"\nПолучаю текущий zimbraMailAdminSieveScriptBefore для {target_domain}...")
    script, err = get_current_script(target_domain)
    if script is None:
        print(f"Ошибка: {err}")
        sys.exit(1)

    # 3. Показать существующие domain-color-filter правила
    existing = parse_existing_rules(script)
    if existing:
        print(f"\nНайдено domain-color-filter правил: {len(existing)}")
        for idx, (comment, block, _) in enumerate(existing, 1):
            print(f"  {idx}. {comment[len(RULE_COMMENT_PREFIX):].strip()}")

        action = ask(
            "\nДействие",
            options=["добавить", "удалить", "выход"],
            default="добавить",
        )
        if action == "выход":
            print("Выход.")
            sys.exit(0)
        if action == "удалить":
            if len(existing) == 1:
                to_delete = existing[0]
            else:
                n = ask(f"Номер правила для удаления (1–{len(existing)})")
                try:
                    to_delete = existing[int(n) - 1]
                except (ValueError, IndexError):
                    print("Некорректный номер.")
                    sys.exit(1)
            comment_line, _, _ = to_delete
            new_script = remove_rule(script, comment_line)
            print(f"\nУдаляю: {comment_line[len(RULE_COMMENT_PREFIX):].strip()}")
            rc, err = set_script(target_domain, new_script)
            if rc == 0:
                print("✓ Правило удалено.")
            else:
                print(f"✗ Ошибка: {err}")
            sys.exit(0)
        # action == "добавить" — продолжаем
    else:
        print("  domain-color-filter правил не найдено.\n")

    # 4. Домен-источник
    from_domain = ask("Домен-отправитель (условие «from» contains)").strip().lower()
    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", from_domain):
        print("Ошибка: некорректный домен.")
        sys.exit(1)

    # 5. Цвет
    print("\nДоступные цвета:")
    for i, (name_ru, name_en) in enumerate(COLORS, 1):
        print(f"  {i:2d}. {name_ru}")
    color_n = ask("Номер цвета")
    try:
        color_ru, _ = COLORS[int(color_n) - 1]
    except (ValueError, IndexError):
        print("Некорректный номер цвета.")
        sys.exit(1)

    # 6. Проверить — не существует ли уже такое правило
    comment_line, rule = make_rule(from_domain, color_ru)
    for c, _, _ in existing:
        if from_domain in c and color_ru in c:
            print(f"\nТакое правило уже существует: {c}")
            sys.exit(0)

    # 7. Подтверждение
    print(f"\nБудет применено:")
    print(f"  Домен:      {target_domain}")
    print(f"  От домена:  {from_domain}")
    print(f"  Цвет:       {color_ru}")
    print(f"  Фильтр не виден пользователям (zimbraMailAdminSieveScriptBefore)")
    confirm = ask("Применить?", options=["да", "нет"], default="да")
    if confirm != "да":
        print("Отменено.")
        sys.exit(0)

    # 8. Применить
    new_script = add_rule(script, rule)
    rc, err = set_script(target_domain, new_script)
    if rc == 0:
        print(f"\n✓ Правило применено для {target_domain}.")
        print(f"  Письма от *@{from_domain} будут помечены тегом «{color_ru}».")
        print(f"\nДля удаления запустите скрипт повторно и выберите «удалить».")
    else:
        print(f"\n✗ Ошибка при записи: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
