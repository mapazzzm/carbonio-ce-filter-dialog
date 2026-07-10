#!/usr/bin/env python3
"""
carbonio-create-filter — installer
Adds "Create Filter" / "Создать фильтр" + "Highlight with color" / "Выделять цветом":
  1. Preview toolbar (⋮ → More actions)     — chunk 388, module 1197
  2. Right-click context menu on message    — chunk 336, module 8264
  3. Exports Ae and Jy from module 3475     — mail-setting-view chunk
  4. After filter is saved — confirmation dialog:
       Yes → standard Apply-filter dialog with Inbox pre-selected and real count
       No  → "Filter created" snackbar
  5. "Highlight with color" action in filter editor (mail-setting-view + 336 + folder-panel-view)
  6. Patches ru.json and en.json with translations
  7. Bugfix: lets you disable an unconditional filter (forward-all) — Carbonio's
     backend can't deactivate a rule with no condition (nothing to wrap in
     `disabled_if`); the patch represents "disabled" via a hidden `trueTest`.

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

# ── create-filter markers ─────────────────────────────────────────────────────
PATCH_MARKER_388      = "9999:(e,t,a)=>"
PATCH_MARKER_336      = "CF=a(9999)"
PATCH_MARKER_SETTINGS = "useState)(initFld)"
PATCH_MARKER_S7       = "N.VN)({folderName:g.name})"

# ── bugfix markers ────────────────────────────────────────────────────────────
PATCH_MARKER_917      = "i.tags||[]"   # fix: i.tags is not iterable on TAG/UNTAG
FF_MARKER_SETTINGS    = "__cuFilterFix"  # fix: can't disable an unconditional filter

# ── color-filter constants & markers ─────────────────────────────────────────
CC_COLORS_JS = (
    '["rgba(220,80,80,0.18)","rgba(220,140,50,0.18)","rgba(200,200,50,0.18)",'
    '"rgba(80,180,80,0.18)","rgba(50,200,200,0.18)","rgba(50,130,220,0.22)",'
    '"rgba(150,80,220,0.18)","rgba(220,80,180,0.18)","rgba(180,120,60,0.18)",'
    '"rgba(120,120,120,0.18)"]'
)
CC_LABELS_JS = (
    '["Красный","Оранжевый","Жёлтый","Зелёный","Бирюзовый",'
    '"Синий","Фиолетовый","Розовый","Коричневый","Серый"]'
)
CC_ZIMBRA_COLORS_JS = '[5,9,6,3,2,1,4,7,0,8]'

CC_MARKER_SETTINGS = 'CC="actionColorize"'
CC_MARKER_LOCALIZE = 'tcc_("settings.set_color_placeholder"'
CC_MARKER_336      = 'CC_COLORS_M='
CC_MARKER_FPV      = 'CC_COLORS_L='

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

def _find_by_content(needle, label):
    """mails-ui 1.34.x переименовал числовые чанки — ищем файл по содержимому."""
    for d in _find_version_dirs():
        for f in sorted(glob.glob(os.path.join(d, "*.js"))):
            if ".bak." in f or f.endswith(".map"):
                continue
            try:
                if needle in read(f):
                    return f
            except OSError:
                pass
    die("Не найден файл с сигнатурой " + label + " в " + MAILS_UI_BASE)

def detect_variant():
    """v1 = mails-ui 1.31.x (чанки 388/336/917), v2 = 1.34.x (40/946/app)."""
    for d in _find_version_dirs():
        if glob.glob(os.path.join(d, "388.*.chunk.js")):
            return "v1"
    return "v2"

def find_chunk_388():
    for d in _find_version_dirs():
        chunks = glob.glob(os.path.join(d, "388.*.chunk.js"))
        if chunks:
            return chunks[0]
    # 1.34.x: тулбар превью переехал в 40.*.chunk.js
    return _find_by_content(',n={id:"More",icon:"MoreVertical"', "toolbar (экс-388)")

def find_chunk_336():
    for d in _find_version_dirs():
        chunks = glob.glob(os.path.join(d, "336.*.chunk.js"))
        if chunks:
            return chunks[0]
    # 1.34.x: контекстное меню переехало в 946.*.chunk.js
    return _find_by_content('"ForwardMenu"===e.id', "context-menu (экс-336)")

def find_chunk_settings():
    for d in _find_version_dirs():
        chunks = glob.glob(os.path.join(d, "mail-setting-view.*.chunk.js"))
        if chunks:
            return chunks[0]
    die("Не найден mail-setting-view.*.chunk.js в " + MAILS_UI_BASE)

def find_chunk_fpv():
    for d in _find_version_dirs():
        chunks = glob.glob(os.path.join(d, "folder-panel-view.*.chunk.js"))
        if chunks:
            return chunks[0]
    die("Не найден folder-panel-view.*.chunk.js в " + MAILS_UI_BASE)

def find_chunk_917():
    for d in _find_version_dirs():
        chunks = glob.glob(os.path.join(d, "917.*.chunk.js"))
        if chunks:
            return chunks[0]
    # 1.34.x: optimistic TAG/UNTAG переехал в главный app.*.js
    return _find_by_content(".UNTAG&&", "optimistic TAG/UNTAG (экс-917)")

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
    # суффикс должен быть уникальным: два backup() одного файла в одну секунду
    # (main-патч + color-патч) иначе перезапишут друг друга
    ts = time.strftime("%Y%m%d%H%M%S")
    dst = path + ".bak." + ts
    n = 1
    while os.path.exists(dst):
        dst = path + ".bak." + ts + "_" + str(n)
        n += 1
    shutil.copy2(path, dst)
    print(f"  Бэкап: {dst}")
    return dst

# ─────────────────────────────────────────────────────────────────────────────
# ru.json / en.json patching
# ─────────────────────────────────────────────────────────────────────────────

RU_JSON_PATH = os.path.join(MAILS_UI_BASE, "i18n", "ru.json")
EN_JSON_PATH = os.path.join(MAILS_UI_BASE, "i18n", "en.json")

RU_KEYS = {
    # create-filter: confirmation dialog
    ("action", "apply_filter_confirm"):
        "Применить условия созданного фильтра для ранее полученных писем?",
    ("modals", "apply_filters", "apply_folder_one"):
        "<bold>{{count}} письмо</bold> будет обработано в выбранной папке.",
    ("modals", "apply_filters", "apply_folder_few"):
        "<bold>{{count}} письма</bold> будет обработано в выбранной папке.",
    ("modals", "apply_filters", "apply_folder_many"):
        "<bold>{{count}} писем</bold> будет обработано в выбранной папке.",
    ("modals", "apply_filters", "apply_folder_other"):
        "<bold>{{count}} сообщение</bold> будет обработано в выбранной папке.",
    ("label", "yes"): "Да",
    ("label", "no"):  "Нет",
    # color-filter: action label + color picker placeholder
    ("settings", "set_color"):             "Выделять цветом",
    ("settings", "set_color_placeholder"): "Выберите цвет",
}

EN_KEYS = {
    # create-filter: buttons missing from en.json
    ("label", "yes"): "Yes",
    ("label", "no"):  "No",
    # color-filter
    ("settings", "set_color"):             "Highlight with color",
    ("settings", "set_color_placeholder"): "Select color",
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

def cmd_patch_json(path, keys, lang):
    if not os.path.exists(path):
        print(f"  {lang}.json: не найден по пути {path}, пропускаем")
        return False
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    missing = {k: v for k, v in keys.items() if _get_nested(data, k) != v}
    if not missing:
        print(f"  {lang}.json: все ключи уже на месте, пропускаем.")
        return False
    ts = time.strftime("%Y%m%d%H%M%S")
    bak = path + ".bak." + ts
    shutil.copy2(path, bak)
    print(f"  Бэкап: {bak}")
    for keys_tuple, value in missing.items():
        _set_nested(data, keys_tuple, value)
        print(f"  ✓ добавлен: {'.'.join(keys_tuple)}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"  ✓ {lang}.json обновлён")
    return True

def cmd_check_json(path, keys, lang):
    if not os.path.exists(path):
        print(f"  {'✗'}  {lang}.json: не найден")
        return False
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    ok = all(_get_nested(data, k) == v for k, v in keys.items())
    print(f"  {'✓' if ok else '✗'}  {lang}.json: {'все ключи на месте' if ok else 'требует обновления'}")
    return ok

def cmd_rollback_json(path, lang):
    backups = sorted(glob.glob(path + ".bak.*"), reverse=True)
    if not backups:
        print(f"  {lang}.json: бэкап не найден, пропускаем")
        return
    latest = backups[0]
    print(f"  {lang}.json: восстанавливаем из {latest}")
    shutil.copy2(latest, path)
    print(f"  {lang}.json: ✓ восстановлено")

# ─────────────────────────────────────────────────────────────────────────────
# Module 9999 — "Create Filter" action hook
# ─────────────────────────────────────────────────────────────────────────────

NEW_MODULE = r""",9999:(e,t,a)=>{a.d(t,{q:()=>H});var n=a(7559),s=a(8153),d=a(7625),i=a(4702);function findFolder(root,id){if(!root)return null;var arr=Array.isArray(root)?root:[root];for(var fi=0;fi<arr.length;fi++){var f=arr[fi];if(String(f.id)===String(id))return f;var found=findFolder(f.folder,id);if(found)return found;}return null;}async function soapCall(m,b){try{var res=await fetch("/service/soap/"+m+"Request",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({Header:{context:{_jsns:"urn:zimbra",format:{type:"js"}}},Body:{[m+"Request"]:b}})});var data=await res.json();return data?.Body?.[m+"Response"];}catch(ex){return null;}}function H(message){var uu=(0,d.m)();var createModal=uu.createModal,closeModal=uu.closeModal,createSnackbar=uu.createSnackbar;var tt=(0,s.useTranslation)(),t=tt[0];var sender=n.useMemo(function(){return message&&message.participants&&message.participants.find(function(p){return p.type==="f";});},[message]);var senderEmail=(sender&&(sender.address||sender.email))||"";n.useEffect(function(){Promise.all([a.e(237),a.e(654),a.e(486),a.e(471),a.e(169),a.e(949)]).catch(function(){});},[]);var canExecute=n.useCallback(function(){return!!senderEmail;},[senderEmail]);var execute=n.useCallback(function(){if(!canExecute())return;var id="create-filter-"+Date.now();var close=function(){closeModal(id);};Promise.all([a.e(237),a.e(654),a.e(486),a.e(471),a.e(169),a.e(949)]).then(function(){var AeComp=a(3475).Ae;if(!AeComp){createSnackbar&&createSnackbar({key:"cf-load-err",severity:"error",label:t("label.error_try_again","Something went wrong, please try again"),hideButton:true});return;}createModal({id:id,size:"large",onClose:close,children:n.createElement(AeComp,{onClose:close,isIncoming:true,initialFromEmail:senderEmail,initialFilterName:t("settings.filter_name_prefix","Emails from ")+senderEmail,onConfirm:function(filter){var filterName=filter.name;soapCall("GetFilterRules",{_jsns:"urn:zimbraMail"}).then(function(gr){var existing=(gr&&gr.filterRules&&gr.filterRules[0]&&gr.filterRules[0].filterRule)||[];var combined=existing.concat([filter]);return soapCall("ModifyFilterRules",{_jsns:"urn:zimbraMail",filterRules:[{filterRule:combined}]});}).then(function(){close();var confirmId="cf-confirm-"+Date.now();var closeConfirm=function(){closeModal(confirmId);};var handleNo=function(){closeConfirm();if(createSnackbar)createSnackbar({key:"cf-ok",severity:"info",label:t("settings.filter_created","Filter created"),hideButton:true,autoHideTimeout:3000});};var handleYes=function(){closeConfirm();Promise.all([a.e(237),a.e(654),a.e(486),a.e(471),a.e(169),a.e(949)]).then(function(){var Jy=a(3475).Jy;if(!Jy){handleNo();return;}return soapCall("GetFolder",{_jsns:"urn:zimbraMail",folder:{id:"2"}}).then(function(fr){var raw=findFolder(fr&&fr.folder,"2");var inbox=raw?{id:raw.id||"2",name:raw.name||"Inbox",absFolderPath:raw.absPath||raw.absFolderPath||"/Inbox",n:raw.n||0}:{id:"2",absFolderPath:"/Inbox",name:"Inbox",n:0};var applyId="cf-apply-"+Date.now();var closeApply=function(){closeModal(applyId);};createModal({id:applyId,size:"medium",onClose:closeApply,children:n.createElement(i.ModalManager,null,n.createElement(Jy,{criteria:{filterName:filterName},initialFolder:inbox,onClose:closeApply}))},true);});}).catch(function(){handleNo();});};createModal({id:confirmId,size:"small",onClose:handleNo,children:n.createElement(i.Container,null,n.createElement(i.ModalHeader,{onClose:handleNo,title:t("settings.filter_created","Filter created"),showCloseIcon:true}),n.createElement(i.Divider,null),n.createElement(i.Container,{padding:{all:"large"},mainAlignment:"flex-start",crossAlignment:"flex-start"},n.createElement(i.Text,{overflow:"break-word"},t("action.apply_filter_confirm","Apply the conditions of the created filter to previously received messages?"))),n.createElement(i.Divider,null),n.createElement(i.ModalFooter,{confirmLabel:t("label.yes","Yes"),onConfirm:handleYes,secondaryActionLabel:t("label.no","No"),onSecondaryAction:handleNo,onClose:handleNo}))},true);}).catch(function(){if(createSnackbar)createSnackbar({key:"cf-err",severity:"error",label:t("label.error_try_again","Something went wrong, please try again"),hideButton:true});});}})},true);}).catch(function(){if(createSnackbar)createSnackbar({key:"cf-load-err",severity:"error",label:t("label.error_try_again","Something went wrong, please try again"),hideButton:true});});},[canExecute,createModal,closeModal,createSnackbar,t,senderEmail]);return n.useMemo(function(){return{id:"message-create-filter",icon:"FunnelOutline",label:t("action.create_filter_from_sender","Create Filter"),execute:execute,canExecute:canExecute};},[execute,canExecute,t]);}"""

# ─────────────────────────────────────────────────────────────────────────────
# Patches for mail-setting-view — create-filter (S1–S7)
# ─────────────────────────────────────────────────────────────────────────────

def build_patches_settings():
    patchS1_old = "a.r(t),a.d(t,{default:()=>yt})"
    patchS1_new = "a.r(t),a.d(t,{default:()=>yt,Ae:()=>Ae,Jy:()=>j})"

    patchS2_old = 'Ae=({onClose:e,onConfirm:t,isIncoming:a})=>{const[d]=(0,c.useTranslation)(),[m,u]=(0,n.useState)("")'
    patchS2_new = 'Ae=({onClose:e,onConfirm:t,isIncoming:a,initialFromEmail:iEmail,initialFilterName:iName})=>{const[d]=(0,c.useTranslation)(),[m,u]=(0,n.useState)(iName||"")'

    patchS3_old = '[S,w]=(0,n.useState)([{filterActions:[{actionKeep:[{}],actionStop:[{}]}],active:g,name:m,key:"subject",label:"Subject",filterTests:[{}],index:0,comp:l().createElement(oe,{t:d,activeIndex:0})}])'
    patchS3_new = '[S,w]=(0,n.useState)(iEmail?[{filterActions:[{actionKeep:[{}],actionStop:[{}]}],active:g,name:m,key:"from",label:"From",filterTests:[{condition:f,addressTest:[{header:"from",part:"all",stringComparison:"is",value:iEmail}]}],index:0,comp:l().createElement(ye,{t:d,activeIndex:0,defaultValue:{addressTest:[{header:"from",part:"all",stringComparison:"is",value:iEmail}]}})}]:[{filterActions:[{actionKeep:[{}],actionStop:[{}]}],active:g,name:m,key:"subject",label:"Subject",filterTests:[{}],index:0,comp:l().createElement(oe,{t:d,activeIndex:0})}])'

    patchS4_old = '[g,b]=(0,n.useState)(!1),[f,h]=(0,n.useState)("anyof")'
    patchS4_new = '[g,b]=(0,n.useState)(iEmail?!0:!1),[f,h]=(0,n.useState)("anyof")'

    patchS5_old = '[E,C]=(0,n.useState)([{actionKeep:[{}],id:(0,L.A)()}])'
    patchS5_new = '[E,C]=(0,n.useState)(iEmail?[{actionFileInto:[{folderPath:""}],id:(0,L.A)()}]:[{actionKeep:[{}],id:(0,L.A)()}])'

    patchS6a_old = 'const j=({criteria:e,onClose:t})=>'
    patchS6a_new = 'const j=({criteria:e,onClose:t,initialFolder:initFld})=>'

    patchS6b_old = '[g,b]=(0,n.useState)(),f=g?.n??0'
    patchS6b_new = '[g,b]=(0,n.useState)(initFld),f=g?.n??0'

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
# Patches for mail-setting-view — color-filter (CC-S1–CC-S7)
# ─────────────────────────────────────────────────────────────────────────────

def build_patches_settings_color():
    cc_le_component = (
        'cc_le=({value:e,onChange:t})=>{'
        'const[tcc_]=(0,c.useTranslation)();'
        'const a_=e?.actionTag?.[0]?.tagName,'
        'r_=a_&&CC_LABELS.includes(a_)?CC_LABELS.indexOf(a_):-1,'
        'cc_items=(0,n.useMemo)(()=>CC_COLORS.map((clr,idx)=>({'
        'label:CC_LABELS[idx],value:idx,'
        'customComponent:l().createElement(i.Row,{padding:{horizontal:"small"},crossAlignment:"center",height:"fit"},'
        'l().createElement("div",{style:{width:"0.875rem",height:"0.875rem",borderRadius:"0.1875rem",'
        'background:clr,flexShrink:0,border:"1px solid rgba(0,0,0,0.15)"}},'
        '),l().createElement(i.Padding,{left:"small"},l().createElement(i.Text,null,CC_LABELS[idx])))})),[]),'
        'cc_def=r_>=0&&r_<10?cc_items[r_]:undefined,'
        'cc_onChg=(0,n.useCallback)(ev=>{'
        'const tn=CC_LABELS[ev],'
        'tags=(0,s.Q2)();'
        'Object.values(tags).some(t=>t.name===tn)||'
        '(0,d.Dq)("CreateTag",{_jsns:"urn:zimbraMail",tag:{name:tn,color:CC_ZIMBRA_COLORS[ev]??0}}).catch(()=>{});'
        't({actionTag:[{tagName:tn}]});},[t]);'
        '(0,n.useEffect)(()=>{'
        'if(a_&&CC_LABELS.includes(a_)){'
        'const tags=(0,s.Q2)();'
        'Object.values(tags).some(tt=>tt.name===a_)||'
        '(0,d.Dq)("CreateTag",{_jsns:"urn:zimbraMail",tag:{name:a_,color:CC_ZIMBRA_COLORS[CC_LABELS.indexOf(a_)]??0}}).catch(()=>{});}}'
        ',[]);'
        'return l().createElement(i.Row,{padding:{right:"small"},minWidth:"12.5rem"},'
        'l().createElement(i.Select,{label:tcc_("settings.set_color_placeholder","Select color"),background:"gray4",onChange:cc_onChg,'
        'items:cc_items,defaultSelection:cc_def,"data-testid":"color-select"}))}'
    )

    old_S1 = 'H="actionKeep",U="actionDiscard",V="actionFileInto",K="actionTag",G="actionFlag",Y="actionRedirect"'
    new_S1 = (old_S1 +
              f',CC="actionColorize",CC_ZIMBRA_COLORS={CC_ZIMBRA_COLORS_JS}'
              f',CC_COLORS={CC_COLORS_JS},CC_LABELS={CC_LABELS_JS}')

    old_S2 = '"data-testid":"tag-input"})},ie='
    new_S2 = ('"data-testid":"tag-input"}}},\n' + cc_le_component + ',ie=')

    return [
        ("color-filter/settings: Константы CC",             old_S1, new_S1),
        ("color-filter/settings: Компонент cc_le",          old_S2, new_S2),
        ("color-filter/settings: CC в массив de",
         'de=[H,U,V,K,G],me=[...de,Y]',
         'de=[H,U,V,K,G,CC],me=[...de,Y]'),
        ("color-filter/settings: Детект CC в b",
         'b=g.find(e=>e in a)??"actionKeep"',
         'b=("_colorize" in a||CC_LABELS.includes(a?.actionTag?.[0]?.tagName))?CC:(g.find(e=>e in a)??"actionKeep")'),
        ("color-filter/settings: Ветка CC в рендере E",
         'E=(y=m,V in(C=a)?',
         'E=(y=m,b===CC?l().createElement(cc_le,{value:a,onChange:y}):V in(C=a)?'),
        ("color-filter/settings: Дефолт [CC]",
         '[Y]:{actionRedirect:[{a:""}]}}}',
         '[Y]:{actionRedirect:[{a:""}]},[CC]:{_colorize:""}}}'),
        ("color-filter/settings: Метка Выделять цветом",
         '[Y]:t("settings.redirect_to_address","Redirect to address")',
         '[Y]:t("settings.redirect_to_address","Redirect to address"),[CC]:t("settings.set_color","Highlight with color")'),
    ]

def build_patches_settings_color_localize():
    """Incremental: adds tcc_ to existing cc_le (installs without localized placeholder)."""
    return [
        ("color-filter/settings: Добавить tcc_ в cc_le",
         'cc_le=({value:e,onChange:t})=>{const a_=e?.actionTag',
         'cc_le=({value:e,onChange:t})=>{const[tcc_]=(0,c.useTranslation)();const a_=e?.actionTag'),
        ("color-filter/settings: Локализовать label Select",
         'label:"Выберите цвет",background:"gray4"',
         'label:tcc_("settings.set_color_placeholder","Select color"),background:"gray4"'),
    ]

# ─────────────────────────────────────────────────────────────────────────────
# Patches for chunk 388 — create-filter (preview toolbar)
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
# Patches for chunk 336 — create-filter (right-click menu)
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

    patchF_old = 'createElement(o.Dropdown,{contextMenu:!0,items:de,display:"block",style:{width:"100%",height:"4rem"}'
    patchF_new = 'createElement(o.Dropdown,{contextMenu:!0,maxHeight:"100vh",items:de,display:"block",style:{width:"100%",height:"4rem"}'

    patchG_old = 'createElement(m.Dropdown,{contextMenu:!0,items:e,display:"block",style:{width:"100%",height:"4rem"}'
    patchG_new = 'createElement(m.Dropdown,{contextMenu:!0,maxHeight:"100vh",items:e,display:"block",style:{width:"100%",height:"4rem"}'

    return [
        ("336: Добавить module 9999 в chunk",             patchA_old, patchA_new),
        ("336: Импорт CF в module 8264",                  patchB_old, patchB_new),
        ("336: Вызов хука create-filter",                 patchC_old, patchC_new),
        ("336: Добавить пункт в контекстное меню",        patchD_old, patchD_new),
        ("336: Добавить Q в зависимости useMemo",         patchE_old, patchE_new),
        ("336: maxHeight 100vh для контекст. меню (de)",  patchF_old, patchF_new),
        ("336: maxHeight 100vh для g-компонента",         patchG_old, patchG_new),
    ]

# ─────────────────────────────────────────────────────────────────────────────
# Patches for chunk 336 — color-filter (message row highlight + hide tag icon)
# ─────────────────────────────────────────────────────────────────────────────

def build_patches_336_color():
    cc_colors_const = f'const CC_COLORS_M={CC_COLORS_JS};const CC_LABELS_M={CC_LABELS_JS};'
    return [
        ("color-filter/336: CC_COLORS_M + CC_LABELS_M",
         'const T=({message:e,selected:t',
         f'{cc_colors_const}const T=({{message:e,selected:t'),
        ("color-filter/336: _hlBg фон строки сообщения",
         'B=(0,r.useMemo)(()=>i?l.noop:u,[i,u]);return n().createElement(o.Container,{mainAlignment:"flex-start",orientation:"horizontal",height:"4rem"},',
         'B=(0,r.useMemo)(()=>i?l.noop:u,[i,u]);'
         'const _hlBg=(0,r.useMemo)(()=>{const t=S.find(s=>CC_LABELS_M.includes(s.name));if(!t)return null;const idx=CC_LABELS_M.indexOf(t.name);return idx>=0?CC_COLORS_M[idx]:null},[S]);'
         'return n().createElement(o.Container,{mainAlignment:"flex-start",orientation:"horizontal",height:"4rem",style:_hlBg?{background:_hlBg}:undefined},'),
        ("color-filter/336: Скрыть CC тег-иконку (компонент s)",
         'd=(0,r.useMemo)(()=>t?.length>1?"TagsMoreOutline":"Tag",[t]),u=(0,r.useMemo)(()=>1===t?.length?t?.[0]?.color:void 0,[t]),m=(0,i.nK)(t),g=(0,r.useMemo)(()=>e.tags&&0!==e.tags.length&&""!==e.tags?.[0]&&m,[m,e.tags])',
         '_t=t?.filter(x=>!CC_LABELS_M.includes(x?.name)),d=(0,r.useMemo)(()=>_t?.length>1?"TagsMoreOutline":"Tag",[_t]),u=(0,r.useMemo)(()=>1===_t?.length?_t?.[0]?.color:void 0,[_t]),m=(0,i.nK)(_t),g=(0,r.useMemo)(()=>_t&&_t.length>0&&m,[m,_t])'),
        ("color-filter/336: Скрыть CC тег-иконку (компонент T)",
         'F=(0,x.nK)(S),O=(0,r.useMemo)(()=>e.tags&&0!==e.tags.length&&""!==e.tags?.[0]&&F,[F,e.tags]),L=(0,r.useMemo)(()=>S.length>1?"TagsMoreOutline":"Tag",[S]),P=(0,r.useMemo)(()=>1===S.length?S[0].color:void 0,[S])',
         '_S=S.filter(x=>!CC_LABELS_M.includes(x?.name)),F=(0,x.nK)(_S),O=(0,r.useMemo)(()=>_S.length>0&&F,[F,_S]),L=(0,r.useMemo)(()=>_S.length>1?"TagsMoreOutline":"Tag",[_S]),P=(0,r.useMemo)(()=>1===_S.length?_S[0].color:void 0,[_S])'),
    ]

# ─────────────────────────────────────────────────────────────────────────────
# Patches for folder-panel-view — color-filter (conversation row highlight)
# ─────────────────────────────────────────────────────────────────────────────

def build_patches_fpv():
    cc_colors_const = f'const CC_COLORS_L={CC_COLORS_JS};const CC_LABELS_L={CC_LABELS_JS};'
    return [
        ("color-filter/fpv: CC_COLORS_L + CC_LABELS_L",
         'const L=({conversation:e,selected:t',
         f'{cc_colors_const}const L=({{conversation:e,selected:t'),
        ("color-filter/fpv: _hlBg фон строки беседы",
         'y=(0,s.useMemo)(()=>d?I("label.hide","Hide"):I("label.expand","Expand"),[d,I]);return a().createElement(r.Container,{mainAlignment:"flex-start",orientation:"horizontal",height:"4rem"},',
         'y=(0,s.useMemo)(()=>d?I("label.hide","Hide"):I("label.expand","Expand"),[d,I]);'
         'const _hlBg=(0,s.useMemo)(()=>{const t=f.find(s=>CC_LABELS_L.includes(s.name));if(!t)return null;const idx=CC_LABELS_L.indexOf(t.name);return idx>=0?CC_COLORS_L[idx]:null},[f]);'
         'return a().createElement(r.Container,{mainAlignment:"flex-start",orientation:"horizontal",height:"4rem",style:_hlBg?{background:_hlBg}:undefined},'),
    ]

# ─────────────────────────────────────────────────────────────────────────────
# Patches for chunk 917 — bugfix: i.tags is not iterable on TAG/UNTAG
# Root cause: optimisticallyHandleMessageActions spreads i.tags without null
# guard. Messages that never had tags have i.tags=undefined → TypeError.
# Triggered by color-filter tagging messages that previously had no tags.
# ─────────────────────────────────────────────────────────────────────────────

def build_patches_917():
    return [
        ("917: i.tags||[] guard in TAG/UNTAG optimistic update",
         't===S.qn.TAG&&n?i.tags=[...i.tags,n]:t===S.qn.UNTAG&&n&&(i.tags=(0,c.filter)(i.tags,e=>e!==n))',
         't===S.qn.TAG&&n?i.tags=[...(i.tags||[]),n]:t===S.qn.UNTAG&&n&&(i.tags=(0,c.filter)(i.tags||[],e=>e!==n))'),
    ]

# ─────────────────────────────────────────────────────────────────────────────
# Patches for mail-setting-view — bugfix: disable an unconditional filter
#
# Symptom: a forward-all filter (only a redirect action, NO condition) can't be
# deactivated — un-checking "Active filter" → Save → reopens still checked.
# Root cause is the Carbonio BACKEND, not the frontend: it deactivates a rule by
# wrapping it in Sieve `disabled_if <condition> { ... }`. With no condition there
# is nothing to wrap, so GetFilterRules always returns active:true.
# Fix: represent a disabled unconditional filter via `trueTest` (Sieve `true`,
# matches every message — identical behaviour for forward-all):
#   filterTests:[{condition:"allof",trueTest:[{index:0}]}], active:false
#   → disabled_if true { redirect :copy "..."; stop; }
# Two patches:
#   1. Save layer: a window.__cuFilterFix helper (injected after "use strict";)
#      injects trueTest into any rule whose filterTests is empty, called from
#      both ModifyFilterRules and ModifyOutgoingFilterRules.
#   2. Condition builder G: hide trueTest from the UI so the forward-all filter
#      shows with no condition rows (no phantom "subject contains…"). It is
#      self-healing — on the next save G omits trueTest → filterTests is empty
#      → the helper re-injects it.
# ─────────────────────────────────────────────────────────────────────────────

def build_patches_settings_filterfix():
    helper = (
        'window.__cuFilterFix=window.__cuFilterFix||function(rules){'
        'try{return(rules||[]).map(function(r){'
        'if(!r||typeof r!=="object")return r;'
        'var ft=r.filterTests&&r.filterTests[0];'
        'var hasTest=ft&&Object.keys(ft).some(function(k){return k!=="condition"});'
        'if(!hasTest){return Object.assign({},r,{filterTests:[{condition:ft&&ft.condition||"allof",trueTest:[{index:0}]}]})}'
        'return r})}catch(_){return rules}};'
    )
    return [
        ("filter-toggle: хелпер __cuFilterFix после use strict",
         '"use strict";(self.webpackChunkcarbonio_mails_ui',
         '"use strict";' + helper + '(self.webpackChunkcarbonio_mails_ui'),
        ("filter-toggle: обернуть ModifyFilterRules в __cuFilterFix",
         '"ModifyFilterRules",{filterRules:[{filterRule:e}]',
         '"ModifyFilterRules",{filterRules:[{filterRule:(window.__cuFilterFix||function(x){return x})(e)}]'),
        ("filter-toggle: обернуть ModifyOutgoingFilterRules в __cuFilterFix",
         '"ModifyOutgoingFilterRules",{filterRules:[{filterRule:e}]',
         '"ModifyOutgoingFilterRules",{filterRules:[{filterRule:(window.__cuFilterFix||function(x){return x})(e)}]'),
        ("filter-toggle: скрыть trueTest от билдера условий G",
         'if("condition"!==a){const n=t[a];(0,o.map)(n,t=>{e.push({...t,testName:a})})}',
         'if("condition"!==a&&"trueTest"!==a){const n=t[a];(0,o.map)(n,t=>{e.push({...t,testName:a})})}'),
    ]

# ─────────────────────────────────────────────────────────────────────────────
# V2 builders — mails-ui 1.34.x (Carbonio CE 26.6): чанки перенумерованы
# (388→40, 336→946, 917→app.*.js), минифицированные имена сменились.
# Module ids: React 7559, i18next 8153, DS 4702 — НЕ изменились; shell-хуки
# 7625→7712, settings-модуль 3475→7306 (chunk 949, deps [522,710,665,471,949]),
# Ae→at, Jy(j)→ge, From-компонент ye→Ge, uuid L.A→fe.A.
# S7 (локализация имени папки) в v2 НЕ применяется — util VN удалён из сборки.
# ─────────────────────────────────────────────────────────────────────────────

NEW_MODULE_V2 = (NEW_MODULE
    .replace("var n=a(7559),s=a(8153),d=a(7625),i=a(4702);",
             "var n=a(7559),s=a(8153),d=a(7712),i=a(4702);")
    .replace("a.e(237),a.e(654),a.e(486),a.e(471),a.e(169),a.e(949)",
             "a.e(522),a.e(710),a.e(665),a.e(471),a.e(949)")
    .replace("a(3475).Ae", "a(7306).Ae")
    .replace("a(3475).Jy", "a(7306).Jy"))

def build_patches_settings_v2():
    head_old = ('at=({onClose:e,onConfirm:t,isIncoming:a})=>{const[d]=(0,c.useTranslation)(),'
                '[m,u]=(0,n.useState)(""),[g,f]=(0,n.useState)(!1),[b,h]=(0,n.useState)("anyof")')
    head_new = ('at=({onClose:e,onConfirm:t,isIncoming:a,initialFromEmail:iEmail,initialFilterName:iName})=>'
                '{const[d]=(0,c.useTranslation)(),'
                '[m,u]=(0,n.useState)(iName||""),[g,f]=(0,n.useState)(iEmail?!0:!1),[b,h]=(0,n.useState)("anyof")')

    s3_old = ('[w,S]=(0,n.useState)([{filterActions:[{actionKeep:[{}],actionStop:[{}]}],'
              'active:g,name:m,key:"subject",label:"Subject",filterTests:[{}],index:0,'
              'comp:l().createElement(De,{t:d,activeIndex:0})}])')
    s3_new = ('[w,S]=(0,n.useState)(iEmail?[{filterActions:[{actionKeep:[{}],actionStop:[{}]}],'
              'active:g,name:m,key:"from",label:"From",filterTests:[{condition:b,'
              'addressTest:[{header:"from",part:"all",stringComparison:"is",value:iEmail}]}],index:0,'
              'comp:l().createElement(Ge,{t:d,activeIndex:0,defaultValue:{addressTest:[{header:"from",'
              'part:"all",stringComparison:"is",value:iEmail}]}})}]:[{filterActions:[{actionKeep:[{}],'
              'actionStop:[{}]}],active:g,name:m,key:"subject",label:"Subject",filterTests:[{}],index:0,'
              'comp:l().createElement(De,{t:d,activeIndex:0})}])')

    s5_old = '[E,C]=(0,n.useState)([{actionKeep:[{}],id:(0,fe.A)()}])'
    s5_new = '[E,C]=(0,n.useState)(iEmail?[{actionFileInto:[{folderPath:""}],id:(0,fe.A)()}]:[{actionKeep:[{}],id:(0,fe.A)()}])'

    return [
        ("settings-v2: Экспорт Ae/Jy из модуля 7306",
         "a.r(t),a.d(t,{default:()=>Gt})",
         "a.r(t),a.d(t,{default:()=>Gt,Ae:()=>at,Jy:()=>ge})"),
        ("settings-v2: props iEmail/iName + активный фильтр",  head_old, head_new),
        ("settings-v2: Предзаполнить условие From",            s3_old,   s3_new),
        ("settings-v2: Действие Переместить в папку",          s5_old,   s5_new),
        ("settings-v2: initialFolder prop к ge",
         "const ge=({criteria:e,onClose:t})=>",
         "const ge=({criteria:e,onClose:t,initialFolder:initFld})=>"),
        ("settings-v2: Pre-select Inbox в ge useState",
         "[f,b]=(0,n.useState)(),h=f?.n??0",
         "[f,b]=(0,n.useState)(initFld),h=f?.n??0"),
    ]

def build_patches_settings_color_v2():
    cc_le_component = (
        'cc_le=({value:e,onChange:t})=>{'
        'const[tcc_]=(0,c.useTranslation)();'
        'const a_=e?.actionTag?.[0]?.tagName,'
        'r_=a_&&CC_LABELS.includes(a_)?CC_LABELS.indexOf(a_):-1,'
        'cc_items=(0,n.useMemo)(()=>CC_COLORS.map((clr,idx)=>({'
        'label:CC_LABELS[idx],value:idx,'
        'customComponent:l().createElement(r.Row,{padding:{horizontal:"small"},crossAlignment:"center",height:"fit"},'
        'l().createElement("div",{style:{width:"0.875rem",height:"0.875rem",borderRadius:"0.1875rem",'
        'background:clr,flexShrink:0,border:"1px solid rgba(0,0,0,0.15)"}},'
        '),l().createElement(r.Padding,{left:"small"},l().createElement(r.Text,null,CC_LABELS[idx])))})),[]),'
        'cc_def=r_>=0&&r_<10?cc_items[r_]:undefined,'
        'cc_onChg=(0,n.useCallback)(ev=>{'
        'const tn=CC_LABELS[ev],'
        'tags=(0,o.Q2)();'
        'Object.values(tags).some(t=>t.name===tn)||'
        '(0,d.Dq)("CreateTag",{_jsns:"urn:zimbraMail",tag:{name:tn,color:CC_ZIMBRA_COLORS[ev]??0}}).catch(()=>{});'
        't({actionTag:[{tagName:tn}]});},[t]);'
        '(0,n.useEffect)(()=>{'
        'if(a_&&CC_LABELS.includes(a_)){'
        'const tags=(0,o.Q2)();'
        'Object.values(tags).some(tt=>tt.name===a_)||'
        '(0,d.Dq)("CreateTag",{_jsns:"urn:zimbraMail",tag:{name:a_,color:CC_ZIMBRA_COLORS[CC_LABELS.indexOf(a_)]??0}}).catch(()=>{});}}'
        ',[]);'
        'return l().createElement(r.Row,{padding:{right:"small"},minWidth:"12.5rem"},'
        'l().createElement(r.Select,{label:tcc_("settings.set_color_placeholder","Select color"),background:"gray4",onChange:cc_onChg,'
        'items:cc_items,defaultSelection:cc_def,"data-testid":"color-select"}))}'
    )

    old_S1 = 'pe="actionKeep",ve="actionDiscard",Ee="actionFileInto",Ce="actionTag",ye="actionFlag",ke="actionRedirect"'
    new_S1 = (old_S1 +
              f',CC="actionColorize",CC_ZIMBRA_COLORS={CC_ZIMBRA_COLORS_JS}'
              f',CC_COLORS={CC_COLORS_JS},CC_LABELS={CC_LABELS_JS}')

    return [
        ("color-v2/settings: Константы CC",           old_S1, new_S1),
        ("color-v2/settings: Компонент cc_le",
         '"data-testid":"tag-input"})},ze=',
         '"data-testid":"tag-input"})},' + cc_le_component + ',ze='),
        ("color-v2/settings: CC в массив Oe",
         'Oe=[pe,ve,Ee,Ce,ye],Ne=[...Oe,ke]',
         'Oe=[pe,ve,Ee,Ce,ye,CC],Ne=[...Oe,ke]'),
        ("color-v2/settings: Детект CC в f",
         'f=g.find(e=>e in a)??"actionKeep"',
         'f=("_colorize" in a||CC_LABELS.includes(a?.actionTag?.[0]?.tagName))?CC:(g.find(e=>e in a)??"actionKeep")'),
        ("color-v2/settings: Ветка CC в рендере E",
         'E=(y=m,Ee in(C=a)?',
         'E=(y=m,f===CC?l().createElement(cc_le,{value:a,onChange:y}):Ee in(C=a)?'),
        ("color-v2/settings: Дефолт [CC]",
         '[ke]:{actionRedirect:[{a:""}]}}}',
         '[ke]:{actionRedirect:[{a:""}]},[CC]:{_colorize:""}}}'),
        ("color-v2/settings: Метка Выделять цветом",
         '[ke]:t("settings.redirect_to_address","Redirect to address")',
         '[ke]:t("settings.redirect_to_address","Redirect to address"),[CC]:t("settings.set_color","Highlight with color")'),
    ]

def build_patches_settings_filterfix_v2():
    v1 = build_patches_settings_filterfix()
    # первые 3 патча (хелпер + 2 обёртки Modify*FilterRules) совпадают с v1;
    # у билдера условий G сменилась только буква lodash-модуля (o.map→s.map)
    return v1[:3] + [
        ("filter-toggle-v2: скрыть trueTest от билдера условий",
         'if("condition"!==a){const n=t[a];(0,s.map)(n,t=>{e.push({...t,testName:a})})}',
         'if("condition"!==a&&"trueTest"!==a){const n=t[a];(0,s.map)(n,t=>{e.push({...t,testName:a})})}'),
    ]

def build_patches_388_v2():
    return [
        ("40: Добавить module 9999 в chunk",
         # NEW_MODULE не закрывает тело модуля — первая } хвоста закрывает его,
         # вторая — словарь модулей (как в v1-инъекции).
         '"data-testid":"layout-component"}))}}}]);',
         '"data-testid":"layout-component"}))}}' + NEW_MODULE_V2 + '}}]);'),
        ("40: Импорт CF",
         "var x=a(8654),C=a(2765),k=a(7424),A=a(8380),T=a(6750),_=a(1067),M=a(426),S=a(6341),I=a(3932);",
         "var x=a(8654),C=a(2765),k=a(7424),A=a(8380),T=a(6750),_=a(1067),M=a(426),S=a(6341),I=a(3932),CF=a(9999);"),
        ("40: Вызов хука в компоненте",
         "}=(0,C.S)({message:e,shouldReplaceHistory:o}),F=(0,k.W)(T,e.tags),L=(0,n.useMemo)(()=>{const e=[",
         "}=(0,C.S)({message:e,shouldReplaceHistory:o}),F=(0,k.W)(T,e.tags),Q=(0,CF.q)(e),L=(0,n.useMemo)(()=>{const e=["),
        ("40: Добавить пункт в массив действий",
         ',(0,x.A)(P),(0,x.A)(z)].filter(e=>!e.disabled),n={id:"More"',
         ',(0,x.A)(P),(0,x.A)(z),(0,x.A)(Q)].filter(e=>!e.disabled),n={id:"More"'),
        ("40: Добавить Q в зависимости useMemo",
         '},[t,i,m,u,d,h,f,b,E,$,p,w,y,v,A,F,_,M,S,I,R,D,P,z,a]);return l().createElement(r.Row,{mainAlignment:"flex-end"',
         '},[t,i,m,u,d,h,f,b,E,$,p,w,y,v,A,F,_,M,S,I,R,D,P,z,Q,a]);return l().createElement(r.Row,{mainAlignment:"flex-end"'),
    ]

def build_patches_336_v2():
    return [
        ("946: Добавить module 9999 в chunk",
         # см. комментарий в build_patches_388_v2 про незакрытое тело модуля
         "isSharedFolderIncluded:t}}}}]);",
         "isSharedFolderIncluded:t}}}" + NEW_MODULE_V2 + "}}]);"),
        ("946: Импорт CF",
         "var r=a(7559),n=a.n(r),o=a(8153),l=a(5978),i=a(5748),s=a(9826),c=a(9732),d=a(7319),u=a(8751),m=a(4702);",
         "var r=a(7559),n=a.n(r),o=a(8153),l=a(5978),i=a(5748),s=a(9826),c=a(9732),d=a(7319),u=a(8751),m=a(4702),CF=a(9999);"),
        ("946: Вызов хука create-filter",
         "[U]=(0,o.useTranslation)(),Y=(0,r.useMemo)(()=>[",
         "[U]=(0,o.useTranslation)(),Q=(0,CF.q)(e),Y=(0,r.useMemo)(()=>["),
        ("946: Добавить пункт в контекстное меню",
         ',(0,l.A)($),(0,l.A)(B)].filter(e=>!(e.disabled||H&&"ForwardMenu"===e.id))',
         ',(0,l.A)($),(0,l.A)(B),(0,l.A)(Q)].filter(e=>!(e.disabled||H&&"ForwardMenu"===e.id))'),
        ("946: Добавить Q в зависимости useMemo",
         ",[b,v,U,E,A,I,y,x,C,k,T,M,w,z,D,S,R,F,O,L,P,W,$,B,N,H]),G=",
         ",[b,v,U,E,A,I,y,x,C,k,T,M,w,z,D,S,R,F,O,L,P,W,$,B,N,H,Q]),G="),
        ("946: maxHeight 100vh для контекст. меню (ue)",
         'createElement(o.Dropdown,{contextMenu:!0,items:ue,display:"block",style:{width:"100%",height:"4rem"}',
         'createElement(o.Dropdown,{contextMenu:!0,maxHeight:"100vh",items:ue,display:"block",style:{width:"100%",height:"4rem"}'),
        ("946: maxHeight 100vh для g-компонента",
         'createElement(m.Dropdown,{contextMenu:!0,items:e,display:"block",style:{width:"100%",height:"4rem"}',
         'createElement(m.Dropdown,{contextMenu:!0,maxHeight:"100vh",items:e,display:"block",style:{width:"100%",height:"4rem"}'),
    ]

def build_patches_336_color_v2():
    cc_colors_const = f'const CC_COLORS_M={CC_COLORS_JS};const CC_LABELS_M={CC_LABELS_JS};'
    return [
        ("color-v2/946: CC_COLORS_M + CC_LABELS_M",
         'const w=({message:e,selected:t',
         f'{cc_colors_const}const w=({{message:e,selected:t'),
        ("color-v2/946: _hlBg фон строки сообщения",
         '$=(0,r.useMemo)(()=>i?l.noop:u,[i,u]);return n().createElement(o.Container,{mainAlignment:"flex-start",orientation:"horizontal",height:"4rem"},',
         '$=(0,r.useMemo)(()=>i?l.noop:u,[i,u]);'
         'const _hlBg=(0,r.useMemo)(()=>{const t=R.find(s=>CC_LABELS_M.includes(s.name));if(!t)return null;const idx=CC_LABELS_M.indexOf(t.name);return idx>=0?CC_COLORS_M[idx]:null},[R]);'
         'return n().createElement(o.Container,{mainAlignment:"flex-start",orientation:"horizontal",height:"4rem",style:_hlBg?{background:_hlBg}:undefined},'),
        ("color-v2/946: Скрыть CC тег-иконку (компонент s)",
         'd=(0,r.useMemo)(()=>t?.length>1?"TagsMoreOutline":"Tag",[t]),u=(0,r.useMemo)(()=>1===t?.length?t?.[0]?.color:void 0,[t]),m=(0,i.nK)(t),g=(0,r.useMemo)(()=>e.tags&&0!==e.tags.length&&""!==e.tags?.[0]&&m,[m,e.tags])',
         '_t=t?.filter(x=>!CC_LABELS_M.includes(x?.name)),d=(0,r.useMemo)(()=>_t?.length>1?"TagsMoreOutline":"Tag",[_t]),u=(0,r.useMemo)(()=>1===_t?.length?_t?.[0]?.color:void 0,[_t]),m=(0,i.nK)(_t),g=(0,r.useMemo)(()=>_t&&_t.length>0&&m,[m,_t])'),
        ("color-v2/946: Скрыть CC тег-иконку (компонент w)",
         'F=(0,k.nK)(R),O=(0,r.useMemo)(()=>e.tags&&0!==e.tags.length&&""!==e.tags?.[0]&&F,[F,e.tags]),L=(0,r.useMemo)(()=>R.length>1?"TagsMoreOutline":"Tag",[R]),P=(0,r.useMemo)(()=>1===R.length?R[0].color:void 0,[R])',
         '_R=R.filter(x=>!CC_LABELS_M.includes(x?.name)),F=(0,k.nK)(_R),O=(0,r.useMemo)(()=>_R.length>0&&F,[F,_R]),L=(0,r.useMemo)(()=>_R.length>1?"TagsMoreOutline":"Tag",[_R]),P=(0,r.useMemo)(()=>1===_R.length?_R[0].color:void 0,[_R])'),
    ]

def build_patches_fpv_v2():
    cc_colors_const = f'const CC_COLORS_L={CC_COLORS_JS};const CC_LABELS_L={CC_LABELS_JS};'
    return [
        ("color-v2/fpv: CC_COLORS_L + CC_LABELS_L",
         'const P=({conversation:e,selected:t',
         f'{cc_colors_const}const P=({{conversation:e,selected:t'),
        ("color-v2/fpv: _hlBg фон строки беседы",
         'S=(0,s.useMemo)(()=>d?I("label.hide","Hide"):I("label.expand","Expand"),[d,I]);return a().createElement(r.Container,{mainAlignment:"flex-start",orientation:"horizontal",height:"4rem"},',
         'S=(0,s.useMemo)(()=>d?I("label.hide","Hide"):I("label.expand","Expand"),[d,I]);'
         'const _hlBg=(0,s.useMemo)(()=>{const t=f.find(s=>CC_LABELS_L.includes(s.name));if(!t)return null;const idx=CC_LABELS_L.indexOf(t.name);return idx>=0?CC_COLORS_L[idx]:null},[f]);'
         'return a().createElement(r.Container,{mainAlignment:"flex-start",orientation:"horizontal",height:"4rem",style:_hlBg?{background:_hlBg}:undefined},'),
    ]

def build_patches_917_v2():
    return [
        ("app: s.tags||[] guard in TAG/UNTAG optimistic update",
         't===k.qn.TAG&&r?s.tags=[...s.tags,r]:t===k.qn.UNTAG&&r&&(s.tags=(0,l.filter)(s.tags,e=>e!==r))',
         't===k.qn.TAG&&r?s.tags=[...(s.tags||[]),r]:t===k.qn.UNTAG&&r&&(s.tags=(0,l.filter)(s.tags||[],e=>e!==r))'),
    ]

# ─────────────────────────────────────────────────────────────────────────────
# Apply helpers
# ─────────────────────────────────────────────────────────────────────────────

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

# ─────────────────────────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_check():
    variant      = detect_variant()
    print(f"Вариант сборки mails-ui: {variant}")
    chunk388     = find_chunk_388()
    chunk336     = find_chunk_336()
    chunkSetting = find_chunk_settings()
    chunkFpv     = find_chunk_fpv()
    chunk917     = find_chunk_917()
    c388     = read(chunk388)
    c336     = read(chunk336)
    cSetting = read(chunkSetting)
    cFpv     = read(chunkFpv)
    c917     = read(chunk917)

    # create-filter
    ok388      = PATCH_MARKER_388      in c388
    ok336      = PATCH_MARKER_336      in c336
    okSetting  = PATCH_MARKER_SETTINGS in cSetting
    okJy       = ("Jy:()=>j" in cSetting) or ("Jy:()=>ge" in cSetting)
    okS6b      = "useState)(initFld)"  in cSetting
    # S7 (локализация имени папки) есть только в v1 — util VN удалён из 1.34.x
    okS7       = PATCH_MARKER_S7 in cSetting if variant == "v1" else True
    okMaxHeight = ('maxHeight:"100vh",items:de' in c336) or ('maxHeight:"100vh",items:ue' in c336)

    # color-filter
    okCCSettings = CC_MARKER_SETTINGS in cSetting
    okCCLocalize = CC_MARKER_LOCALIZE  in cSetting
    okCC336      = CC_MARKER_336       in c336
    okCCFpv      = CC_MARKER_FPV       in cFpv

    # bugfixes
    ok917        = (PATCH_MARKER_917 in c917) or ("s.tags||[]" in c917)
    okFF         = FF_MARKER_SETTINGS in cSetting and '"trueTest"!==a' in cSetting

    print(f"{'✓' if ok388      else '✗'}  chunk 388      {'применён' if ok388      else 'НЕ применён'}: {chunk388}")
    print(f"{'✓' if ok336      else '✗'}  chunk 336      {'применён' if ok336      else 'НЕ применён'}: {chunk336}")
    print(f"  {'✓' if okMaxHeight else '✗'}  maxHeight 100vh (нет скроллбара): {'да' if okMaxHeight else 'нет'}")
    print(f"{'✓' if okSetting  else '✗'}  chunk settings {'применён' if okSetting  else 'НЕ применён'}: {chunkSetting}")
    print(f"  {'✓' if okJy     else '✗'}  Jy экспорт: {'да' if okJy else 'нет'}")
    print(f"  {'✓' if okS6b    else '✗'}  initFld (Inbox): {'да' if okS6b else 'нет'}")
    print(f"  {'✓' if okS7     else '✗'}  локализация имени папки (S7): {'да' if okS7 else 'нет'}")
    print(f"{'✓' if okCCSettings else '✗'}  color-filter/settings {'применён' if okCCSettings else 'НЕ применён'}")
    print(f"  {'✓' if okCCLocalize else '✗'}  tcc_ локализация Select label: {'да' if okCCLocalize else 'нет'}")
    print(f"{'✓' if okCC336      else '✗'}  color-filter/336      {'применён' if okCC336      else 'НЕ применён'}")
    print(f"{'✓' if okCCFpv      else '✗'}  color-filter/fpv      {'применён' if okCCFpv      else 'НЕ применён'}: {chunkFpv}")
    print(f"{'✓' if ok917        else '✗'}  bugfix/917            {'применён' if ok917        else 'НЕ применён'}: {chunk917}")
    print(f"{'✓' if okFF         else '✗'}  bugfix/filter-toggle  {'применён' if okFF         else 'НЕ применён'} (отключение безусловного фильтра)")
    okRu = cmd_check_json(RU_JSON_PATH, RU_KEYS, "ru")
    okEn = cmd_check_json(EN_JSON_PATH, EN_KEYS, "en")

    return (ok388 and ok336 and okMaxHeight and okSetting and okS7
            and okCCSettings and okCCLocalize and okCC336 and okCCFpv
            and ok917 and okFF and okRu and okEn)


def cmd_install():
    variant      = detect_variant()
    print(f"Вариант сборки mails-ui: {variant}")
    chunk388     = find_chunk_388()
    chunk336     = find_chunk_336()
    chunkSetting = find_chunk_settings()
    chunkFpv     = find_chunk_fpv()

    # ── create-filter: settings chunk ────────────────────────────────────────
    print(f"chunk settings: {chunkSetting}")
    cSetting = read(chunkSetting)

    if variant == "v2":
        if PATCH_MARKER_SETTINGS in cSetting:
            print("chunk settings: create-filter v2 уже применён, пропускаем.")
            appliedSetting = False
        else:
            appliedSetting = _apply_patches(chunkSetting, build_patches_settings_v2(),
                                             PATCH_MARKER_SETTINGS,
                                             "chunk settings: патч уже применён, пропускаем.")
    elif PATCH_MARKER_SETTINGS in cSetting and PATCH_MARKER_S7 in cSetting:
        print("chunk settings: create-filter патч уже применён полностью, пропускаем.")
        appliedSetting = False
    elif PATCH_MARKER_SETTINGS in cSetting and PATCH_MARKER_S7 not in cSetting:
        print("chunk settings: S1-S6 уже применены, применяем S7 (локализация имени папки)...")
        s7_patches = [("settings: Локализовать имя папки в чипе Apply-диалога",
                        'label:g.absFolderPath,hasAvatar:!0',
                        'label:(0,N.VN)({folderName:g.name})||g.absFolderPath,hasAvatar:!0')]
        appliedSetting = _apply_patches(chunkSetting, s7_patches, PATCH_MARKER_S7,
                                         "chunk settings: S7 уже применён.")
    elif "Ae:()=>Ae" in cSetting and "Jy:()=>j" not in cSetting:
        print("chunk settings: S1-S5 уже применены, применяем Jy + S6 + S7...")
        appliedSetting = _apply_patches(chunkSetting, build_patches_settings_incremental(),
                                         PATCH_MARKER_SETTINGS,
                                         "chunk settings: уже полностью применён.")
    else:
        appliedSetting = _apply_patches(chunkSetting, build_patches_settings(),
                                         PATCH_MARKER_SETTINGS,
                                         "chunk settings: патч уже применён полностью, пропускаем.")
    if appliedSetting:
        print(f"✓ chunk settings (create-filter) пропатчен")

    # ── color-filter: settings chunk ─────────────────────────────────────────
    cSetting = read(chunkSetting)
    if CC_MARKER_SETTINGS not in cSetting:
        print("\ncolor-filter/settings: применяем...")
        cc_builder = build_patches_settings_color_v2 if variant == "v2" else build_patches_settings_color
        applied = _apply_patches(chunkSetting, cc_builder(),
                                  CC_MARKER_SETTINGS, "color-filter/settings: уже применён.")
        if applied:
            print("✓ chunk settings (color-filter) пропатчен")
    elif CC_MARKER_LOCALIZE not in cSetting:
        print("\ncolor-filter/settings: добавляем локализацию tcc_...")
        applied = _apply_patches(chunkSetting, build_patches_settings_color_localize(),
                                  CC_MARKER_LOCALIZE, "color-filter/settings: tcc_ уже на месте.")
        if applied:
            print("✓ chunk settings (color-filter локализация) пропатчен")
    else:
        print("color-filter/settings: патч уже применён полностью, пропускаем.")

    # ── bugfix: disable-unconditional-filter (trueTest) on settings chunk ─────
    cSetting = read(chunkSetting)
    if FF_MARKER_SETTINGS not in cSetting:
        print("\nbugfix/filter-toggle: применяем фикс trueTest...")
        ff_builder = build_patches_settings_filterfix_v2 if variant == "v2" else build_patches_settings_filterfix
        applied_ff = _apply_patches(chunkSetting, ff_builder(),
                                     FF_MARKER_SETTINGS, "bugfix/filter-toggle: уже применён.")
        if applied_ff:
            print("✓ chunk settings (фикс отключения безусловного фильтра) пропатчен")
    else:
        print("bugfix/filter-toggle: патч уже применён, пропускаем.")

    # ── create-filter: chunk 388 (v2: 40) ────────────────────────────────────
    print()
    print(f"chunk 388/40: {chunk388}")
    b388 = build_patches_388_v2 if variant == "v2" else build_patches_388
    applied388 = _apply_patches(chunk388, b388(), PATCH_MARKER_388,
                                 "chunk 388/40: патч уже применён, пропускаем.")
    if applied388:
        print(f"✓ chunk 388/40 пропатчен")

    # ── create-filter: chunk 336 (v2: 946) ───────────────────────────────────
    print()
    print(f"chunk 336/946: {chunk336}")
    b336 = build_patches_336_v2 if variant == "v2" else build_patches_336
    applied336 = _apply_patches(chunk336, b336(), PATCH_MARKER_336,
                                 "chunk 336/946: патч уже применён, пропускаем.")
    if applied336:
        print(f"✓ chunk 336/946 пропатчен")

    # Incremental: maxHeight fix for older v1 installs
    c336_now = read(chunk336)
    if variant == "v1" and PATCH_MARKER_336 in c336_now and 'maxHeight:"100vh",items:de' not in c336_now:
        print("\nchunk 336: добавляем maxHeight:100vh (фикс скроллбара контекстного меню)...")
        mh_patches = [
            ("336: maxHeight 100vh для контекст. меню (de)",
             'createElement(o.Dropdown,{contextMenu:!0,items:de,display:"block",style:{width:"100%",height:"4rem"}',
             'createElement(o.Dropdown,{contextMenu:!0,maxHeight:"100vh",items:de,display:"block",style:{width:"100%",height:"4rem"}'),
            ("336: maxHeight 100vh для g-компонента",
             'createElement(m.Dropdown,{contextMenu:!0,items:e,display:"block",style:{width:"100%",height:"4rem"}',
             'createElement(m.Dropdown,{contextMenu:!0,maxHeight:"100vh",items:e,display:"block",style:{width:"100%",height:"4rem"}'),
        ]
        applied_mh = _apply_patches(chunk336, mh_patches, 'maxHeight:"100vh",items:de',
                                     "chunk 336: maxHeight уже применён.")
        if applied_mh:
            print("✓ chunk 336 maxHeight пропатчен")

    # ── color-filter: chunk 336 ───────────────────────────────────────────────
    c336_now = read(chunk336)
    if CC_MARKER_336 not in c336_now:
        print("\ncolor-filter/336: применяем...")
        bc336 = build_patches_336_color_v2 if variant == "v2" else build_patches_336_color
        applied = _apply_patches(chunk336, bc336(), CC_MARKER_336,
                                  "color-filter/336: уже применён.")
        if applied:
            print("✓ chunk 336 (color-filter) пропатчен")
    else:
        print("color-filter/336: патч уже применён, пропускаем.")

    # ── color-filter: folder-panel-view ──────────────────────────────────────
    print()
    print(f"chunk folder-panel-view: {chunkFpv}")
    cFpv = read(chunkFpv)
    if CC_MARKER_FPV not in cFpv:
        bfpv = build_patches_fpv_v2 if variant == "v2" else build_patches_fpv
        applied_fpv = _apply_patches(chunkFpv, bfpv(), CC_MARKER_FPV,
                                      "color-filter/fpv: уже применён.")
        if applied_fpv:
            print("✓ chunk folder-panel-view (color-filter) пропатчен")
    else:
        print("color-filter/fpv: патч уже применён, пропускаем.")

    # ── bugfix: 917 chunk ─────────────────────────────────────────────────────
    chunk917 = find_chunk_917()
    print()
    print(f"chunk 917 (bugfix): {chunk917}")
    c917 = read(chunk917)
    marker917 = "s.tags||[]" if variant == "v2" else PATCH_MARKER_917
    if marker917 not in c917:
        b917 = build_patches_917_v2 if variant == "v2" else build_patches_917
        applied_917 = _apply_patches(chunk917, b917(), marker917,
                                      "bugfix/917: уже применён.")
        if applied_917:
            print("✓ chunk 917 (bugfix i.tags) пропатчен")
    else:
        print("bugfix/917: патч уже применён, пропускаем.")

    # ── i18n ──────────────────────────────────────────────────────────────────
    print()
    print("ru.json:")
    cmd_patch_json(RU_JSON_PATH, RU_KEYS, "ru")
    print("en.json:")
    cmd_patch_json(EN_JSON_PATH, EN_KEYS, "en")

    print("\n✓ Готово. Обновите страницу браузера (Ctrl+Shift+R).")
    print("  Доступны:")
    print("  1. «Создать фильтр» в тулбаре и right-click меню")
    print("  2. Действие «Выделять цветом» в редакторе фильтров")


def cmd_rollback():
    cmd_rollback_json(RU_JSON_PATH, "ru")
    cmd_rollback_json(EN_JSON_PATH, "en")
    for find_fn, label in [
        (find_chunk_settings, "chunk settings"),
        (find_chunk_388,      "chunk 388"),
        (find_chunk_336,      "chunk 336"),
        (find_chunk_fpv,      "chunk folder-panel-view"),
        (find_chunk_917,      "chunk 917"),
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
        ok = cmd_check()
        sys.exit(0 if ok else 1)
    elif arg == "rollback":
        cmd_rollback()
    elif arg == "install":
        cmd_install()
    else:
        print(__doc__)
        sys.exit(1)
