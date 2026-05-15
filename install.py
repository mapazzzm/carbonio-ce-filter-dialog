#!/usr/bin/env python3
"""
carbonio-create-filter — installer
Adds "Create Filter" / "Создать фильтр":
  1. Preview toolbar (⋮ → More actions)     — chunk 388, module 1197
  2. Right-click context menu on message    — chunk 336, module 8264
  3. Exports Ae and Jy from module 3475     — mail-setting-view chunk
  4. After filter is saved — confirmation dialog:
       Yes → standard Apply-filter dialog with Inbox pre-selected and real count
       No  → "Filter created" snackbar
  5. Patches ru.json with Russian translations

Usage:
    python3 install.py          — apply patch
    python3 install.py check    — check if patch is applied
    python3 install.py rollback — restore from backup
"""

import sys
import os
import json
import shutil
import glob
import time

MAILS_UI_BASE = "/opt/zextras/web/iris/carbonio-mails-ui"

# Markers to detect if patch is already applied (one per chunk)
PATCH_MARKER_388      = "9999:(e,t,a)=>"   # module 9999 definition in chunk 388
PATCH_MARKER_336      = "CF=a(9999)"        # CF import in module 8264 of chunk 336
PATCH_MARKER_SETTINGS = "useState)(initFld)" # active=true when iEmail provided (S4) + S6b
PATCH_MARKER_S7       = "N.VN)({folderName:g.name})"  # S7: translated folder name in chip

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _find_version_dirs():
    dirs = [d for d in glob.glob(os.path.join(MAILS_UI_BASE, "*"))
            if os.path.isdir(d) and "current" not in d and "i18n" not in d]
    if not dirs:
        die("Не найден каталог carbonio-mails-ui")
    dirs.sort(key=lambda d: os.path.getmtime(d), reverse=True)
    return dirs

def find_chunk_388():
    for d in _find_version_dirs():
        chunks = glob.glob(os.path.join(d, "388.*.chunk.js"))
        if chunks:
            return chunks[0]
    die("Не найден chunk 388.*.chunk.js в " + MAILS_UI_BASE)

def find_chunk_336():
    for d in _find_version_dirs():
        chunks = glob.glob(os.path.join(d, "336.*.chunk.js"))
        if chunks:
            return chunks[0]
    die("Не найден chunk 336.*.chunk.js в " + MAILS_UI_BASE)

def find_chunk_settings():
    for d in _find_version_dirs():
        chunks = glob.glob(os.path.join(d, "mail-setting-view.*.chunk.js"))
        if chunks:
            return chunks[0]
    die("Не найден mail-setting-view.*.chunk.js в " + MAILS_UI_BASE)

def die(msg):
    print("ОШИБКА:", msg, file=sys.stderr)
    sys.exit(1)

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def backup(path):
    ts = time.strftime("%Y%m%d%H%M%S")
    dst = path + ".bak." + ts
    shutil.copy2(path, dst)
    print(f"  Бэкап: {dst}")
    return dst

# ─────────────────────────────────────────────────────────────────────────────
# ru.json patching
# ─────────────────────────────────────────────────────────────────────────────

RU_JSON_PATH = os.path.join(MAILS_UI_BASE, "i18n", "ru.json")

RU_KEYS = {
    # Confirmation dialog body text
    ("action", "apply_filter_confirm"):
        "Применить условия созданного фильтра для ранее полученных писем?",
    # "N messages will be processed" — Russian plural forms (i18next)
    ("modals", "apply_filters", "apply_folder_one"):
        "<bold>{{count}} письмо</bold> будет обработано в выбранной папке.",
    ("modals", "apply_filters", "apply_folder_few"):
        "<bold>{{count}} письма</bold> будет обработано в выбранной папке.",
    ("modals", "apply_filters", "apply_folder_many"):
        "<bold>{{count}} писем</bold> будет обработано в выбранной папке.",
    ("modals", "apply_filters", "apply_folder_other"):
        "<bold>{{count}} сообщение</bold> будет обработано в выбранной папке.",
}

