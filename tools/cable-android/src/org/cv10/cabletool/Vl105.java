package org.cv10.cabletool;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.function.Consumer;

final class Vl105 {
    private static final int WRITE_BASE = 0x20000;
    private static final int BLOCK = 32;
    private static final int SECTOR = 4096;
    private static final byte[] EMPTY = new byte[0];

    interface Transport extends AutoCloseable {
        byte[] read(int request, int value, int index, int length) throws IOException;
        void write(int request, int value, int index, byte[] data) throws IOException;
        @Override void close();
    }

    interface Host {
        Transport initial() throws IOException;
        Transport awaitMode(boolean runtime) throws IOException;
    }

    interface BackupStore {
        String save(byte[] image) throws IOException;
    }

    static final class RecoveryRequired extends IOException {
        RecoveryRequired(String message, Throwable cause) {
            super(message, cause);
        }
    }

    static final class Snapshot {
        final byte[] image;
        final String savedAt;

        Snapshot(byte[] image, String savedAt) {
            this.image = image;
            this.savedAt = savedAt;
        }
    }

    private interface RomTask<T> {
        T run(Transport rom, byte[] runningVersion) throws IOException;
    }

    private final Host host;
    private final Consumer<String> progress;

    Vl105(Host host, Consumer<String> progress) {
        this.host = host;
        this.progress = progress;
    }

    static boolean isRuntime(Transport usb) throws IOException {
        return (register(usb, 0xf7) & 0x80) != 0;
    }

    static byte[] runningVersion(Transport usb) throws IOException {
        if (!isRuntime(usb) || (register(usb, 0x18) & 0xf0) != 0xa0) {
            throw new IOException("线盒未处于 VL105 运行态。");
        }
        byte[] version = usb.read(0xe2, 1, 0, 4);
        if (version[0] != 0x0c || version[1] != 9 || version[3] != 6) {
            throw new IOException("运行版本与 CV10 线盒不匹配。");
        }
        return version;
    }

    String probe() throws IOException {
        try (Transport usb = host.initial()) {
            return Firmware.version(runningVersion(usb), 0);
        }
    }

    Snapshot backup(BackupStore store) throws IOException {
        return inRom((rom, version) -> {
            byte[] image = readVerified(rom, version);
            return new Snapshot(image, store.save(image));
        }, null);
    }

    int flash(Snapshot snapshot, byte[] target) throws IOException {
        Firmware.validate(snapshot.image);
        Firmware.validate(target);
        List<Integer> changed = changedSectors(snapshot.image, target);
        if (changed.isEmpty()) {
            return 0;
        }
        return inRom((rom, version) -> {
            byte[] current = readVerified(rom, version);
            if (!Arrays.equals(current, snapshot.image)) {
                throw new IOException("线盒内容与已保存的备份不同。请重新备份和预检。");
            }
            program(rom, current, target, changed);
            return changed.size();
        }, Arrays.copyOfRange(target, Firmware.HEADER, Firmware.HEADER + 4));
    }

    static List<Integer> changedSectors(byte[] current, byte[] target) {
        List<Integer> changes = new ArrayList<>();
        for (int offset = 0; offset < Firmware.SIZE; offset += SECTOR) {
            if (!Arrays.equals(sector(current, offset), sector(target, offset))) {
                changes.add(offset);
            }
        }
        return changes;
    }

    private <T> T inRom(RomTask<T> task, byte[] newVersion) throws IOException {
        byte[] version;
        try (Transport usb = host.initial()) {
            version = runningVersion(usb);
            progress.accept("正在切换 VL105 维护模式...");
            detach(usb);
        }
        T result;
        try (Transport rom = host.awaitMode(false)) {
            try {
                result = task.run(rom, version);
            } catch (RecoveryRequired failure) {
                throw failure;
            } catch (IOException failure) {
                try {
                    reset(rom, 0xb0);
                } catch (IOException restartFailure) {
                    failure.addSuppressed(restartFailure);
                }
                throw failure;
            }
            progress.accept("正在重启线盒并检查运行版本...");
            reset(rom, 0xb0);
        }
        try (Transport usb = host.awaitMode(true)) {
            if (!Arrays.equals(runningVersion(usb), newVersion == null ? version : newVersion)) {
                throw new IOException("线盒重启后的版本与预期不同。");
            }
        } catch (IOException failure) {
            if (newVersion != null) {
                throw new IOException("镜像已完整回读，但重启后的运行版本未确认。", failure);
            }
            throw failure;
        }
        return result;
    }

    private void detach(Transport usb) throws IOException {
        int[] addresses = {0x15, 0x19, 0x1c, 3};
        int[] saved = new int[addresses.length];
        for (int i = 0; i < addresses.length; i++) {
            saved[i] = register(usb, addresses[i]);
        }
        int[] desired = {0x7f, 0, 2, (saved[3] | 0x10) & 0xfe};
        try {
            for (int i = 0; i < addresses.length; i++) {
                setRegister(usb, addresses[i], desired[i]);
            }
        } catch (IOException failure) {
            for (int i = addresses.length - 1; i >= 0; i--) {
                try {
                    setRegister(usb, addresses[i], saved[i]);
                } catch (IOException restoreFailure) {
                    failure.addSuppressed(restoreFailure);
                }
            }
            throw failure;
        }
        reset(usb, 0xc0);
    }

