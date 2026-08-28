import uuid
import time
import json
import sqlite3
from typing import Dict, List
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

# ==============================================================================
# 0. 資料庫初始化模組
# ==============================================================================
DB_FILE = "lanyang_food_hazard.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vendor_records (
        record_id TEXT PRIMARY KEY,
        submit_time TEXT,
        issuing_unit TEXT,
        worker_count INTEGER,
        project_name TEXT,
        project_location TEXT,
        contractor_name TEXT,
        owner_name TEXT,
        supervisor_name TEXT,
        hazards TEXT,
        sig_owner TEXT,
        sig_supervisor TEXT,
        sig_safety TEXT,
        status TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

app = FastAPI()

# ==============================================================================
# 1. 資料傳輸物件 (Pydantic Models)
# ==============================================================================
class SubmitFormRequest(BaseModel):
    issuing_unit: str
    worker_count: int
    project_name: str
    project_location: str
    contractor_name: str
    owner_name: str
    sig_owner: str

class ApproveFormRequest(BaseModel):
    record_id: str
    sig_safety: str

class UpdateFormRequest(BaseModel):
    record_id: str
    issuing_unit: str
    worker_count: int
    contractor_name: str
    project_name: str
    project_location: str

FOOD_HAZARD_RULES_DB = {
    "跌倒、滑倒危害": [
        "1. 食品廠地面常有水漬或油污，施工人員應穿著防滑安全鞋。",
        "2. 施工區域周圍應設置防滑告示牌，濕滑區域應即時清理或鋪設防滑墊。"
    ],
    "高溫與蒸氣燙傷": [
        "1. 接觸高溫蒸氣管線、殺菌釜或熱水洗滌管道前，必須確認管線溫度或關閉閥門洩壓。",
        "2. 需配戴耐高溫隔熱手套與防護面罩，嚴禁於運作中之高溫設備上方盲目作業。"
    ],
    "低溫與凍傷受困": [
        "1. 進入冷凍/冷藏庫作業前，需先通知廠方登記，並確認庫門防鎖死安全機制正常。",
        "2. 穿著足夠保暖衣物，並採雙人夥同作業，設有時間限制與定時報平安機制。"
    ],
    "夾捲與機械危害": [
        "1. 自動化輸送帶、包裝機、攪拌機維修時，必須嚴格執行 LOTO（上鎖掛牌）與斷電防護。",
        "2. 禁止取下防護罩作業，操作時不得配戴寬鬆衣物或飾品。"
    ],
    "局限空間與缺氧": [
        "1. 進入儲料槽、發酵桶、調配罐或廢水池前，必須先進行氣體檢測（氧氣及有害氣體）。",
        "2. 實施強制通風換氣，並於人孔外配置專人監視與救援裝備。"
    ],
    "感電危害": [
        "1. 食品廠環境潮濕，使用之移動式電動工具必須連接漏電斷路器。",
        "2. 嚴禁手部潮濕直接插拔電源，電線不得拖拉於積水地面。"
    ],
    "化學品中毒與灼傷": [
        "1. CIP 自動清洗系統區（含強酸強鹼清潔劑）作業，需配戴防護面罩、橡膠手套與防酸鹼圍裙。",
        "2. 氨氣/冷媒管線維修需配戴合適之防毒面具，並確認緊急洗眼器功能正常。"
    ],
    "高空墜落危害": [
        "1. 於高位管道、儲槽頂端或2公尺以上高處作業，必須全程繫妥安全帶並掛載於穩固錨定點。",
        "2. 使用合梯時需有止滑裝置，且需有第二人在旁監視協助。"
    ]
}

