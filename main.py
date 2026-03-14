import flet as ft
import re
import random
import traceback 

def main(page: ft.Page):
    try:
        # App 基础设置与高级 UI 主题
        page.title = "刷题神器"
        page.theme_mode = ft.ThemeMode.LIGHT
        # 启用 Material 3 设计语言，以蓝色为主色调
        page.theme = ft.Theme(color_scheme_seed=ft.colors.BLUE, use_material3=True)
        page.padding = 0
        page.bgcolor = ft.colors.GREY_100 # 浅灰背景反衬白色卡片
        page.scroll = ft.ScrollMode.ADAPTIVE

        # 安全读取本地存储数据
        try:
            stored_banks = page.client_storage.get("mobile_quiz_banks")
            if not isinstance(stored_banks, dict):
                stored_banks = {}
        except Exception:
            stored_banks = {}

        # 全局状态管理
        state = {
            "banks": stored_banks,
            "selected_banks": {},
            "all_questions": [],
            "quiz_questions": [],
            "current_idx": 0,
            "user_answers": {},
            "user_selected_texts": {}
        }
        
        for b in state["banks"].keys():
            state["selected_banks"][b] = True

        def save_banks():
            try:
                page.client_storage.set("mobile_quiz_banks", state["banks"])
            except Exception as e:
                print(f"保存失败: {e}")

        # --- 核心题库解析逻辑 (保持不变) ---
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

        # --- 底部弹窗提示 (SnackBar) ---
        def show_snack(msg, is_error=False):
            color = ft.colors.ERROR if is_error else ft.colors.GREEN_700
            page.snack_bar = ft.SnackBar(
                content=ft.Text(msg, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD), 
                bgcolor=color,
                behavior=ft.SnackBarBehavior.FLOATING,
                margin=20
            )
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
                        show_snack("文件读取失败！", True)
                        return
                
                count = parse_text_to_bank(text, bank_name)
                if count > 0:
                    show_snack(f"成功导入 {count} 道题！")
                    build_menu_view()
                else:
                    show_snack("未识别到题目，请检查格式！", True)

        file_picker = ft.FilePicker(on_result=on_file_picked)
        page.overlay.append(file_picker)

        # ==========================================
        # 1. 首页菜单视图 (高颜值重构)
        # ==========================================
        def build_menu_view():
            def toggle_bank(e, b_name):
                state["selected_banks"][b_name] = e.control.value
                update_total_qs()
                
            def delete_bank(b_name):
                if b_name in state["banks"]: del state["banks"][b_name]
                if b_name in state["selected_banks"]: del state["selected_banks"][b_name]
                save_banks()
                build_menu_view()
                show_snack("题库已删除", False)

            bank_list_controls = []
            total_q = 0
            if not state["banks"]:
                bank_list_controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.icons.INBOX, size=50, color=ft.colors.GREY_400),
                            ft.Text("题库空空如也\n点击上方按钮导入 txt 文件", text_align=ft.TextAlign.CENTER, color=ft.colors.GREY_500)
                        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=40, alignment=ft.alignment.center
                    )
                )
            else:
                for b_name, qs in state["banks"].items():
                    total_q += len(qs)
                    # 每一项做成圆角小卡片，防误触
                    row = ft.Container(
                        content=ft.Row([
                            ft.Checkbox(label=f"{b_name}\n({len(qs)}题)", value=state["selected_banks"].get(b_name, True), 
                                        on_change=lambda e, b=b_name: toggle_bank(e, b), expand=True, label_style=ft.TextStyle(size=15)),
                            ft.IconButton(icon=ft.icons.DELETE_OUTLINE, icon_color=ft.colors.RED_400, on_click=lambda e, b=b_name: delete_bank(b))
                        ]),
                        padding=ft.padding.symmetric(horizontal=10, vertical=5),
                        border_radius=10,
                        bgcolor=ft.colors.SURFACE_VARIANT
                    )
                    bank_list_controls.append(row)

            lbl_total = ft.Text(f"当前题库总题数: {total_q}", weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_700, size=16)
            
            num_qs_dropdown = ft.Dropdown(
                label="本次随机抽题量",
                options=[ft.dropdown.Option("10"), ft.dropdown.Option("20"), ft.dropdown.Option("50"), ft.dropdown.Option("100")],
                value="50" if total_q >= 50 else str(total_q) if total_q > 0 else "10",
                width=200,
                border_radius=10
            )

            def update_total_qs():
                t = sum([len(state["banks"][b]) for b, v in state["selected_banks"].items() if v and b in state["banks"]])
                lbl_total.value = f"已勾选题目池: {t} 题"
                page.update()

            def on_start_click(e):
                state["all_questions"] = []
                for b_name, is_selected in state["selected_banks"].items():
                    if is_selected and b_name in state["banks"]:
                        state["all_questions"].extend(state["banks"][b_name])
                        
                if not state["all_questions"]:
                    show_snack("请至少勾选一个包含题目的题库！", True)
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

            # 首页的 App 原生顶栏
            app_bar = ft.AppBar(
                title=ft.Text("刷题神器", weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
                center_title=True,
                bgcolor=ft.colors.BLUE,
                elevation=2
            )

            # 导入按钮设计
            import_btn = ft.ElevatedButton(
                content=ft.Row([ft.Icon(ft.icons.UPLOAD_FILE), ft.Text("导入 TXT 题库", size=18, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.CENTER),
                style=ft.ButtonStyle(
                    color=ft.colors.WHITE,
                    bgcolor=ft.colors.BLUE_600,
                    shape=ft.RoundedRectangleBorder(radius=15),
                    padding=15
                ),
                on_click=lambda _: file_picker.pick_files(allowed_extensions=["txt"]),
                width=float('inf')
            )

            menu_view = ft.View(
                "/",
                appbar=app_bar,
                bgcolor=ft.colors.GREY_100,
                padding=20,
                controls=[
                    import_btn,
                    ft.Container(height=10),
                    # 本地题库卡片
                    ft.Card(
                        elevation=2,
                        surface_tint_color=ft.colors.WHITE,
                        content=ft.Container(
                            padding=20,
                            content=ft.Column([
                                ft.Row([ft.Icon(ft.icons.LIBRARY_BOOKS, color=ft.colors.BLUE), ft.Text("本地题库", size=18, weight=ft.FontWeight.BOLD)]),
                                ft.Divider(),
                                ft.Container(
                                    content=ft.Column(bank_list_controls, scroll=ft.ScrollMode.AUTO, spacing=8),
                                    height=250
                                )
                            ])
                        )
                    ),
                    ft.Container(height=10),
                    # 设置区域卡片
                    ft.Card(
                        elevation=2,
                        surface_tint_color=ft.colors.WHITE,
                        content=ft.Container(
                            padding=20,
                            content=ft.Column([
                                lbl_total,
                                ft.Container(height=5),
                                num_qs_dropdown
                            ])
                        )
                    ),
                    ft.Container(expand=True), # 占位推到底部
                    # 底部固定的大尺寸开始按钮
                    ft.ElevatedButton(
                        content=ft.Row([ft.Icon(ft.icons.PLAY_ARROW_ROUNDED, size=28), ft.Text("开始刷题", size=20, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.CENTER),
                        style=ft.ButtonStyle(
                            color=ft.colors.WHITE,
                            bgcolor=ft.colors.GREEN_600,
                            shape=ft.RoundedRectangleBorder(radius=30), # 胶囊形状
                            padding=20
                        ),
                        on_click=on_start_click,
                        width=float('inf')
                    )
                ]
            )
            page.views.clear()
            page.views.append(menu_view)
            page.update()

        # ==========================================
        # 2. 答题视图 (卡片化，大字号优化)
        # ==========================================
        def build_quiz_view():
            if state["current_idx"] >= len(state["quiz_questions"]):
                build_result_view()
                return
                
            q = state["quiz_questions"][state["current_idx"]]
            is_multi = '多选' in q['type']
            opt_keys = sorted(q['options'].keys())
            
            # 顶栏：显示进度
            app_bar = ft.AppBar(
                title=ft.Text(f"进度 {state['current_idx'] + 1} / {len(state['quiz_questions'])}", size=18, color=ft.colors.WHITE),
                center_title=True,
                bgcolor=ft.colors.BLUE,
                leading=ft.IconButton(icon=ft.icons.CLOSE, icon_color=ft.colors.WHITE, on_click=lambda _: build_menu_view()) # 退出按钮
            )
            
            progress_val = state["current_idx"] / len(state["quiz_questions"])
            pb = ft.ProgressBar(value=progress_val, color=ft.colors.GREEN, bgcolor=ft.colors.BLUE_100, height=5)
            
            # 题目卡片
            q_title = ft.Text(f"【{q['type']}】", color=ft.colors.BLUE_700, weight=ft.FontWeight.BOLD, size=16)
            q_text = ft.Text(q['question'], size=18, weight=ft.FontWeight.W_500)
            
            options_column = ft.Column(spacing=15)
            opt_controls = {}
            cg = ft.RadioGroup(content=options_column) if not is_multi else None

            # 放大的选项区域
            for opt in opt_keys:
                text_label = f"{opt}、{q['options'][opt]}"
                if is_multi:
                    cb = ft.Checkbox(label=text_label, value=False, label_style=ft.TextStyle(size=16))
                    options_column.controls.append(cb)
                    opt_controls[opt] = cb
                else:
                    rd = ft.Radio(value=opt, label=text_label, label_style=ft.TextStyle(size=16))
                    options_column.controls.append(rd)
                    opt_controls[opt] = rd

            feedback_text = ft.Text("", size=18, weight=ft.FontWeight.BOLD)
            
            # 底部按钮区 (左右布局优化)
            btn_submit = ft.ElevatedButton("提交答案", bgcolor=ft.colors.BLUE_600, color=ft.colors.WHITE, expand=True, height=50, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=15)))
            btn_next = ft.ElevatedButton("下一题", bgcolor=ft.colors.GREEN_600, color=ft.colors.WHITE, expand=True, height=50, disabled=True, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=15)))
            btn_prev = ft.OutlinedButton("上一题", expand=True, height=50, disabled=(state["current_idx"]==0), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=15)))

            def on_submit(e):
                correct_ans = q['answer']
                if is_multi:
                    selected_list = [opt for opt, cb in opt_controls.items() if cb.value]
                    selected = "".join(sorted(selected_list))
                else:
                    selected = cg.value if cg else None
                    
                if not selected:
                    show_snack("请至少选择一个选项！", True)
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
                    feedback_text.color = ft.colors.GREEN_600
                else:
                    feedback_text.value = f"✖ 回答错误！正确答案是: {correct_ans}"
                    feedback_text.color = ft.colors.RED_600
                    
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
            
            action_row = ft.Row([btn_prev, btn_submit, btn_next], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=15)

            quiz_view = ft.View(
                "/quiz",
                appbar=app_bar,
                bgcolor=ft.colors.GREY_100,
                padding=0, # 外层无内边距，为了让进度条贴紧
                controls=[
                    pb,
                    ft.Container(
                        padding=20,
                        expand=True,
                        content=ft.Column([
                            # 题目与选项包裹在卡片中
                            ft.Card(
                                elevation=2,
                                surface_tint_color=ft.colors.WHITE,
                                content=ft.Container(
                                    padding=20,
                                    content=ft.Column([
                                        q_title,
                                        ft.Container(height=5),
                                        q_text,
                                        ft.Divider(height=30, color=ft.colors.GREY_200),
                                        ft.Container(content=cg if cg else options_column, expand=True), 
                                    ])
                                )
                            ),
                            ft.Container(height=10),
                            # 结果反馈区
                            ft.Container(
                                content=feedback_text,
                                alignment=ft.alignment.center,
                                padding=10
                            ),
                            ft.Container(expand=True),
                            # 底部操作栏
                            action_row,
                            ft.Container(height=10) # 底部留白防遮挡
                        ])
                    )
                ]
            )
            
            # 如果是返回上一题，恢复其状态
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
                    feedback_text.value = "✔ 回答正确！"; feedback_text.color = ft.colors.GREEN_600
                else:
                    feedback_text.value = f"✖ 回答错误！正确答案是: {q['answer']}"; feedback_text.color = ft.colors.RED_600

            page.views.clear()
            page.views.append(quiz_view)
            page.update()

        # ==========================================
        # 3. 成绩单与错题回顾 (优雅布局)
        # ==========================================
        def build_result_view():
            score = sum(state["user_answers"].values())
            total = len(state["quiz_questions"])
            percentage = (score / total) * 100 if total > 0 else 0
            
            app_bar = ft.AppBar(
                title=ft.Text("测试结果", weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
                center_title=True,
                bgcolor=ft.colors.BLUE,
            )
            
            def show_egg():
                if percentage < 60:
                    dlg = ft.AlertDialog(title=ft.Text("😭 需要继续努力！(不及格)", color=ft.colors.RED_600))
                else:
                    dlg = ft.AlertDialog(title=ft.Text("🎉 成绩不错！继续保持！", color=ft.colors.GREEN_600))
                page.dialog = dlg
                dlg.open = True
                page.update()

            # 顶部大分数值
            score_card = ft.Container(
                content=ft.Column([
                    ft.Text("你的得分", size=16, color=ft.colors.GREY_600),
                    ft.Text(f"{score} / {total}", size=45, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_600),
                    ft.Text(f"正确率 {percentage:.1f}%", size=16, color=ft.colors.GREEN_600 if percentage >= 60 else ft.colors.RED_600)
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.alignment.center,
                padding=30,
                bgcolor=ft.colors.WHITE,
                border_radius=15,
                shadow=ft.BoxShadow(spread_radius=1, blur_radius=5, color=ft.colors.GREY_300)
            )
            
            wrong_list = []
            for idx, correct in state["user_answers"].items():
                if not correct:
                    q = state["quiz_questions"][idx]
                    u_ans = state["user_selected_texts"].get(idx, "未选")
                    c_ans = q['answer']
                    
                    # 错题解析精美卡片
                    card = ft.Card(
                        elevation=1,
                        surface_tint_color=ft.colors.WHITE,
                        margin=ft.margin.only(bottom=10),
                        content=ft.Container(
                            padding=15,
                            content=ft.Column([
                                ft.Text(f"第 {idx+1} 题. 【{q['type']}】", color=ft.colors.BLUE_600, weight=ft.FontWeight.BOLD),
                                ft.Text(q['question'], size=15),
                                ft.Divider(color=ft.colors.GREY_200),
                                ft.Row([
                                    ft.Text("你的答案: ", size=14, color=ft.colors.GREY_600),
                                    ft.Text(f"{u_ans}", size=14, color=ft.colors.RED_500, weight=ft.FontWeight.BOLD),
                                    ft.Container(width=20),
                                    ft.Text("正确答案: ", size=14, color=ft.colors.GREY_600),
                                    ft.Text(f"{c_ans}", size=14, color=ft.colors.GREEN_600, weight=ft.FontWeight.BOLD)
                                ])
                            ])
                        )
                    )
                    wrong_list.append(card)

            content_column = ft.Column([score_card, ft.Container(height=20)], spacing=10, expand=True)
            
            if not wrong_list:
                content_column.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.icons.EMOJI_EVENTS, size=60, color=ft.colors.AMBER_500),
                            ft.Text("太棒了！全对！🎉", size=22, color=ft.colors.AMBER_600, weight=ft.FontWeight.BOLD)
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        alignment=ft.alignment.center,
                        expand=True
                    )
                )
            else:
                content_column.controls.append(ft.Text("📑 错题回顾：", size=18, color=ft.colors.RED_500, weight=ft.FontWeight.BOLD))
                content_column.controls.append(
                    ft.Container(content=ft.Column(wrong_list, scroll=ft.ScrollMode.AUTO), expand=True)
                )

            btn_home = ft.ElevatedButton(
                content=ft.Row([ft.Icon(ft.icons.HOME), ft.Text("返回首页", size=18)], alignment=ft.MainAxisAlignment.CENTER),
                style=ft.ButtonStyle(
                    color=ft.colors.WHITE, bgcolor=ft.colors.BLUE_600,
                    shape=ft.RoundedRectangleBorder(radius=25), padding=15
                ),
                width=float('inf'),
                on_click=lambda _: build_menu_view()
            )
            content_column.controls.append(ft.Container(height=10))
            content_column.controls.append(btn_home)

            res_view = ft.View(
                "/result",
                appbar=app_bar,
                bgcolor=ft.colors.GREY_100,
                padding=20,
                controls=[content_column]
            )
            
            page.views.clear()
            page.views.append(res_view)
            page.update()
            
            import threading
            threading.Timer(0.6, show_egg).start()

        # 一切准备就绪，加载首页
        build_menu_view()

    # 万一出错了，拦截错误输出到屏幕上
    except Exception as e:
        error_msg = traceback.format_exc()
        error_view = ft.View(
            "/error",
            padding=20,
            controls=[
                ft.SafeArea(
                    ft.Column([
                        ft.Icon(ft.icons.ERROR_OUTLINE, size=60, color=ft.colors.RED),
                        ft.Text("🚨 哎呀，程序崩溃了", color=ft.colors.RED, size=24, weight=ft.FontWeight.BOLD),
                        ft.Text("请截屏以下代码发送给开发者以供修复：", color=ft.colors.GREY_700),
                        ft.Divider(),
                        ft.Text(f"错误简述: {e}", color=ft.colors.RED_700, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            content=ft.Text(error_msg, size=11, color=ft.colors.RED_400),
                            bgcolor=ft.colors.RED_50, border=ft.border.all(1, ft.colors.RED_200),
                            padding=10, border_radius=8, expand=True
                        )
                    ], expand=True)
                )
            ]
        )
        page.views.clear()
        page.views.append(error_view)
        page.update()

if __name__ == '__main__':
    ft.app(target=main)