    private byte[] readVerified(Transport rom, byte[] version) throws IOException {
        progress.accept("正在双读线盒固件...");
        byte[] first = readRegion(rom, 0, Firmware.SIZE);
        Firmware.validate(first);
        byte[] header = Arrays.copyOfRange(first, Firmware.HEADER, Firmware.HEADER + 4);
        if (!Arrays.equals(header, version)
                || !Arrays.equals(first, readRegion(rom, 0, Firmware.SIZE))) {
            throw new IOException("镜像两次读回或镜像头与运行版本不一致。");
        }
        progress.accept("正在核对 VL105 写入区...");
        if (!Arrays.equals(first, readRegion(rom, WRITE_BASE, Firmware.SIZE))) {
            throw new IOException("线盒的写入区与原固件读数不一致。");
        }
        return first;
    }

    private void program(Transport rom, byte[] current, byte[] target, List<Integer> changes)
            throws IOException {
        if (status(rom) != 0) {
            throw new IOException("SPI 状态异常，已停止更新。");
        }
        int gpio = register(rom, 3);
        List<Integer> started = new ArrayList<>();
        try {
            setRegister(rom, 0x15, 0x7f);
            setRegister(rom, 0x19, 0);
            setRegister(rom, 0x1c, 2);
            setRegister(rom, 3, gpio | 0x44);
            for (int offset : changes) {
                started.add(offset);
                progress.accept("正在写入并回读扇区 " + started.size() + " / " + changes.size());
                programSector(rom, offset, sector(target, offset));
            }
            verifyProgrammed(rom, target);
        } catch (IOException failure) {
            if (started.isEmpty()) {
                throw failure;
            }
            try {
                progress.accept("写入中断，正在恢复并核对原固件...");
                waitFlash(rom);
                for (int i = started.size() - 1; i >= 0; i--) {
                    int offset = started.get(i);
                    byte[] original = sector(current, offset);
                    if (!Arrays.equals(original, readRegion(rom, WRITE_BASE + offset, SECTOR))) {
                        programSector(rom, offset, original);
                    }
                }
                verifyProgrammed(rom, current);
            } catch (IOException recovery) {
                recovery.addSuppressed(failure);
                throw new RecoveryRequired("写入和原固件恢复均失败。工具保留维护模式，避免从未验证镜像启动。", recovery);
            }
            throw new IOException("写入失败，原固件已恢复并完整回读。", failure);
        } finally {
            try {
                setRegister(rom, 3, gpio);
            } catch (IOException failure) {
                throw new RecoveryRequired("写入保护寄存器未能恢复。工具保留维护模式。", failure);
            }
        }
    }

    private static void verifyProgrammed(Transport usb, byte[] expected) throws IOException {
        if (!Arrays.equals(expected, readRegion(usb, WRITE_BASE, Firmware.SIZE))
                || !Arrays.equals(expected, readRegion(usb, 0, Firmware.SIZE))) {
            throw new IOException("写入区或启动映射的完整镜像回读不匹配。");
        }
    }

    private static byte[] sector(byte[] image, int offset) {
        return Arrays.copyOfRange(image, offset, offset + SECTOR);
    }

    private static void programSector(Transport usb, int offset, byte[] data) throws IOException {
        int base = WRITE_BASE + offset;
        usb.write(0xd4, 6, 0, EMPTY);
        usb.write(0xd2, 0x20, base >> 8, EMPTY);
        waitFlash(usb);
        for (byte value : readRegion(usb, base, SECTOR)) {
            if (value != (byte) 0xff) {
                throw new IOException("扇区擦除校验失败。");
            }
        }
        byte[] erased = new byte[BLOCK];
        Arrays.fill(erased, (byte) 0xff);
        for (int i = 0; i < SECTOR; i += BLOCK) {
            byte[] chunk = Arrays.copyOfRange(data, i, i + BLOCK);
            if (Arrays.equals(chunk, erased)) {
                continue;
            }
            int pos = base + i;
            usb.write(0xd4, 6, 0, EMPTY);
            usb.write(0xdc, (pos & 0xff) << 8 | 2, pos >> 8, chunk);
            sleep(1);
            waitFlash(usb);
        }
        if (!Arrays.equals(readRegion(usb, base, SECTOR), data)) {
            throw new IOException("扇区写入回读不匹配。");
        }
    }

    private static byte[] readRegion(Transport usb, int address, int length) throws IOException {
        byte[] region = new byte[length];
        for (int offset = 0; offset < length; offset += BLOCK) {
            int pos = address + offset;
            byte[] block = usb.read(0xc4, (pos & 0xff) << 8 | 3, pos >> 8, Math.min(BLOCK, length - offset));
            System.arraycopy(block, 0, region, offset, block.length);
        }
        return region;
    }

    private static int status(Transport usb) throws IOException {
        return usb.read(0xc2, 5, 0, 1)[0] & 0xff;
    }

    private static void waitFlash(Transport usb) throws IOException {
        long deadline = System.nanoTime() + 5_000_000_000L;
        while ((status(usb) & 1) != 0) {
            if (System.nanoTime() >= deadline) {
                throw new IOException("等待 SPI 空闲超时。");
            }
            sleep(5);
        }
    }

    private static int register(Transport usb, int address) throws IOException {
        return usb.read(0xe0, (address & 0xff) << 8 | 1, address >> 8, 1)[0] & 0xff;
    }

    private static void setRegister(Transport usb, int address, int value) throws IOException {
        usb.write(0xe0, (address & 0xff) << 8 | 2, address >> 8, new byte[] {(byte) value});
    }

    private void reset(Transport usb, int request) throws IOException {
        try {
            usb.write(request, 0, 0, EMPTY);
        } catch (IOException disconnect) {
            // On Android a reset may drop USB before the status stage returns.
            progress.accept("等待线盒重新枚举...");
        }
    }

    static void sleep(long ms) throws IOException {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException failure) {
            Thread.currentThread().interrupt();
            throw new IOException("USB 操作已中断。", failure);
        }
    }
}
