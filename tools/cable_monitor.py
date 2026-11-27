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


def snapshot(addresses=()):
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
        try:
            battery = cable.battery_status(read, info=info)
            battery_error = None
        except (OSError, ValueError) as exc:
            battery = None
            battery_error = str(exc)
        captured = {0x0018: chip, 0x00f7: mode}
        if battery is not None:
            temperature = battery['temperature_raw']
            captured.update({
                0x2dfe: battery['level_raw'],
                0x2dff: battery['port_status_raw'],
                0x2e00: battery['charger_info_raw'],
                0x2e01: temperature & 0xff,
                0x2e02: temperature >> 8,
            })
        registers = cable.register_snapshot(read, info, addresses, captured=captured)
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
                config=config.hex(), interfaces=interfaces, modes=modes,
                battery=battery, battery_error=battery_error, registers=registers)


def battery_rows(sample):
    battery = sample['battery']
    if battery is None:
        return [('线盒电池与端口', f"不可用（{sample['battery_error']}）")]
    level = battery['level_percent']
    temperature = battery['temperature_c']
    level_text = '未知' if level is None else f'{level}%'
    temperature_text = '未知' if temperature is None else f'{temperature:.1f} °C'
    charger = battery['charger_model'] or '未知型号'
    return [
        ('线盒电量缓存', f"{level_text}（原值 0x{battery['level_raw']:02X}）"),
        ('线盒温度缓存', f"{temperature_text}（原值 0x{battery['temperature_raw']:04X}）"),
        ('VL105 端口状态原值', f"0x{battery['port_status_raw']:02X}"),
        ('充电芯片身份', f"{charger}（INFO 0x{battery['charger_info_raw']:02X}）"),
    ]