def _get_nested(d, keys):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d

def _set_nested(d, keys, value):
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value

def cmd_patch_ru_json():
    if not os.path.exists(RU_JSON_PATH):
        print(f"  ru.json: не найден по пути {RU_JSON_PATH}, пропускаем")
        return False
    with open(RU_JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    missing = {k: v for k, v in RU_KEYS.items() if _get_nested(data, k) != v}
    if not missing:
        print("  ru.json: все ключи уже на месте, пропускаем.")
        return False
    ts = time.strftime("%Y%m%d%H%M%S")
    bak = RU_JSON_PATH + ".bak." + ts
    shutil.copy2(RU_JSON_PATH, bak)
    print(f"  Бэкап: {bak}")
    for keys, value in missing.items():
        _set_nested(data, keys, value)
        print(f"  ✓ добавлен: {'.'.join(keys)}")
    with open(RU_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print("  ✓ ru.json обновлён")
    return True

def cmd_check_ru_json():
    if not os.path.exists(RU_JSON_PATH):
        print(f"  {'✗'}  ru.json: не найден")
        return False
    with open(RU_JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    ok = all(_get_nested(data, k) == v for k, v in RU_KEYS.items())
    print(f"  {'✓' if ok else '✗'}  ru.json: {'все ключи на месте' if ok else 'требует обновления'}")
    return ok

def cmd_rollback_ru_json():
    backups = sorted(glob.glob(RU_JSON_PATH + ".bak.*"), reverse=True)
    if not backups:
        print(f"  ru.json: бэкап не найден, пропускаем")
        return
    latest = backups[0]
    print(f"  ru.json: восстанавливаем из {latest}")
    shutil.copy2(latest, RU_JSON_PATH)
    print("  ru.json: ✓ восстановлено")

# ─────────────────────────────────────────────────────────────────────────────
# The new webpack module (module 9999)
# After filter is created, shows confirmation dialog "Apply to existing mails?":
#   Нет → shows "Filter created" snackbar
#   Да  → opens the standard Apply filter dialog (Jy component from chunk 949)
#          with Inbox folder pre-selected
# ─────────────────────────────────────────────────────────────────────────────

NEW_MODULE = r""",9999:(e,t,a)=>{a.d(t,{q:()=>H});var n=a(7559),s=a(8153),d=a(7625),i=a(4702);function findFolder(root,id){if(!root)return null;var arr=Array.isArray(root)?root:[root];for(var fi=0;fi<arr.length;fi++){var f=arr[fi];if(String(f.id)===String(id))return f;var found=findFolder(f.folder,id);if(found)return found;}return null;}async function soapCall(m,b){try{var res=await fetch("/service/soap/"+m+"Request",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({Header:{context:{_jsns:"urn:zimbra",format:{type:"js"}}},Body:{[m+"Request"]:b}})});var data=await res.json();return data?.Body?.[m+"Response"];}catch(ex){return null;}}function H(message){var uu=(0,d.m)();var createModal=uu.createModal,closeModal=uu.closeModal,createSnackbar=uu.createSnackbar;var tt=(0,s.useTranslation)(),t=tt[0];var sender=n.useMemo(function(){return message&&message.participants&&message.participants.find(function(p){return p.type==="f";});},[message]);var senderEmail=(sender&&(sender.address||sender.email))||"";n.useEffect(function(){Promise.all([a.e(237),a.e(654),a.e(486),a.e(471),a.e(169),a.e(949)]).catch(function(){});},[]);var canExecute=n.useCallback(function(){return!!senderEmail;},[senderEmail]);var execute=n.useCallback(function(){if(!canExecute())return;var id="create-filter-"+Date.now();var close=function(){closeModal(id);};Promise.all([a.e(237),a.e(654),a.e(486),a.e(471),a.e(169),a.e(949)]).then(function(){var AeComp=a(3475).Ae;if(!AeComp){createSnackbar&&createSnackbar({key:"cf-load-err",severity:"error",label:t("label.error_try_again","Something went wrong, please try again"),hideButton:true});return;}createModal({id:id,size:"large",onClose:close,children:n.createElement(AeComp,{onClose:close,isIncoming:true,initialFromEmail:senderEmail,initialFilterName:t("settings.filter_name_prefix","Emails from ")+senderEmail,onConfirm:function(filter){var filterName=filter.name;soapCall("GetFilterRules",{_jsns:"urn:zimbraMail"}).then(function(gr){var existing=(gr&&gr.filterRules&&gr.filterRules[0]&&gr.filterRules[0].filterRule)||[];var combined=existing.concat([filter]);return soapCall("ModifyFilterRules",{_jsns:"urn:zimbraMail",filterRules:[{filterRule:combined}]});}).then(function(){close();var confirmId="cf-confirm-"+Date.now();var closeConfirm=function(){closeModal(confirmId);};var handleNo=function(){closeConfirm();if(createSnackbar)createSnackbar({key:"cf-ok",severity:"info",label:t("settings.filter_created","Filter created"),hideButton:true,autoHideTimeout:3000});};var handleYes=function(){closeConfirm();Promise.all([a.e(237),a.e(654),a.e(486),a.e(471),a.e(169),a.e(949)]).then(function(){var Jy=a(3475).Jy;if(!Jy){handleNo();return;}return soapCall("GetFolder",{_jsns:"urn:zimbraMail",folder:{id:"2"}}).then(function(fr){var raw=findFolder(fr&&fr.folder,"2");var inbox=raw?{id:raw.id||"2",name:raw.name||"Inbox",absFolderPath:raw.absPath||raw.absFolderPath||"/Inbox",n:raw.n||0}:{id:"2",absFolderPath:"/Inbox",name:"Inbox",n:0};var applyId="cf-apply-"+Date.now();var closeApply=function(){closeModal(applyId);};createModal({id:applyId,size:"medium",onClose:closeApply,children:n.createElement(i.ModalManager,null,n.createElement(Jy,{criteria:{filterName:filterName},initialFolder:inbox,onClose:closeApply}))},true);});}).catch(function(){handleNo();});};createModal({id:confirmId,size:"small",onClose:handleNo,children:n.createElement(i.Container,null,n.createElement(i.ModalHeader,{onClose:handleNo,title:t("settings.filter_created","Filter created"),showCloseIcon:true}),n.createElement(i.Divider,null),n.createElement(i.Container,{padding:{all:"large"},mainAlignment:"flex-start",crossAlignment:"flex-start"},n.createElement(i.Text,{overflow:"break-word"},t("action.apply_filter_confirm","Apply the conditions of the created filter to previously received messages?"))),n.createElement(i.Divider,null),n.createElement(i.ModalFooter,{confirmLabel:t("label.yes","Yes"),onConfirm:handleYes,secondaryActionLabel:t("label.no","No"),onSecondaryAction:handleNo,onClose:handleNo}))},true);}).catch(function(){if(createSnackbar)createSnackbar({key:"cf-err",severity:"error",label:t("label.error_try_again","Something went wrong, please try again"),hideButton:true});});}})},true);}).catch(function(){if(createSnackbar)createSnackbar({key:"cf-load-err",severity:"error",label:t("label.error_try_again","Something went wrong, please try again"),hideButton:true});});},[canExecute,createModal,closeModal,createSnackbar,t,senderEmail]);return n.useMemo(function(){return{id:"message-create-filter",icon:"FunnelOutline",label:t("action.create_filter_from_sender","Create Filter"),execute:execute,canExecute:canExecute};},[execute,canExecute,t]);}"""

# ─────────────────────────────────────────────────────────────────────────────
# Patches for chunk 949 / mail-setting-view (module 3475)
# Exports Ae and Jy, adds initialFromEmail / initialFilterName props to Ae,
# adds initialFolder prop to j (Apply filter dialog, pre-selects Inbox).
# ─────────────────────────────────────────────────────────────────────────────

def build_patches_settings():
    # S1. Export Ae and Jy from module 3475
    patchS1_old = "a.r(t),a.d(t,{default:()=>yt})"
    patchS1_new = "a.r(t),a.d(t,{default:()=>yt,Ae:()=>Ae,Jy:()=>j})"

    # S2. Add initialFromEmail and initialFilterName props; use initialFilterName as default name
    patchS2_old = 'Ae=({onClose:e,onConfirm:t,isIncoming:a})=>{const[d]=(0,c.useTranslation)(),[m,u]=(0,n.useState)("")'
    patchS2_new = 'Ae=({onClose:e,onConfirm:t,isIncoming:a,initialFromEmail:iEmail,initialFilterName:iName})=>{const[d]=(0,c.useTranslation)(),[m,u]=(0,n.useState)(iName||"")'

    # S3. Pre-fill From condition with exact match ("is") in initial state when initialFromEmail is provided
    patchS3_old = '[S,w]=(0,n.useState)([{filterActions:[{actionKeep:[{}],actionStop:[{}]}],active:g,name:m,key:"subject",label:"Subject",filterTests:[{}],index:0,comp:l().createElement(oe,{t:d,activeIndex:0})}])'
    patchS3_new = '[S,w]=(0,n.useState)(iEmail?[{filterActions:[{actionKeep:[{}],actionStop:[{}]}],active:g,name:m,key:"from",label:"From",filterTests:[{condition:f,addressTest:[{header:"from",part:"all",stringComparison:"is",value:iEmail}]}],index:0,comp:l().createElement(ye,{t:d,activeIndex:0,defaultValue:{addressTest:[{header:"from",part:"all",stringComparison:"is",value:iEmail}]}})}]:[{filterActions:[{actionKeep:[{}],actionStop:[{}]}],active:g,name:m,key:"subject",label:"Subject",filterTests:[{}],index:0,comp:l().createElement(oe,{t:d,activeIndex:0})}])'

    # S4. Active checkbox = true by default when creating from a message (iEmail provided)
    patchS4_old = '[g,b]=(0,n.useState)(!1),[f,h]=(0,n.useState)("anyof")'
    patchS4_new = '[g,b]=(0,n.useState)(iEmail?!0:!1),[f,h]=(0,n.useState)("anyof")'

    # S5. Default action = "Move to folder" when creating from a message (iEmail provided)
    patchS5_old = '[E,C]=(0,n.useState)([{actionKeep:[{}],id:(0,L.A)()}])'
    patchS5_new = '[E,C]=(0,n.useState)(iEmail?[{actionFileInto:[{folderPath:""}],id:(0,L.A)()}]:[{actionKeep:[{}],id:(0,L.A)()}])'

    # S6a. Add initialFolder prop to j (Apply filter dialog)
    patchS6a_old = 'const j=({criteria:e,onClose:t})=>'
    patchS6a_new = 'const j=({criteria:e,onClose:t,initialFolder:initFld})=>'

    # S6b. Pre-select initialFolder in useState (Inbox when called from create-filter)
    patchS6b_old = '[g,b]=(0,n.useState)(),f=g?.n??0'
    patchS6b_new = '[g,b]=(0,n.useState)(initFld),f=g?.n??0'

    # S7. Show translated folder name in chip (e.g. «Входящие» instead of «/inbox»)
    # N=a(790) already imported in module 3475; N.VN translates system folder names via folders.* keys
    patchS7_old = 'label:g.absFolderPath,hasAvatar:!0'
    patchS7_new = 'label:(0,N.VN)({folderName:g.name})||g.absFolderPath,hasAvatar:!0'

    return [
        ("settings: Экспортировать Ae и Jy из модуля 3475",       patchS1_old, patchS1_new),
        ("settings: Добавить props initialFromEmail/FilterName",   patchS2_old, patchS2_new),
        ("settings: Предзаполнить условие From (точное совп.)",    patchS3_old, patchS3_new),
        ("settings: Активный фильтр по умолчанию",                 patchS4_old, patchS4_new),
        ("settings: Действие Переместить в папку по умолчанию",   patchS5_old, patchS5_new),
        ("settings: Добавить initialFolder prop к j",              patchS6a_old, patchS6a_new),
        ("settings: Pre-select Inbox folder в j useState",         patchS6b_old, patchS6b_new),
        ("settings: Локализовать имя папки в чипе Apply-диалога", patchS7_old,  patchS7_new),
    ]

# Patches for incremental update: Jy export + S6 when S1-S5 are already applied
def build_patches_settings_incremental():
    patchJy_old = "a.r(t),a.d(t,{default:()=>yt,Ae:()=>Ae})"
    patchJy_new = "a.r(t),a.d(t,{default:()=>yt,Ae:()=>Ae,Jy:()=>j})"

    patchS6a_old = 'const j=({criteria:e,onClose:t})=>'
    patchS6a_new = 'const j=({criteria:e,onClose:t,initialFolder:initFld})=>'

    patchS6b_old = '[g,b]=(0,n.useState)(),f=g?.n??0'
    patchS6b_new = '[g,b]=(0,n.useState)(initFld),f=g?.n??0'

    patchS7_old = 'label:g.absFolderPath,hasAvatar:!0'
    patchS7_new = 'label:(0,N.VN)({folderName:g.name})||g.absFolderPath,hasAvatar:!0'

    return [
        ("settings: Добавить Jy экспорт",                          patchJy_old,  patchJy_new),
        ("settings: Добавить initialFolder prop к j",               patchS6a_old, patchS6a_new),
        ("settings: Pre-select Inbox folder в j useState",          patchS6b_old, patchS6b_new),
        ("settings: Локализовать имя папки в чипе Apply-диалога",  patchS7_old,  patchS7_new),
    ]

# ─────────────────────────────────────────────────────────────────────────────
# Patches for chunk 388 (preview toolbar — module 1197)
# ─────────────────────────────────────────────────────────────────────────────

def build_patches_388():
    patch1_old = "canExecute:a}}}}]);"
    patch1_new = "canExecute:a}}}" + NEW_MODULE + "}}]);"

    patch2_old = "var y=a(9191),v=a.n(y),x=a(1132),C=a(3405),k=a(566);"
    patch2_new = "var y=a(9191),v=a.n(y),x=a(1132),C=a(3405),k=a(566),CF=a(9999);"

    patch3_old = "}=(0,C.S)({message:e,shouldReplaceHistory:o}),z=(0,k.W)(T,e.tags),"
    patch3_new = "}=(0,C.S)({message:e,shouldReplaceHistory:o}),Q=(0,CF.q)(e),z=(0,k.W)(T,e.tags),"

    patch4_old = ",(0,x.A)($),(0,x.A)(P)].filter(e=>!e.disabled)"
    patch4_new = ",(0,x.A)($),(0,x.A)(P),(0,x.A)(Q)].filter(e=>!e.disabled)"

    patch5_old = ",I,R,D,$,P,a]);"
    patch5_new = ",I,R,D,$,P,Q,a]);"

    return [
        ("388: Добавить module 9999 в chunk",             patch1_old, patch1_new),
        ("388: Импорт CF в module 1197",                  patch2_old, patch2_new),
        ("388: Вызов хука в компоненте",                  patch3_old, patch3_new),
        ("388: Добавить пункт в массив действий",         patch4_old, patch4_new),
        ("388: Добавить Q в зависимости useMemo",         patch5_old, patch5_new),
    ]

# ─────────────────────────────────────────────────────────────────────────────
# Patches for chunk 336 (right-click context menu — module 8264)
# ─────────────────────────────────────────────────────────────────────────────

def build_patches_336():
    patchA_old = "execute:l,canExecute:r}}}}]);"
    patchA_new = "execute:l,canExecute:r}}}" + NEW_MODULE + "}}]);"

    patchB_old = "var r=a(7559),n=a.n(r),o=a(8153),l=a(1132),i=a(9518),s=a(3405),c=a(566),d=a(6609),u=a(4713),m=a(4702);"
    patchB_new = "var r=a(7559),n=a.n(r),o=a(8153),l=a(1132),i=a(9518),s=a(3405),c=a(566),d=a(6609),u=a(4713),m=a(4702),CF=a(9999);"

    patchC_old = "[U]=(0,o.useTranslation)(),Y=(0,r.useMemo)(()=>["
    patchC_new = "[U]=(0,o.useTranslation)(),Q=(0,CF.q)(e),Y=(0,r.useMemo)(()=>["

    patchD_old = ",(0,l.A)(B),(0,l.A)($)].filter(e=>!(e.disabled||H&&\"ForwardMenu\"===e.id))"
    patchD_new = ",(0,l.A)(B),(0,l.A)($),(0,l.A)(Q)].filter(e=>!(e.disabled||H&&\"ForwardMenu\"===e.id))"

    patchE_old = ",$,N,H])"
    patchE_new = ",$,N,H,Q])"

    return [
        ("336: Добавить module 9999 в chunk",             patchA_old, patchA_new),
        ("336: Импорт CF в module 8264",                  patchB_old, patchB_new),
        ("336: Вызов хука create-filter",                 patchC_old, patchC_new),
        ("336: Добавить пункт в контекстное меню",        patchD_old, patchD_new),
        ("336: Добавить Q в зависимости useMemo",         patchE_old, patchE_new),
    ]

# ─────────────────────────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_check():
    chunk388     = find_chunk_388()
    chunk336     = find_chunk_336()
    chunkSetting = find_chunk_settings()
    c388     = read(chunk388)
    c336     = read(chunk336)
    cSetting = read(chunkSetting)

    ok388     = PATCH_MARKER_388 in c388
    ok336     = PATCH_MARKER_336 in c336
    okSetting = PATCH_MARKER_SETTINGS in cSetting
    okJy      = "Jy:()=>j" in cSetting
    okS6b     = "useState)(initFld)" in cSetting
    okS7      = PATCH_MARKER_S7 in cSetting

    print(f"{'✓' if ok388     else '✗'}  chunk 388      {'применён' if ok388     else 'НЕ применён'}: {chunk388}")
    print(f"{'✓' if ok336     else '✗'}  chunk 336      {'применён' if ok336     else 'НЕ применён'}: {chunk336}")
    print(f"{'✓' if okSetting else '✗'}  chunk settings {'применён' if okSetting else 'НЕ применён'}: {chunkSetting}")
    print(f"  {'✓' if okJy  else '✗'}  Jy экспорт: {'да' if okJy else 'нет'}")
    print(f"  {'✓' if okS6b else '✗'}  initFld (Inbox): {'да' if okS6b else 'нет'}")
    print(f"  {'✓' if okS7  else '✗'}  локализация имени папки (S7): {'да' if okS7 else 'нет'}")
    okRu = cmd_check_ru_json()

    return ok388 and ok336 and okSetting and okS7 and okRu

def _apply_patches(chunk_path, patches, marker, already_msg):
    content = read(chunk_path)

    if marker in content:
        print(already_msg)
        return False

    print("\nПроверка корректности патчей...")
    for desc, old, new in patches:
        count = content.count(old)
        if count == 0:
            die(f"Строка для замены НЕ НАЙДЕНА ({desc}).\n"
                f"Вероятно, версия carbonio-mails-ui изменилась.\n"
                f"Ищем: {old[:80]}...")
        if count > 1:
            die(f"Строка найдена {count} раз (должна быть 1): {desc}\n"
                f"Патч небезопасен — прерываем.")
        print(f"  ✓ {desc}")

    print("\nСоздаём бэкап...")
    backup(chunk_path)

    print("\nПрименяем патчи...")
    new_content = content
    for desc, old, new in patches:
        new_content = new_content.replace(old, new, 1)
        print(f"  ✓ {desc}")

    if marker not in new_content:
        die("После замен маркер патча не найден — что-то пошло не так!")

    write(chunk_path, new_content)
    return True

def cmd_install():
    chunk388     = find_chunk_388()
    chunk336     = find_chunk_336()
    chunkSetting = find_chunk_settings()

    print(f"chunk settings: {chunkSetting}")
    cSetting = read(chunkSetting)

    if PATCH_MARKER_SETTINGS in cSetting and PATCH_MARKER_S7 in cSetting:
        print("chunk settings: патч уже применён полностью, пропускаем.")
        appliedSetting = False
    elif PATCH_MARKER_SETTINGS in cSetting and PATCH_MARKER_S7 not in cSetting:
        # S1-S6 applied (previous version without S7), add folder name translation
        print("chunk settings: S1-S6 уже применены, применяем S7 (локализация имени папки)...")
        s7_patches = [("settings: Локализовать имя папки в чипе Apply-диалога",
                        'label:g.absFolderPath,hasAvatar:!0',
                        'label:(0,N.VN)({folderName:g.name})||g.absFolderPath,hasAvatar:!0')]
        appliedSetting = _apply_patches(
            chunkSetting, s7_patches, PATCH_MARKER_S7,
            "chunk settings: S7 уже применён."
        )
    elif "Ae:()=>Ae" in cSetting and "Jy:()=>j" not in cSetting:
        # S1-S5 already applied (previous version), add Jy + S6 incrementally
        print("chunk settings: S1-S5 уже применены, применяем Jy + S6 (initialFolder)...")
        appliedSetting = _apply_patches(
            chunkSetting, build_patches_settings_incremental(), PATCH_MARKER_SETTINGS,
            "chunk settings: уже полностью применён."
        )
    else:
        # Fresh install (original file or post-rollback)
        appliedSetting = _apply_patches(
            chunkSetting, build_patches_settings(), PATCH_MARKER_SETTINGS,
            "chunk settings: патч уже применён полностью, пропускаем."
        )
    if appliedSetting:
        print(f"✓ chunk settings пропатчен")

    print()
    print(f"chunk 388: {chunk388}")
    applied388 = _apply_patches(
        chunk388, build_patches_388(), PATCH_MARKER_388,
        "chunk 388: патч уже применён, пропускаем."
    )
    if applied388:
        print(f"✓ chunk 388 пропатчен")

    print()
    print(f"chunk 336: {chunk336}")
    applied336 = _apply_patches(
        chunk336, build_patches_336(), PATCH_MARKER_336,
        "chunk 336: патч уже применён, пропускаем."
    )
    if applied336:
        print(f"✓ chunk 336 пропатчен")

    print()
    print("ru.json:")
    appliedRu = cmd_patch_ru_json()

    if appliedSetting or applied388 or applied336 or appliedRu:
        print("\n✓ Готово. Обновите страницу браузера (Ctrl+Shift+R).")
        print("  «Создать фильтр» появится:")
        print("  1. В тулбаре превью письма (⋮ → Ещё действия → Создать фильтр)")
        print("  2. В контекстном меню по right-click на письме в списке")
        print("  После нажатия «Создать»: диалог подтверждения →")
        print("    «Нет» — снекбар «Фильтр создан»")
        print("    «Да»  — Apply-диалог с предвыбором папки Входящие и реальным счётчиком")

def cmd_rollback():
    cmd_rollback_ru_json()
    for find_fn, label in [
        (find_chunk_settings, "chunk settings"),
        (find_chunk_388,      "chunk 388"),
        (find_chunk_336,      "chunk 336"),
    ]:
        chunk = find_fn()
        backups = sorted(glob.glob(chunk + ".bak.*"), reverse=True)
        if not backups:
            print(f"  {label}: бэкап не найден для {chunk}, пропускаем")
            continue
        latest = backups[0]
        print(f"  {label}: восстанавливаем из {latest}")
        shutil.copy2(latest, chunk)
        print(f"  {label}: ✓ восстановлено")

# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "install"
    if arg == "check":
        cmd_check()
    elif arg == "rollback":
        cmd_rollback()
    elif arg == "install":
        cmd_install()
    else:
        print(__doc__)
        sys.exit(1)