# ==============================================================================
# 2. API 路由與網頁渲染
# ==============================================================================
@app.get("/vendor-entry", response_class=HTMLResponse)
def get_vendor_entry_page():
    hazards_list = list(FOOD_HAZARD_RULES_DB.keys())
    hazards_display = "".join([f'<div class="hazard-card"><b>⚠️ {hz}</b></div>' for hz in hazards_list])

    rules_html = ""
    for hz, rules in FOOD_HAZARD_RULES_DB.items():
        rules_html += f"<div style='font-weight:bold; color:#0056b3; margin-top:8px;'>【{hz}】</div><ul>"
        for r in rules:
            rules_html += f"<li>{r}</li>"
        rules_html += "</ul>"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>蘭揚食品危害告知書</title>
        <script src="https://cdn.jsdelivr.net/npm/signature_pad@4.1.7/dist/signature_pad.umd.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 12px; max-width: 650px; margin: auto; background: #f4f6f9; }}
            .box {{ border: 1px solid #e1e4e8; padding: 20px; border-radius: 12px; background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
            h2 {{ text-align: center; color: #2c3e50; margin-top: 0; border-bottom: 2px solid #28a745; padding-bottom: 8px; font-size: 20px; }}
            .section-title {{ background: #28a745; color: white; padding: 6px 10px; border-radius: 4px; font-weight: bold; margin-top: 15px; font-size: 14px; }}
            .hazard-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px; }}
            .hazard-card {{ background: #fff3cd; border: 1px solid #ffeeba; color: #856404; padding: 8px 12px; border-radius: 6px; font-size: 13px; text-align: center; }}
            .rules-container {{ border: 1px solid #ddd; padding: 12px; background: #fafafa; border-radius: 6px; font-size: 13px; line-height: 1.5; margin-top: 8px; max-height: 220px; overflow-y: scroll; }}
            .rules-container ul {{ padding-left: 18px; margin: 4px 0; color: #444; }}
            .sig-box {{ border: 2px dashed #28a745; border-radius: 8px; height: 180px; background: #fff; margin-top: 5px; touch-action: none; }}
            canvas {{ width: 100%; height: 100%; }}
            .form-group {{ margin-top: 12px; }}
            label {{ display: block; font-weight: bold; margin-bottom: 4px; font-size: 13px; }}
            input[type="text"], input[type="number"] {{ width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 6px; font-size: 14px; }}
            button {{ padding: 12px; font-size: 16px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; }}
            .submit-btn {{ background: #28a745; color: white; margin-top: 20px; }}
            .clear-btn {{ background: #6c757d; color: white; padding: 6px 12px; font-size: 12px; margin-top: 6px; float: left; width: auto; border-radius: 4px; }}
            .chk-item {{ display: flex; align-items: flex-start; gap: 8px; padding: 8px; border-bottom: 1px solid #f0f0f0; font-size: 13px; }}
            .chk-item input[type="checkbox"] {{ width: 18px; height: 18px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="box">
            <h2>蘭揚食品危害告知書</h2>
            
            <div class="section-title">一、請填寫本日進廠施工資訊</div>
            <div class="form-group"><label>發包單位/人員 *</label><input type="text" id="issuing_unit" placeholder="例如：總務部 / 王小明"></div>
            <div class="form-group"><label>承攬廠商名稱 *</label><input type="text" id="contractor_name" placeholder="例如：大安工程有限公司"></div>
            <div class="form-group"><label>施工作業名稱 *</label><input type="text" id="project_name" placeholder="例如：A區冷凍庫風扇維修"></div>
            <div class="form-group"><label>施工地點 / 車間 *</label><input type="text" id="project_location" placeholder="例如：B棟 2樓 充填室"></div>
            <div class="form-group"><label>作業人數 (人) *</label><input type="number" id="worker_count" min="1" value="1"></div>

            <div class="section-title">二、廠區潛在危害因素告知</div>
            <div class="hazard-grid">{hazards_display}</div>

            <div class="section-title">三、工安與食品衛生(GHP)防範對策</div>
            <div class="rules-container">{rules_html}</div>
            
            <div class="chk-item" style="background:#e8f4f8; margin-top:8px; border-radius:6px;">
                <input type="checkbox" id="chk_promise">
                <label for="chk_promise"><b>我已詳閱職業安全與食品衛生(GHP)防範對策，並承諾恪守規定，若造成人員傷害或食品污染願負完全責任。</b></label>
            </div>

            <div class="section-title" style="background:#007bff;">四、進場人員手寫簽章</div>
            <div class="form-group">
                <label>承攬人經營負責人或代理人 姓名與簽章 *</label>
                <input type="text" id="owner_name" placeholder="請輸入 姓名" style="margin-bottom:6px;">
                <div class="sig-box"><canvas id="canvas-owner"></canvas></div>
                <button type="button" class="clear-btn" onclick="padOwner.clear()">重簽</button>
            </div>

            <button type="button" class="submit-btn" style="clear:both;" onclick="submitForm()">確認回傳表單 (送至廠方職安審核)</button>
        </div>

        <script>
            const padOwner = new SignaturePad(document.getElementById('canvas-owner'));
            let lastWidth = window.innerWidth;

            function resizeCanvases() {{
                if (window.innerWidth === lastWidth && padOwner.toData().length > 0) return;
                lastWidth = window.innerWidth;
                const c = padOwner.canvas;
                const ratio = Math.max(window.devicePixelRatio || 1, 1);
                const data = padOwner.toData();
                c.width = c.offsetWidth * ratio;
                c.height = c.offsetHeight * ratio;
                c.getContext("2d").scale(ratio, ratio);
                padOwner.clear();
                padOwner.fromData(data);
            }}
            window.addEventListener("resize", resizeCanvases);
            resizeCanvases();

            async function submitForm() {{
                const issuingUnit = document.getElementById('issuing_unit').value.trim();
                const workerCount = parseInt(document.getElementById('worker_count').value) || 1;
                const contractor = document.getElementById('contractor_name').value.trim();
                const project = document.getElementById('project_name').value.trim();
                const location = document.getElementById('project_location').value.trim();
                const owner = document.getElementById('owner_name').value.trim();

                if (!issuingUnit || !contractor || !project || !location || !owner || workerCount <= 0) {{
                    alert('請完整填寫各項資訊！');
                    return;
                }}
                if (!document.getElementById('chk_promise').checked) {{
                    alert('請勾選同意遵守承諾！');
                    return;
                }}
                if (padOwner.isEmpty()) {{
                    alert('請完成手寫簽名！');
                    return;
                }}

                const response = await fetch('/api/submit-vendor-form', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        issuing_unit: issuingUnit,
                        worker_count: workerCount,
                        project_name: project,
                        project_location: location,
                        contractor_name: contractor,
                        owner_name: owner,
                        sig_owner: padOwner.toDataURL()
                    }})
                }});

                if (response.ok) {{
                    document.body.innerHTML = '<div class="box" style="text-align:center;"><h2 style="color:#28a745;">✓ 危害告知單已成功回傳</h2><p>已傳送至廠方職安管理系統。</p></div>';
                }} else {{
                    alert('送出失敗，請稍後再試。');
                }}
            }}
        </script>
    </body>
    </html>
    """

@app.post("/api/submit-vendor-form")
def submit_vendor_form(req: SubmitFormRequest):
    record_id = str(uuid.uuid4())[:8]
    submit_time = time.strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO vendor_records (record_id, submit_time, issuing_unit, worker_count, project_name, project_location, contractor_name, owner_name, supervisor_name, hazards, sig_owner, sig_supervisor, sig_safety, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, '', '', '待職安簽核')
    """, (
        record_id, submit_time, req.issuing_unit, req.worker_count,
        req.project_name, req.project_location, req.contractor_name,
        req.owner_name, json.dumps(list(FOOD_HAZARD_RULES_DB.keys()), ensure_ascii=False),
        req.sig_owner
    ))
    conn.commit()
    conn.close()
    return {"status": "success", "record_id": record_id}

@app.post("/api/approve-form")
def approve_form(req: ApproveFormRequest):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE vendor_records SET sig_safety = ?, status = '已簽核結案' WHERE record_id = ?", (req.sig_safety, req.record_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/update-record")
def update_record(req: UpdateFormRequest):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE vendor_records 
    SET issuing_unit = ?, worker_count = ?, contractor_name = ?, project_name = ?, project_location = ?
    WHERE record_id = ?
    """, (req.issuing_unit, req.worker_count, req.contractor_name, req.project_name, req.project_location, req.record_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/api/delete-record/{record_id}")
def delete_record(record_id: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vendor_records WHERE record_id = ?", (record_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/records")
def get_records():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vendor_records ORDER BY submit_time DESC")
    rows = cursor.fetchall()
    conn.close()
    
    records_dict = {}
    for r in rows:
        item = dict(r)
        item['hazards'] = json.loads(item['hazards']) if item['hazards'] else []
        records_dict[item['record_id']] = item
    return records_dict

# ==============================================================================
# 重點修復：view-record 憑證網頁 HTML/CSS 乾淨排版
# ==============================================================================
@app.get("/view-record/{record_id}", response_class=HTMLResponse)
def view_record_page(record_id: str):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vendor_records WHERE record_id = ?", (record_id,))
    rec_row = cursor.fetchone()
    conn.close()

    if not rec_row:
        return "<h3>紀錄不存在</h3>"
    
    rec = dict(rec_row)
    rec['hazards'] = json.loads(rec['hazards']) if rec['hazards'] else []

    rules_html = ""
    for hz in rec['hazards']:
        if hz in FOOD_HAZARD_RULES_DB:
            rules_html += f"<div style='font-weight:bold; color:#0056b3; margin-top:4px; font-size:11px;'>【{hz} 應採取之防範對策】</div><ul style='margin:1px 0 4px 0; padding-left:16px; font-size:10px; line-height:1.3;'>"
            for rule in FOOD_HAZARD_RULES_DB[hz]:
                rules_html += f"<li>{rule}</li>"
            rules_html += "</ul>"

    safety_sig_html = f"<img src='{rec['sig_safety']}' class='sig-img'>" if rec.get('sig_safety') else "&nbsp;"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>蘭揚食品危害告知書 - 稽核憑證</title>
        <style>
            @page {{ size: A4; margin: 10mm; }}
            * {{ box-sizing: border-box; font-family: "Microsoft JhengHei", "微軟正黑體", sans-serif; }}
            
            /* 清除背景定位與多餘屬性 */
            html, body {{ background: #f0f2f5; margin: 0; padding: 0; }}
            body {{ padding: 10px; margin: auto; max-width: 780px; color: #333; }}
            
            /* 主容器：採用標準 block 排版，高度自由流動 */
            .paper {{ background: white; padding: 20px 25px; border-radius: 6px; border: 1px solid #ccc; display: block; }}
            
            h1 {{ text-align: center; font-size: 18px; color: #1a365d; border-bottom: 2px solid #28a745; padding-bottom: 6px; margin: 0 0 12px 0; }}
            
            table {{ width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 11px; }}
            td, th {{ border: 1px solid #333; padding: 5px 8px; vertical-align: middle; }}
            th {{ background: #e2e8f0; font-weight: bold; text-align: left; }}
            
            .tag {{ display: inline-block; background: #28a745; color: white; padding: 2px 6px; border-radius: 3px; margin: 1px; font-size: 10px; }}
            .sig-img {{ height: 50px; max-width: 100%; object-fit: contain; display: block; margin: auto; }}
            
            /* 中間條文框：明確取消 position: absolute 與 overflow 固定 */
            .rules-box {{ 
                border: 1px solid #ccc; 
                padding: 8px 12px; 
                background: #fafafa; 
                border-radius: 4px; 
                margin-top: 6px; 
                margin-bottom: 25px; 
                display: block; 
                position: static !important; 
                clear: both;
            }}
            
            /* 標題段落：給予足夠頂部間距，絕不上疊 */
            .section-title-h3 {{ 
                margin-top: 20px !important; 
                margin-bottom: 6px !important; 
                font-size: 12px; 
                font-weight: bold; 
                display: block; 
                clear: both; 
            }}
            
            .print-btn {{ display: block; width: 100%; padding: 10px; background: #28a745; color: white; border: none; font-size: 14px; font-weight: bold; border-radius: 4px; cursor: pointer; margin-top: 20px; text-align: center; }}
            
            @media print {{ 
                .print-btn {{ display: none !important; }} 
                body {{ background: white; padding: 0; margin: 0; max-width: 100%; }} 
                .paper {{ box-shadow: none; border: none; padding: 0; }} 
            }}
        </style>
    </head>
    <body>
        <div class="paper">
            <h1>蘭揚食品危害告知書 (稽核憑證)</h1>
            
            <table>
                <tr>
                    <td width="15%"><b>回傳時間</b></td><td width="35%">{rec['submit_time']}</td>
                    <td width="15%"><b>簽核狀態</b></td><td width="35%"><b>{rec['status']}</b></td>
                </tr>
                <tr>
                    <td><b>發包單位/人員</b></td><td>{rec.get('issuing_unit', '')}</td>
                    <td><b>作業人數</b></td><td>{rec.get('worker_count', 1)} 人</td>
                </tr>
                <tr>
                    <td><b>承攬廠商</b></td><td colspan="3"><b>{rec['contractor_name']}</b></td>
                </tr>
                <tr>
                    <td><b>作業名稱</b></td><td colspan="3"><b>{rec['project_name']}</b></td>
                </tr>
                <tr>
                    <td><b>施工地點/車間</b></td><td colspan="3">{rec['project_location']}</td>
                </tr>
                <tr>
                    <td><b>告知危害因素</b></td>
                    <td colspan="3">
                        """ + "".join([f"<span class='tag'>✓ {hz}</span>" for hz in rec['hazards']]) + f"""
                    </td>
                </tr>
            </table>

            <div class="section-title-h3" style="color:#0056b3;">工安與食品衛生(GHP)對策 (已詳閱同意)</div>
            <div class="rules-box">
                {rules_html}
            </div>

            <div class="section-title-h3" style="color:#28a745;">雙方簽署審核留痕</div>
            <table>
                <tr>
                    <th width="50%">1. 承攬人經營負責人或代理人 簽章</th>
                    <th width="50%" style="background:#d4edda;">2. 廠方職安簽核</th>
                </tr>
                <tr>
                    <td align="center" style="height: 70px;">
                        <div style="font-size: 11px; margin-bottom: 2px;"><b>{rec['owner_name']}</b></div>
                        <img src="{rec['sig_owner']}" class="sig-img">
                    </td>
                    <td align="center" style="background:#f8f9fa; height: 70px;">
                        {safety_sig_html}
                    </td>
                </tr>
            </table>

            <button class="print-btn" onclick="window.print()">列印 / 存檔</button>
        </div>
    </body>
    </html>
    """
