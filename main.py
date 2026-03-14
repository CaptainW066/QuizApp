import flet as ft
import re
import random

def main(page: ft.Page):
    # App 基础设置
    page.title = "刷题神器 App"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 400
    page.window_height = 800
    page.padding = 0
    page.scroll = ft.ScrollMode.ADAPTIVE

    # 使用字典管理全局状态，彻底消除 nonlocal 语法错误风险
    state = {
        "banks": page.client_storage.get("mobile_quiz_banks") or {},
        "selected_banks": {},
        "all_questions": [],
        "quiz_questions": [],
        "current_idx": 0,
        "user_answers": {},
        "user_selected_texts": {}
    }
    
    # 初始化选中状态
    for b in state["banks"].keys():
        state["selected_banks"][b] = True

    def save_banks():
        page.client_storage.set("mobile_quiz_banks", state["banks"])

    # --- 数据解析逻辑 (与桌面版核心一致) ---
    def parse_text_to_bank(text, bank_name):
        parsed_list = []
        text = re.sub(r'[•\r]', '', text)
        pattern = r'(?:^|\n)\s*(\d+)\s*[、\.]?\s*【(.*?)】(.*?)(?=\n\s*\d+\s*[、\.]?\s*【|$)'
        matches = re.finditer(pattern, text, re.DOTALL)
        
        for m in matches:
            q_num = m.group(1)
            q_type = m.group(2).strip()
            block = m.group(3).strip()
            options, ans = {}, ""
            q_text = block
            
            ans_match = re.search(r'正确答案：\s*([A-Za-z]+|[对错√×]|正确|错误)', block)
            if ans_match:
                ans_raw = ans_match.group(1).upper()
                q_text = re.split(r'\n?\s*正确答案', block)[0].strip()
            else:
                ans_match2 = re.search(r'[\(（]\s*([A-Za-z]+|[对错√×]|正确|错误)\s*[）\)]', block)
                if ans_match2:
                    ans_raw = ans_match2.group(1).upper()
                    q_text = re.sub(r'[\(（]\s*([A-Za-z]+|[对错√×]|正确|错误)\s*[）\)]', '(  )', q_text) 
                else: continue 

            if ans_raw in ['对', '√', 'T', '正确']: ans = 'A'
            elif ans_raw in ['错', '×', 'F', '错误']: ans = 'B'
            else: ans = "".join(sorted(ans_raw))

            if '判断' in q_type:
                options = {'A': '正确', 'B': '错误'}
                q_text = re.split(r'\n?\s*[A-B][、\.．）\)\s]', q_text)[0].strip()
            else:
                opts_text = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
                for i, opt in enumerate(opts_text):
                    next_opt = opts_text[i+1] if i+1 < len(opts_text) else None
                    if next_opt: opt_pattern = rf'{opt}[、\.．）\)](.*?)(?=\s*{next_opt}[、\.．）\)]|$)'
                    else: opt_pattern = rf'{opt}[、\.．）\)](.*?)(?=$)'
                    opt_match = re.search(opt_pattern, q_text, re.DOTALL)
                    if opt_match: options[opt] = opt_match.group(1).strip()
                q_text = re.split(r'\n?\s*A[、\.．）\)]', q_text)[0].strip()
                if not options: continue
                    
            parsed_list.append({
                'num': q_num, 'type': q_type, 'question': q_text,
                'options': options, 'answer': ans
            })
        
        if parsed_list:
            state["banks"][bank_name] = parsed_list
            state["selected_banks"][bank_name] = True
            save_banks()
            return len(parsed_list)
        return 0

    # --- 界面构建逻辑 ---
    def show_snack(msg, color=ft.colors.GREEN):
        page.snack_bar = ft.SnackBar(ft.Text(msg, color=ft.colors.WHITE), bgcolor=color)
        page.snack_bar.open = True
        page.update()

    def on_file_picked(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            file_path = e.files[0].path
            bank_name = e.files[0].name.replace(".txt", "")
            try:
                with open(file_path, 'r', encoding='utf-8') as f: text = f.read()
            except:
                try:
                    with open(file_path, 'r', encoding='gbk') as f: text = f.read()
                except:
                    show_snack("文件读取失败！", ft.colors.RED)
                    return
            
            count = parse_text_to_bank(text, bank_name)
            if count > 0:
                show_snack(f"成功导入 {count} 道题！")
                build_menu_view()
            else:
                show_snack("未识别到题目，请检查格式！", ft.colors.RED)

    file_picker = ft.FilePicker(on_result=on_file_picked)
    page.overlay.append(file_picker)

    # 1. 首页菜单视图
    def build_menu_view():
        def toggle_bank(e, b_name):
            state["selected_banks"][b_name] = e.control.value
            update_total_qs()
            
        def delete_bank(b_name):
            if b_name in state["banks"]: del state["banks"][b_name]
            if b_name in state["selected_banks"]: del state["selected_banks"][b_name]
            save_banks()
            build_menu_view()
            show_snack("题库已删除", ft.colors.BLUE)

        bank_list_controls = []
        total_q = 0
        if not state["banks"]:
            bank_list_controls.append(ft.Text("暂无题库，请点击上方按钮导入 txt 文件", color=ft.colors.GREY))
        else:
            for b_name, qs in state["banks"].items():
                total_q += len(qs)
                row = ft.Row([
                    ft.Checkbox(label=f"{b_name} ({len(qs)}题)", value=state["selected_banks"].get(b_name, True), 
                                on_change=lambda e, b=b_name: toggle_bank(e, b), expand=True),
                    ft.IconButton(icon=ft.icons.DELETE, icon_color="red", on_click=lambda e, b=b_name: delete_bank(b))
                ])
                bank_list_controls.append(row)

        lbl_total = ft.Text(f"当前题库总题数: {total_q}", weight=ft.FontWeight.BOLD, color=ft.colors.BLUE)
        
        num_qs_dropdown = ft.Dropdown(
            label="本次抽题数量",
            options=[ft.dropdown.Option("10"), ft.dropdown.Option("20"), ft.dropdown.Option("50"), ft.dropdown.Option("100")],
            value="50" if total_q >= 50 else str(total_q) if total_q > 0 else "10",
            width=200
        )

        def update_total_qs():
            t = sum([len(state["banks"][b]) for b, v in state["selected_banks"].items() if v and b in state["banks"]])
            lbl_total.value = f"已选中题库供抽取: {t} 题"
            page.update()

        def on_start_click(e):
            state["all_questions"] = []
            for b_name, is_selected in state["selected_banks"].items():
                if is_selected and b_name in state["banks"]:
                    state["all_questions"].extend(state["banks"][b_name])
                    
            if not state["all_questions"]:
                show_snack("请至少勾选一个包含题目的题库！", ft.colors.RED)
                return
            
            try: sample_size = int(num_qs_dropdown.value)
            except: sample_size = 50
            
            sample_size = min(sample_size, len(state["all_questions"]))
            if sample_size <= 0: return
            
            state["quiz_questions"] = random.sample(state["all_questions"], sample_size)
            state["current_idx"] = 0
            state["user_answers"].clear()
            state["user_selected_texts"].clear()
            build_quiz_view()

        menu_view = ft.SafeArea(
            ft.Column([
                ft.Text("刷题神器", size=30, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE),
                ft.Divider(),
                ft.ElevatedButton("📁 导入 TXT 题库", icon=ft.icons.UPLOAD_FILE, on_click=lambda _: file_picker.pick_files(allowed_extensions=["txt"]), width=float('inf'), height=50),
                ft.Container(height=20),
                ft.Text("本地题库列表", size=18, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=ft.Column(bank_list_controls, scroll=ft.ScrollMode.AUTO),
                    height=250, border=ft.border.all(1, ft.colors.OUTLINE), border_radius=10, padding=10
                ),
                ft.Container(height=10),
                lbl_total,
                num_qs_dropdown,
                ft.Container(height=20),
                ft.ElevatedButton("▶ 开始沉浸式刷题", bgcolor=ft.colors.GREEN, color=ft.colors.WHITE, width=float('inf'), height=55, on_click=on_start_click)
            ], spacing=10, expand=True)
        )
        page.views.clear()
        page.views.append(ft.View("/", [menu_view], padding=20))
        page.update()

    # 2. 答题视图
    def build_quiz_view():
        if state["current_idx"] >= len(state["quiz_questions"]):
            build_result_view()
            return
            
        q = state["quiz_questions"][state["current_idx"]]
        is_multi = '多选' in q['type']
        opt_keys = sorted(q['options'].keys())
        
        progress_val = state["current_idx"] / len(state["quiz_questions"])
        pb = ft.ProgressBar(value=progress_val, color=ft.colors.BLUE, bgcolor=ft.colors.BLUE_100)
        
        q_title = ft.Text(f"{state['current_idx'] + 1}/{len(state['quiz_questions'])}. 【{q['type']}】", color=ft.colors.BLUE_700, weight=ft.FontWeight.BOLD)
        q_text = ft.Text(q['question'], size=18)
        
        options_column = ft.Column(spacing=15)
        opt_controls = {}
        cg = ft.RadioGroup(content=options_column) if not is_multi else None

        for opt in opt_keys:
            text_label = f"{opt}、{q['options'][opt]}"
            if is_multi:
                cb = ft.Checkbox(label=text_label, value=False)
                options_column.controls.append(cb)
                opt_controls[opt] = cb
            else:
                rd = ft.Radio(value=opt, label=text_label)
                options_column.controls.append(rd)
                opt_controls[opt] = rd

        feedback_text = ft.Text("", size=16, weight=ft.FontWeight.BOLD)
        
        btn_submit = ft.ElevatedButton("提交答案", bgcolor=ft.colors.BLUE, color=ft.colors.WHITE, expand=True, height=50)
        btn_next = ft.ElevatedButton("下一题", bgcolor=ft.colors.ORANGE, color=ft.colors.WHITE, expand=True, height=50, disabled=True)
        btn_prev = ft.OutlinedButton("上一题", expand=True, height=50, disabled=(state["current_idx"]==0))

        def on_submit(e):
            correct_ans = q['answer']
            if is_multi:
                selected_list = [opt for opt, cb in opt_controls.items() if cb.value]
                selected = "".join(sorted(selected_list))
            else:
                selected = cg.value if cg else None
                
            if not selected:
                show_snack("请至少选择一个选项！", ft.colors.RED)
                return
                
            if is_multi:
                for cb in opt_controls.values(): cb.disabled = True
            else:
                for rd in opt_controls.values(): rd.disabled = True
                
            is_correct = (selected == correct_ans)
            state["user_answers"][state["current_idx"]] = is_correct
            state["user_selected_texts"][state["current_idx"]] = selected
            
            if is_correct:
                feedback_text.value = "✔ 回答正确！"
                feedback_text.color = ft.colors.GREEN
            else:
                feedback_text.value = f"✖ 回答错误！正确答案是: {correct_ans}"
                feedback_text.color = ft.colors.RED
                
            btn_submit.disabled = True
            btn_next.disabled = False
            page.update()

        def on_next(e):
            state["current_idx"] += 1
            build_quiz_view()

        def on_prev(e):
            if state["current_idx"] > 0:
                state["current_idx"] -= 1
                build_quiz_view()

        btn_submit.on_click = on_submit
        btn_next.on_click = on_next
        btn_prev.on_click = on_prev
        
        action_row = ft.Row([btn_prev, btn_submit, btn_next], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        quiz_view = ft.SafeArea(
            ft.Column([
                pb,
                ft.Container(height=10),
                q_title,
                q_text,
                ft.Divider(),
                ft.Container(content=cg if cg else options_column, expand=True), 
                feedback_text,
                ft.Container(height=10),
                action_row
            ], expand=True)
        )
        
        if state["current_idx"] in state["user_answers"]:
            btn_submit.disabled = True
            btn_next.disabled = False
            prev_sel = state["user_selected_texts"].get(state["current_idx"], "")
            if is_multi:
                for cb in opt_controls.values(): cb.disabled = True
                for s in prev_sel: 
                    if s in opt_controls: opt_controls[s].value = True
            else:
                for rd in opt_controls.values(): rd.disabled = True
                if cg: cg.value = prev_sel
            
            if state["user_answers"][state["current_idx"]]:
                feedback_text.value = "✔ 回答正确！"; feedback_text.color = ft.colors.GREEN
            else:
                feedback_text.value = f"✖ 回答错误！正确答案是: {q['answer']}"; feedback_text.color = ft.colors.RED

        page.views.clear()
        page.views.append(ft.View("/quiz", [quiz_view], padding=20))
        page.update()

    # 3. 成绩与错题回顾视图
    def build_result_view():
        score = sum(state["user_answers"].values())
        total = len(state["quiz_questions"])
        percentage = (score / total) * 100 if total > 0 else 0
        
        def show_egg():
            if percentage < 60:
                dlg = ft.AlertDialog(title=ft.Text("😭 完蛋了完蛋了！(不及格)", color=ft.colors.RED))
            else:
                dlg = ft.AlertDialog(title=ft.Text("🎉 老哥牛逼老哥牛逼！", color=ft.colors.GREEN))
            page.dialog = dlg
            dlg.open = True
            page.update()

        lbl_title = ft.Text(f"测试完成！得分: {score} / {total}", size=24, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE)
        
        wrong_list = []
        for idx, correct in state["user_answers"].items():
            if not correct:
                q = state["quiz_questions"][idx]
                u_ans = state["user_selected_texts"].get(idx, "未选")
                c_ans = q['answer']
                
                card = ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text(f"第 {idx+1} 题. 【{q['type']}】 {q['question']}", size=15),
                            ft.Text(f"你的答案: {u_ans}  |  正确答案: {c_ans}", color=ft.colors.RED, weight=ft.FontWeight.BOLD)
                        ]), padding=10
                    )
                )
                wrong_list.append(card)

        content_column = ft.Column([lbl_title, ft.Divider()], spacing=10)
        
        if not wrong_list:
            content_column.controls.append(ft.Text("太棒了！全对！🎉", size=20, color=ft.colors.GREEN))
        else:
            content_column.controls.append(ft.Text("📑 错题回顾：", size=18, color=ft.colors.RED))
            content_column.controls.append(
                ft.Container(content=ft.Column(wrong_list, scroll=ft.ScrollMode.AUTO), expand=True)
            )

        btn_home = ft.ElevatedButton("返回主页", icon=ft.icons.HOME, width=float('inf'), height=50, on_click=lambda _: build_menu_view())
        content_column.controls.append(btn_home)

        res_view = ft.SafeArea(ft.Container(content=content_column, expand=True))
        
        page.views.clear()
        page.views.append(ft.View("/result", [res_view], padding=20))
        page.update()
        
        import threading
        threading.Timer(0.5, show_egg).start()

    build_menu_view()

if __name__ == '__main__':
    ft.app(target=main)