def scrollable_table(parent, columns, *, show, height):
    frame = ttk.Frame(parent)
    frame.pack(fill='both', expand=True)
    scrollbar = ttk.Scrollbar(frame, orient='vertical')
    scrollbar.pack(side='right', fill='y')
    table = ttk.Treeview(frame, columns=[c for c, _, _ in columns if c != '#0'],
                         show=show, height=height, yscrollcommand=scrollbar.set)
    for column, label, width in columns:
        table.heading(column, text=label)
        table.column(column, width=width, stretch=(column == columns[-1][0]))
    scrollbar.configure(command=table.yview)
    table.pack(side='left', fill='both', expand=True)
    return table


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
        pages = ttk.Notebook(box)
        pages.pack(fill='both', expand=True)
        overview = ttk.Frame(pages, padding=6)
        register_page = ttk.Frame(pages, padding=6)
        pages.add(overview, text='概览')
        pages.add(register_page, text='寄存器')
        self.table = scrollable_table(overview, [('key', '诊断项', 165), ('value', '实机读数', 360)],
                                      show='headings', height=12)
        ttk.Label(overview, text='Billboard 状态为设备声明。电芯电压、电流和充电阶段需另行测量。'
                  ).pack(anchor='w', pady=(10, 0))
        self.register_panel(register_page)
        self.samples = deque(maxlen=300)
        self.queue = Queue()
        self.busy = False
        self.timer = None
        self.last_manual = None

    def register_panel(self, page):
        controls = ttk.Frame(page)
        controls.pack(fill='x', pady=(0, 4))
        ttk.Label(controls, text='十六进制地址').pack(side='left', padx=(0, 6))
        self.address_entry = ttk.Entry(controls)
        self.address_entry.pack(side='left', fill='x', expand=True)
        self.address_entry.bind('<Return>', lambda _: self.read_addresses())
        self.read_selected = ttk.Button(controls, text='单次读取地址', command=self.read_addresses)
        self.read_selected.pack(side='left', padx=(6, 0))
        ttk.Label(page, text='例如 0003, 2DFE-2E02').pack(anchor='w', pady=(0, 5))
        self.register_table = scrollable_table(
            page, [('#0', '地址 / 分组', 100), ('name', '寄存器', 157),
                   ('raw', '原值', 60), ('details', '解释 / 来源', 210)],
            show='tree headings', height=11)
        self.register_status = tk.StringVar(value='等待读取')
        ttk.Label(page, textvariable=self.register_status, wraplength=525).pack(anchor='w', pady=(6, 0))

    def read_addresses(self):
        try:
            addresses = cable.parse_register_addresses(self.address_entry.get())
            if not addresses:
                raise ValueError('请输入要读取的地址')
        except ValueError as error:
            messagebox.showerror('地址格式', str(error), parent=self.root)
            return
        self.start(addresses)

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

    def start(self, addresses=()):
        if not self.active or self.busy:
            return
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        self.busy = True
        self.refresh.state(['disabled'])
        self.read_selected.state(['disabled'])
        self.status.set('正在读取寄存器…' if addresses else '正在读取快照…')
        def worker():
            try:
                with self.device_lock:
                    result = snapshot(addresses)
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
        self.read_selected.state(['!disabled'])
        self.save.state(['!disabled'])
        self.table.delete(*self.table.get_children())
        if 'error' in s:
            rows = [('读取失败', s['error'])]
        else:
            rows = [('USB 设备', s['vid_pid']+'  '+s['product']), ('固件版本字节', s['version_raw']),
                    ('USB 修订号', f"0x{s['bcd_device'].upper()}"),
                    ('芯片识别寄存器', s['project_register']), ('运行模式寄存器', s['mode_register']+'  '+s['mode'])]
            rows.extend(battery_rows(s))
            for i in s['interfaces']:
                rows.append((f"接口 {i['number']}", f"类 0x{i['usb_class']:02X}，数据端点 {i['endpoints']} 个"))
            for m in s['modes']:
                rows.append(('Billboard 模式', f"SVID {m['svid']}，模式 {m['alternate_mode']}，声明状态 {m['configuration']}"))
        for row in rows:
            self.table.insert('', 'end', values=row)
        self.show_registers(s)
        self.status.set(s['timestamp']+'    保留最近 '+str(len(self.samples))+' 条采样（上限 300）')
        self.schedule()

    def show_registers(self, sample):
        table = self.register_table
        groups = table.get_children()
        open_groups = {table.item(group, 'text'): table.item(group, 'open') for group in groups}
        scroll = table.yview()[0]
        table.delete(*groups)
        data = sample.get('registers')
        if data and data['manual']:
            version = cable.format_version(sample['version_raw'])
            self.last_manual = (f"{version} · {sample['timestamp'][11:19]}", data['manual'])
            scroll = 0

        group_ids = {}
        if self.last_manual:
            label, entries = self.last_manual
            manual_group = table.insert('', 'end', text='手动读取', open=True, values=('', '', label))
            for entry in entries:
                self.insert_register(manual_group, entry)

        if data:
            for entry in data['presets']:
                name = entry['group']
                if name not in group_ids:
                    group_ids[name] = table.insert('', 'end', text=name, open=open_groups.get(name, True))
                self.insert_register(group_ids[name], entry)
            note = data['layout_error']
            self.register_status.set(f"{len(data['presets'])} 项预设" + (f" · {note}" if note else ''))
        else:
            self.register_status.set('当前连接的寄存器快照不可用')
        table.yview_moveto(scroll)

    def insert_register(self, group, entry):
        value = entry['raw']
        raw = f'0x{value:02X}' if value is not None else '未读到'
        details = ' · '.join(part for part in (entry['interpretation'], entry['note']) if part)
        self.register_table.insert(group, 'end', text=f"0x{entry['address']:04X}",
                                   values=(entry['name'], raw, entry['error'] or details))

    def export(self):
        name = filedialog.asksaveasfilename(parent=self.root, defaultextension='.json',
                initialfile='CV10-diagnostics.json', filetypes=[('诊断记录','*.json')])
        if name:
            try:
                Path(name).write_text(json.dumps(list(self.samples), ensure_ascii=False, indent=2), encoding='utf-8')
            except OSError as exc:
                messagebox.showerror('保存失败',str(exc),parent=self.root)


