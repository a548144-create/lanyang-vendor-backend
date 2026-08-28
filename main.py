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

    # 完整條文以雙欄式組合，大幅節省垂直高度
    rules_items = []
    for hz in rec['hazards']:
        if hz in FOOD_HAZARD_RULES_DB:
            item_html = f"<div style='margin-bottom:4px;'><b style='color:#0056b3; font-size:10.5px;'>【{hz}】</b><ul style='margin:1px 0; padding-left:14px; font-size:9.5px; color:#333; line-height:1.25;'>"
            for rule in FOOD_HAZARD_RULES_DB[hz]:
                item_html += f"<li>{rule}</li>"
            item_html += "</ul></div>"
            rules_items.append(item_html)

    # 拆分為左右兩欄
    half = (len(rules_items) + 1) // 2
    left_col = "".join(rules_items[:half])
    right_col = "".join(rules_items[half:])

    safety_sig_html = f"<img src='{rec['sig_safety']}' class='sig-img'>" if rec.get('sig_safety') else "&nbsp;"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>蘭揚食品危害告知書 - 稽核憑證</title>
        <style>
            @page {{ size: A4; margin: 8mm; }}
            * {{ box-sizing: border-box; font-family: "Microsoft JhengHei", "微軟正黑體", sans-serif; }}
            body {{ padding: 0; margin: auto; max-width: 760px; background: #f0f2f5; color: #333; font-size: 11px; }}
            .paper {{ background: white; padding: 20px 25px; border-radius: 6px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); border: 1px solid #ccc; }}
            h1 {{ text-align: center; font-size: 18px; color: #1a365d; border-bottom: 2px solid #28a745; padding-bottom: 4px; margin: 0 0 8px 0; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 4px; font-size: 11px; }}
            td, th {{ border: 1px solid #333; padding: 4px 6px; vertical-align: middle; }}
            th {{ background: #e2e8f0; font-weight: bold; text-align: left; }}
            .tag {{ display: inline-block; background: #28a745; color: white; padding: 1px 6px; border-radius: 3px; margin: 1px; font-size: 10px; }}
            .sig-img {{ height: 50px; max-width: 100%; object-fit: contain; display: block; margin: auto; }}
            .rules-box {{ border: 1px solid #ccc; padding: 6px 10px; background: #fafafa; border-radius: 4px; display: flex; gap: 12px; margin-top: 3px; }}
            .rules-col {{ flex: 1; min-width: 0; }}
            .section-h3 {{ margin: 8px 0 3px 0; font-size: 11.5px; font-weight: bold; }}
            .print-btn {{ display: block; width: 100%; padding: 8px; background: #28a745; color: white; border: none; font-size: 13px; font-weight: bold; border-radius: 4px; cursor: pointer; margin-top: 10px; text-align: center; }}
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
                    <td width="15%"><b>簽核狀態</b></td><td width="34%"><b>{rec['status']}</b></td>
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

            <h3 class="section-h3" style="color:#0056b3;">工安與食品衛生(GHP)對策 (已詳閱同意)</h3>
            <div class="rules-box">
                <div class="rules-col">{left_col}</div>
                <div class="rules-col">{right_col}</div>
            </div>

            <h3 class="section-h3" style="color:#28a745;">雙方簽署審核留痕</h3>
            <table>
                <tr>
                    <th width="50%">1. 承攬人經營負責人或代理人 簽章</th>
                    <th width="50%" style="background:#d4edda;">2. 廠方職安簽核</th>
                </tr>
                <tr>
                    <td align="center" style="height: 70px;">
                        <div style="font-size: 10.5px; margin-bottom: 2px;"><b>{rec['owner_name']}</b></div>
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
