"""Fal.ai-Seedream5-Layers-To-Save-PSD GUI.

layerize JSON을 붙여넣고 Run을 누르면 make_psd.build_psd로 PSD를 생성한다.
사양은 GUI_SPEC.md 참조.
"""

import json
import locale
import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, font as tkfont, ttk

from make_psd import __version__, build_psd

STRINGS = {
    'en': {
        'title': 'Fal.ai-Seedream5-Layers-To-Save-PSD',
        'lang_label': 'Language:',
        'json_label': 'Layerize JSON:',
        'out_folder': 'Output folder:',
        'browse': 'Browse…',
        'file_name': 'File name:',
        'gen_layers': 'Export layer PNGs folder (<name>.psd_layers)',
        'run': 'Run',
        'running': 'Running…',
        'status_ready': 'Ready.',
        'invalid_json': 'Invalid JSON: {}',
        'no_layers': 'JSON has no "layers" list.',
        'bad_name': 'File name must not contain a path.',
        'bad_folder': 'Cannot create output folder: {}',
        'done': 'Done: {}',
        'error': 'Error: {}',
    },
    'ko': {
        'title': 'Fal.ai-Seedream5-Layers-To-Save-PSD',
        'lang_label': '언어:',
        'json_label': 'Layerize JSON:',
        'out_folder': '출력 폴더:',
        'browse': '찾아보기…',
        'file_name': '파일 이름:',
        'gen_layers': '레이어 PNG 폴더 내보내기 (<이름>.psd_layers)',
        'run': '실행',
        'running': '실행 중…',
        'status_ready': '준비됨.',
        'invalid_json': '잘못된 JSON: {}',
        'no_layers': 'JSON에 "layers" 리스트가 없다.',
        'bad_name': '파일 이름에 경로를 넣을 수 없다.',
        'bad_folder': '출력 폴더를 만들 수 없다: {}',
        'done': '완료: {}',
        'error': '오류: {}',
    },
    'ja': {
        'title': 'Fal.ai-Seedream5-Layers-To-Save-PSD',
        'lang_label': '言語:',
        'json_label': 'Layerize JSON:',
        'out_folder': '出力フォルダ:',
        'browse': '参照…',
        'file_name': 'ファイル名:',
        'gen_layers': 'レイヤーPNGフォルダを出力 (<名前>.psd_layers)',
        'run': '実行',
        'running': '実行中…',
        'status_ready': '準備完了。',
        'invalid_json': '無効なJSON: {}',
        'no_layers': 'JSONに "layers" リストがありません。',
        'bad_name': 'ファイル名にパスを含めることはできません。',
        'bad_folder': '出力フォルダを作成できません: {}',
        'done': '完了: {}',
        'error': 'エラー: {}',
    },
}
LANG_NAMES = {'English': 'en', '한국어': 'ko', '日本語': 'ja'}

MODEL_LINK_TEXT = 'fal.ai › Seedream 5 Pro Layerize ↗'
MODEL_LINK_URL = 'https://fal.ai/models/bytedance/seedream/v5/pro/layerize'

MONO_FONT = ('Consolas' if sys.platform == 'win32' else 'Menlo', 10)


def resource_path(name: str) -> Path:
    return Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / name


def default_folder() -> Path:
    """기본 출력 폴더. 원칙은 cwd — 탐색기 더블클릭 시 cwd가 exe 폴더가 되므로
    두 경우 모두 커버된다. 단 바로가기 등으로 cwd가 시스템 폴더에 떨어지는
    frozen exe만 exe 폴더로 폴백한다."""
    cwd = Path.cwd()
    if getattr(sys, 'frozen', False):
        windir = Path(os.environ.get('WINDIR', r'C:\Windows'))
        if cwd == windir or windir in cwd.parents:
            return Path(sys.executable).parent
    return cwd


