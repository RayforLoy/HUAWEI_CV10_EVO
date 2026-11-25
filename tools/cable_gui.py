"""Windows desktop interface for the CV10 cable firmware tool."""
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from threading import Lock, Thread
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from types import SimpleNamespace

import cable
from cable_monitor import Monitor


def status():
    with cable.cable_reader() as read:
        return cable.probe(read)


def version(raw):
    tag, major, minor, patch = bytes.fromhex(raw)
    return f'{tag:X}{major:X}.{minor:X}.{patch:X}'


class Window:
    def __init__(self, root):
        self.root = root
        self.busy = False
        self.results = Queue()
        self.backup = None
        root.title('CV10 连接线工具')
        root.minsize(630, 390)
        self.device_lock = Lock()
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill='both', expand=True)
        panel = ttk.Frame(self.tabs, padding=22)
        diagnostics = ttk.Frame(self.tabs)
        self.tabs.add(panel, text='固件管理')
        self.tabs.add(diagnostics, text='连接线诊断')
        self.monitor = Monitor(diagnostics, self.device_lock)
        self.tabs.bind('<<NotebookTabChanged>>', self.tab_changed)
        ttk.Label(panel, text='请将一根原厂连接线单独接入电脑。操作期间请保持连接。').pack(anchor='w', pady=(5, 16))
        bar = ttk.Frame(panel)
        bar.pack(fill='x')
        self.buttons = []
        for label, action in [('读取状态', self.probe), ('导出固件…', self.dump), ('烧录固件…', self.flash)]:
            button = ttk.Button(bar, text=label, command=action)
            button.pack(side='left', padx=(0, 9))
            self.buttons.append(button)
        self.state = tk.StringVar(value='就绪')
        ttk.Label(panel, textvariable=self.state).pack(anchor='w', pady=(15, 3))
        self.progress = ttk.Progressbar(panel, mode='indeterminate')
        self.progress.pack(fill='x')
        self.log = tk.Text(panel, width=76, height=12, wrap='word', padx=8, pady=8, state='disabled')
        self.log.pack(fill='both', expand=True, pady=(12, 0))
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.probe()

    def tab_changed(self, event):
        self.monitor.set_active(self.tabs.index('current') == 1)

    def close(self):
        if self.busy:
            messagebox.showinfo('操作进行中', '请等操作结束后再关闭窗口。', parent=self.root)
        else:
            self.root.destroy()

    def note(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text + '\n\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def run(self, label, action, done):
        if self.busy:
            return
        self.busy = True
        self.tabs.tab(1, state='disabled')
        self.state.set(label)
        for button in self.buttons:
            button.state(['disabled'])
        self.progress.start(14)

        def worker():
            try:
                with self.device_lock:
                    result = action()
                self.results.put((True, result))
            except Exception as exc:
                self.results.put((False, str(exc)))

        def poll():
            try:
                ok, result = self.results.get_nowait()
            except Empty:
                self.root.after(100, poll)
                return
            self.progress.stop()
            self.busy = False
            self.tabs.tab(1, state='normal')
            for button in self.buttons:
                button.state(['!disabled'])
            if ok:
                self.state.set('完成')
                done(result)
            else:
                self.state.set('操作未完成')
                if 'found 0' in result:
                    result = '未检测到连接线。请重新连接，再点击“读取状态”。'
                self.note(result)

        Thread(target=worker, daemon=True).start()
        self.root.after(100, poll)

    def probe(self):
        def show(info):
            mode = '运行态' if info['mode'] == 'runtime' else 'ROM 维护模式'
            self.note(f"{info['manufacturer']}  ·  {info['product']}\nUSB  {info['vid_pid']}    "
                      f"固件  {version(info['version_raw'])}    模式  {mode}")
        self.run('正在读取设备状态…', status, show)

    def dump(self):
        name = 'CV10-cable-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.bin'
        selected = filedialog.asksaveasfilename(parent=self.root, title='保存连接线固件',
                    initialfile=name, defaultextension='.bin', filetypes=[('固件镜像', '*.bin')])
        if not selected:
            return
        dest = Path(selected)
        if dest.exists():
            messagebox.showinfo('文件已存在', '请选择新的文件名，以保留原备份。', parent=self.root)
            return

        def done(result):
            self.backup = dest
            self.note(f"导出成功，两次读取一致。\n{dest}\n版本  {version(result['version_raw'])}    "
                      f"{result['bytes']:,} 字节    CRC-16  {result['crc16_usb']}\nSHA-256  {result['sha256']}")
        args = SimpleNamespace(file=dest, maintenance=True, fwupdtool=None)
        self.run('正在读取两遍并校验固件…', lambda: cable.export(args), done)

    def flash(self):
        common = dict(parent=self.root, filetypes=[('固件镜像', '*.bin')])
        target = filedialog.askopenfilename(title='选择同板型的待烧录固件', **common)
        if not target:
            return
        hint = dict(initialdir=str(self.backup.parent), initialfile=self.backup.name) if self.backup else {}
        backup = filedialog.askopenfilename(title='选择当前这根线的原始备份', **hint, **common)
        if not backup:
            return
        args = SimpleNamespace(file=Path(target), backup=Path(backup), apply=False)

        def preview(result):
            meta = result['candidate']
            diff = result['differing_sectors']
            self.note(f"预检完成：{target}\n候选版本  {version(meta['version_raw'])}    "
                      f"差异扇区  {diff}\nSHA-256  {meta['sha256']}")
            if not diff:
                self.state.set('固件相同，无需烧录')
                return
            prompt = (f"当前版本  {version(result['runtime_version'])}\n"
                      f"候选版本  {version(meta['version_raw'])}\n文件  {target}\n\n"
                      f"即将擦写 {diff} 个扇区。请确认固件来自同板型连接线。断电可能导致设备无法启动。")
            if not messagebox.askyesno('确认烧录', prompt, default='no', parent=self.root):
                self.state.set('已取消烧录')
                return
            args.apply = True
            self.run('正在写入并回读校验…', lambda: cable.flash_raw(args, expected_sha256=meta['sha256']),
                     lambda r: self.note(f"烧录完成。已写入 {r['programmed_sectors']} 个扇区，"
                                         f"重启后版本 {version(r['runtime_version'])}。"))
        self.run('正在核对备份与设备，比较候选固件…', lambda: cable.flash_raw(args), preview)


if __name__ == '__main__':
    app = tk.Tk()
    Window(app)
    app.mainloop()
