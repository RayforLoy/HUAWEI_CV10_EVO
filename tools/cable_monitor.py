"""Read-only WinUSB diagnostics for the CV10 VL105 cable."""
from collections import deque
from datetime import datetime
import json
from pathlib import Path
from queue import Queue, Empty
from threading import Thread
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

import cable


def descriptors(raw):
    pos = 0
    while pos < len(raw):
        size = raw[pos]
        if size < 2 or pos + size > len(raw):
            raise ValueError('描述符长度无效')
        yield raw[pos:pos + size]
        pos += size


def snapshot():
    with cable.cable_reader() as read:
        info = cable.probe(read)
        chip = cable.read_register(read, 0x18)
        mode = cable.read_register(read, 0xf7)
        header = read(6, 0x0200, 0, 9, descriptor=True)
        if len(header) != 9:
            raise ValueError('配置描述符不完整')
        total = int.from_bytes(header[2:4], 'little')
        config = read(6, 0x0200, 0, total, descriptor=True)
        if len(config) != total:
            raise ValueError('配置描述符长度不匹配')
    modes = []
    for d in descriptors(bytes.fromhex(info['bos'])):
        if d[1:3] == bytes([16, 13]):
            if len(d) < 44 or d[4] > 128 or len(d) < 44 + 4*d[4]:
                raise ValueError('Billboard 模式表不完整')
            for i in range(d[4]):
                off = 44 + 4*i
                modes.append(dict(svid=f'{int.from_bytes(d[off:off+2], "little"):04X}',
                                  alternate_mode=d[off+2], configuration=(d[8+i//4] >> (2*(i%4))) & 3))
    interfaces = [dict(number=d[2], alternate=d[3], endpoints=d[4], usb_class=d[5])
                  for d in descriptors(config) if d[1] == 4 and len(d) >= 9]
    return dict(timestamp=datetime.now().astimezone().isoformat(timespec='seconds'),
                **info, project_register=f'{chip:02X}', mode_register=f'{mode:02X}',
                config=config.hex(), interfaces=interfaces, modes=modes)


class Monitor:
    def __init__(self, root, device_lock):
        self.root = root
        self.device_lock = device_lock
        self.active = False
        box = ttk.Frame(root, padding=18)
        box.pack(fill='both', expand=True)
        bar = ttk.Frame(box)
        bar.pack(fill='x')
        self.refresh = ttk.Button(bar, text='读取快照', command=self.start)
        self.refresh.pack(side='left')
        self.auto = tk.BooleanVar()
        ttk.Checkbutton(bar, text='每 2 秒刷新', variable=self.auto, command=self.schedule).pack(side='left', padx=12)
        self.save = ttk.Button(bar, text='导出采样记录…', command=self.export)
        self.save.pack(side='right')
        self.save.state(['disabled'])
        self.status = tk.StringVar(value='等待读取')
        ttk.Label(box, textvariable=self.status).pack(anchor='w', pady=8)
        self.table = ttk.Treeview(box, columns=('key', 'value'), show='headings', height=10)
        for col, label, width in [('key', '诊断项', 165), ('value', '实机读数', 390)]:
            self.table.heading(col, text=label)
            self.table.column(col, width=width)
        self.table.pack(fill='both', expand=True)
        ttk.Label(box, text='Billboard 为设备声明值。实际视频、供电和充电电流需在对应链路测量。').pack(anchor='w', pady=(10,0))
        self.samples = deque(maxlen=300)
        self.queue = Queue()
        self.busy = False
        self.timer = None

    def set_active(self, active):
        self.active = active
        if active:
            self.start()
        else:
            self.schedule()

    def schedule(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        if self.active and self.auto.get() and not self.busy:
            self.timer = self.root.after(2000, self.start)

    def start(self):
        if not self.active or self.busy:
            return
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        self.busy = True
        self.refresh.state(['disabled'])
        def worker():
            try:
                with self.device_lock:
                    result = snapshot()
                self.queue.put(result)
            except Exception as exc:
                self.queue.put(dict(timestamp=datetime.now().astimezone().isoformat(timespec='seconds'),error=str(exc)))
        Thread(target=worker, daemon=True).start()
        self.root.after(75, self.finish)

    def finish(self):
        try:
            s = self.queue.get_nowait()
        except Empty:
            self.root.after(75, self.finish)
            return
        self.busy = False
        self.samples.append(s)
        self.refresh.state(['!disabled'])
        self.save.state(['!disabled'])
        self.table.delete(*self.table.get_children())
        if 'error' in s:
            rows = [('读取失败', s['error'])]
        else:
            rows = [('USB 设备', s['vid_pid']+'  '+s['product']), ('固件版本字节', s['version_raw']),
                    ('芯片识别寄存器', s['project_register']), ('运行模式寄存器', s['mode_register']+'  '+s['mode'])]
            for i in s['interfaces']:
                rows.append((f"接口 {i['number']}", f"类 0x{i['usb_class']:02X}，数据端点 {i['endpoints']} 个"))
            for m in s['modes']:
                rows.append(('Billboard 模式', f"SVID {m['svid']}，模式 {m['alternate_mode']}，配置字段 {m['configuration']}"))
        for row in rows:
            self.table.insert('', 'end', values=row)
        self.status.set(s['timestamp']+'    保留最近 '+str(len(self.samples))+' 条采样（上限 300）')
        self.schedule()

    def export(self):
        name = filedialog.asksaveasfilename(parent=self.root, defaultextension='.json',
                initialfile='CV10-diagnostics.json', filetypes=[('诊断记录','*.json')])
        if name:
            try:
                Path(name).write_text(json.dumps(list(self.samples), ensure_ascii=False, indent=2), encoding='utf-8')
            except OSError as exc:
                messagebox.showerror('保存失败',str(exc),parent=self.root)


