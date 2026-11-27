"""Windows desktop interface for the CV10 cable firmware tool."""
import os
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


class Window:
    def __init__(self, root):
        self.root = root
        self.busy = False
        self.results = Queue()
        local_data = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
        self.backup_directory = local_data / 'CV10-Cable-Tool' / 'Backups'
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
                      f"固件  {cable.format_version(info['version_raw'])}    模式  {mode}")
        self.run('正在读取设备状态…', status, show)

    def dump(self):
        selected = filedialog.askdirectory(
            parent=self.root, title='选择固件导出目录', mustexist=True)
        if not selected:
            return

        def export():
            return cable.save_versioned_dump(Path(selected), cable.dump_maintenance())

        def done(result):
            self.note(f"导出成功，两次读取一致。\n{result['output']}\n"
                      f"版本  {cable.format_version(result['version_raw'])}    "
                      f"{result['bytes']:,} 字节    CRC-16  {result['crc16_usb']}\nSHA-256  {result['sha256']}")
        self.run('正在读取两遍并校验固件…', export, done)

    def flash(self):
        target = filedialog.askopenfilename(parent=self.root, title='选择待烧录固件',
                                            filetypes=[('固件镜像', '*.bin')])
        if not target:
            return
        candidate_file = Path(target)

        def preview(result):
            meta = result['candidate']
            backup = result['backup']
            diff = result['differing_sectors']
            current = cable.format_version(backup['version_raw'])
            target_version = cable.format_version(meta['version_raw'])
            self.note(f"自动备份已保存\n{backup['output']}\n"
                      f"预检完成  {current} → {target_version}    差异扇区  {diff}\n"
                      f"目标文件  {target}\nSHA-256  {meta['sha256']}")
            if not diff:
                self.state.set('固件相同，无需烧录')
                return
            prompt = (f"{current} → {target_version}\n"
                      f"目标文件  {target}\n自动备份  {backup['output']}\n\n"
                      f"即将擦写 {diff} 个扇区。请确认固件来自同板型连接线。断电可能导致设备无法启动。")
            if not messagebox.askyesno('确认烧录', prompt, default='no', parent=self.root):
                self.state.set('已取消烧录')
                return
            args = SimpleNamespace(file=candidate_file, backup=Path(backup['output']), apply=True)

            def apply():
                return cable.flash_raw(args, expected_sha256=meta['sha256'],
                                       expected_backup_sha256=backup['sha256'])

            self.run('正在写入并回读校验…', apply,
                     lambda r: self.note(f"烧录完成。已写入 {r['programmed_sectors']} 个扇区，"
                                         f"重启后版本 {cable.format_version(r['runtime_version'])}。"))
        self.run('正在双读备份并比较目标固件…',
                 lambda: cable.prepare_upgrade(candidate_file, self.backup_directory), preview)


if __name__ == '__main__':
    app = tk.Tk()
    Window(app)
    app.mainloop()