def default_lang() -> str:
    loc = (locale.getdefaultlocale()[0] or '').lower()
    for code in ('ko', 'ja'):
        if loc.startswith(code):
            return code
    return 'en'


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.lang = default_lang()
        self.q: queue.Queue = queue.Queue()
        self.running = False

        icon = resource_path('icon.png')
        if icon.exists():
            root.iconphoto(True, tk.PhotoImage(file=str(icon)))
        root.minsize(560, 640)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        pad = {'padx': 8, 'pady': 4}

        # 최상단: 모델 페이지 바로가기 링크
        link_font = tkfont.nametofont('TkDefaultFont').copy()
        link_font.configure(underline=True)
        link = ttk.Label(
            root, text=MODEL_LINK_TEXT, foreground='#0066cc',
            font=link_font, cursor='hand2',
        )
        link.grid(row=0, column=0, sticky='w', padx=8, pady=(6, 0))
        link.bind('<Button-1>', lambda e: webbrowser.open(MODEL_LINK_URL))

        # 상단: 언어 선택
        top = ttk.Frame(root)
        top.grid(row=1, column=0, sticky='ew', **pad)
        self.lang_label = ttk.Label(top)
        self.lang_label.pack(side='left')
        self.lang_combo = ttk.Combobox(
            top, state='readonly', width=10, values=list(LANG_NAMES)
        )
        self.lang_combo.set(
            next(k for k, v in LANG_NAMES.items() if v == self.lang)
        )
        self.lang_combo.bind('<<ComboboxSelected>>', self.on_lang)
        self.lang_combo.pack(side='left', padx=6)

        # JSON 영역 (stretch, mono 폰트)
        jf = ttk.Frame(root)
        jf.grid(row=2, column=0, sticky='nsew', **pad)
        jf.columnconfigure(0, weight=1)
        jf.rowconfigure(1, weight=1)
        self.json_label = ttk.Label(jf)
        self.json_label.grid(row=0, column=0, sticky='w')
        self.json_text = tk.Text(jf, font=MONO_FONT, wrap='none', undo=True)
        self.json_text.grid(row=1, column=0, sticky='nsew')
        sb = ttk.Scrollbar(jf, command=self.json_text.yview)
        sb.grid(row=1, column=1, sticky='ns')
        self.json_text.configure(yscrollcommand=sb.set)

        # 출력 폴더 / 파일명 / 토글
        form = ttk.Frame(root)
        form.grid(row=3, column=0, sticky='ew', **pad)
        form.columnconfigure(1, weight=1)
        self.out_label = ttk.Label(form)
        self.out_label.grid(row=0, column=0, sticky='w')
        self.folder_var = tk.StringVar(value=str(default_folder()))
        ttk.Entry(form, textvariable=self.folder_var).grid(
            row=0, column=1, sticky='ew', padx=6
        )
        self.browse_btn = ttk.Button(form, command=self.on_browse)
        self.browse_btn.grid(row=0, column=2)
        self.name_label = ttk.Label(form)
        self.name_label.grid(row=1, column=0, sticky='w', pady=(4, 0))
        self.name_var = tk.StringVar(value='output.psd')
        ttk.Entry(form, textvariable=self.name_var).grid(
            row=1, column=1, sticky='ew', padx=6, pady=(4, 0)
        )
        self.gen_var = tk.BooleanVar(value=True)
        self.gen_check = ttk.Checkbutton(form, variable=self.gen_var)
        self.gen_check.grid(row=2, column=0, columnspan=3, sticky='w', pady=(4, 0))

        # Run 버튼
        self.run_btn = ttk.Button(root, command=self.on_run)
        self.run_btn.grid(row=4, column=0, sticky='e', **pad)

        # Status 로그 (read-only 4줄)
        self.status = tk.Text(
            root, height=4, state='disabled', font='TkDefaultFont', wrap='word'
        )
        self.status.grid(row=5, column=0, sticky='ew', **pad)
        self.status.tag_configure('ok', foreground='#008000')
        self.status.tag_configure('err', foreground='#c00000')

        # 최하단 버전 표기
        ttk.Label(root, text=f'v{__version__}', foreground='#888888').grid(
            row=6, column=0, sticky='e', padx=8, pady=(0, 4)
        )

        self.apply_language()
        self.log(self.tr('status_ready'))
        root.after(100, self.poll)

    # --- i18n ---
    def tr(self, key: str) -> str:
        return STRINGS[self.lang][key]

    def on_lang(self, _event=None) -> None:
        self.lang = LANG_NAMES[self.lang_combo.get()]
        self.apply_language()

    def apply_language(self) -> None:
        self.root.title(f'{self.tr("title")} v{__version__}')
        self.lang_label.configure(text=self.tr('lang_label'))
        self.json_label.configure(text=self.tr('json_label'))
        self.out_label.configure(text=self.tr('out_folder'))
        self.browse_btn.configure(text=self.tr('browse'))
        self.name_label.configure(text=self.tr('file_name'))
        self.gen_check.configure(text=self.tr('gen_layers'))
        self.run_btn.configure(
            text=self.tr('running') if self.running else self.tr('run')
        )

    # --- status log (메인 스레드 전용) ---
    def log(self, msg: str, tag: str | None = None) -> None:
        self.status.configure(state='normal')
        self.status.insert('end', msg + '\n', tag or ())
        self.status.see('end')
        self.status.configure(state='disabled')

    # --- actions ---
    def on_browse(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.folder_var.get())
        if folder:
            self.folder_var.set(folder)

    def on_run(self) -> None:
        if self.running:
            return
        try:
            data = json.loads(self.json_text.get('1.0', 'end'))
        except json.JSONDecodeError as e:
            self.log(self.tr('invalid_json').format(e), 'err')
            return
        if not isinstance(data, dict) or not isinstance(data.get('layers'), list):
            self.log(self.tr('no_layers'), 'err')
            return
        name = self.name_var.get().strip() or 'output.psd'
        if Path(name).name != name:
            self.log(self.tr('bad_name'), 'err')
            return
        if not name.lower().endswith('.psd'):
            name += '.psd'
        folder = Path(self.folder_var.get().strip() or '.')
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.log(self.tr('bad_folder').format(e), 'err')
            return

        self.running = True
        self.run_btn.configure(state='disabled', text=self.tr('running'))
        threading.Thread(
            target=self.worker,
            args=(data, folder / name, self.gen_var.get()),
            daemon=True,
        ).start()

    def worker(self, data: dict, output: Path, gen_layers: bool) -> None:
        # tkinter 위젯 접근 금지 — 큐로만 보고한다
        try:
            result = build_psd(
                data, output, gen_layers, progress=lambda m: self.q.put(('msg', m))
            )
            self.q.put(('done', str(result)))
        except Exception as e:  # 네트워크·파일 오류 등 무엇이든 status로
            self.q.put(('error', f'{type(e).__name__}: {e}'))

    def poll(self) -> None:
        try:
            while True:
                kind, msg = self.q.get_nowait()
                if kind == 'msg':
                    self.log(msg)
                elif kind == 'done':
                    self.log(self.tr('done').format(msg), 'ok')
                    self.finish()
                else:
                    self.log(self.tr('error').format(msg), 'err')
                    self.finish()
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def finish(self) -> None:
        self.running = False
        self.run_btn.configure(state='normal', text=self.tr('run'))


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
