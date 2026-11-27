package org.cv10.cableupdater;

import java.io.File;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.TimeUnit;

final class Updater {
    private static final int PD_START = 0x20000;
    private static final int SECTOR = 0x1000;
    private static final int BLOCK = 32;
    private static final int[] GPIO_REGISTERS = {0x15, 0x19, 0x1c, 0x03};
    private static final byte[] EMPTY = new byte[0];

    interface Usb extends AutoCloseable {
        int transfer(int type, int request, int value, int index, byte[] data, int offset, int size);
        @Override void close();
    }

    interface Host {
        Link open(boolean runtime) throws IOException;
        void checkSetup() throws IOException;
    }

    interface Backup {
        File save(byte[] image, String version) throws IOException;
    }

    interface Status {
        void show(String text);
    }

    static final class Result {
        final File backup;
        final int sectors;
        final String version;

        Result(File backup, int sectors, String version) {
            this.backup = backup;
            this.sectors = sectors;
            this.version = version;
        }
    }

    private static final class UnverifiedFlash extends IOException {
        UnverifiedFlash(String message, Exception cause) {
            super(message, cause);
        }
    }

    private Updater() {}

    static Result install(Host host, byte[] target, Backup backup, Status status) throws IOException {
        if (!Firmware.TWO_AMP.equals(Firmware.inspect(target))) {
            throw new IOException("内置固件的 SHA-256 与实测镜像不符。");
        }
        byte[] liveVersion;
        status.show("正在识别原厂线并确认 USB 权限…");
        try (Link runtime = host.open(true)) {
            if ((runtime.register(0x18) & 0xf0) != 0xa0) {
                throw new IOException("芯片识别值与 VL105 不符。");
            }
            liveVersion = runtime.version();
            String version = Firmware.version(liveVersion);
            if (!version.equals("C9.49.6") && !version.equals("C9.52.6")) {
                throw new IOException("当前版本 " + version + " 未经此镜像验证。");
            }
            status.show("正在让线控进入维护模式…");
            runtime.enterRom();
        }

        Result result;
        try (Link rom = host.open(false)) {
            boolean safeToReset = true;
            try {
                result = installInRom(host, rom, liveVersion, target, backup, status);
            } catch (UnverifiedFlash failure) {
                safeToReset = false;
                throw failure;
            } finally {
                if (safeToReset) {
                    rom.reset(0xb0);
                }
            }
        }

        status.show("正在等待线控恢复运行态…");
        try (Link runtime = host.open(true)) {
            if (!Arrays.equals(runtime.version(), Firmware.versionBytes(target))) {
                throw new IOException("写入区回读通过，但重启后的运行版本异常。");
            }
        }
        return result;
    }

    private static Result installInRom(Host host, Link rom, byte[] liveVersion, byte[] target,
                                       Backup backup, Status status) throws IOException {
        status.show("正在双读原固件并验证镜像…");
        byte[] original = rom.region(0, Firmware.SIZE);
        if (!Arrays.equals(original, rom.region(0, Firmware.SIZE))
                || !Arrays.equals(liveVersion, Firmware.versionBytes(original))) {
            throw new IOException("两次读取或运行版本不一致。");
        }
        String digest = Firmware.inspect(original);
        if (!digest.equals(Firmware.STOCK_49) && !digest.equals(Firmware.STOCK_52)
                && !digest.equals(Firmware.TWO_AMP)) {
            throw new IOException("当前镜像与已验证的原厂线镜像不匹配。");
        }
        if (!Arrays.equals(original, rom.region(PD_START, Firmware.SIZE))) {
            throw new IOException("启动镜像和写入区的内容不一致。");
        }

        String version = Firmware.version(Firmware.versionBytes(target));
        if (digest.equals(Firmware.TWO_AMP)) {
            return new Result(null, 0, version);
        }

        status.show("正在保存原固件备份…");
        File saved = backup.save(original, Firmware.version(liveVersion));
        host.checkSetup();
        List<Integer> changed = new ArrayList<>();
        for (int offset = 0; offset < original.length; offset += SECTOR) {
            if (!Arrays.equals(Arrays.copyOfRange(original, offset, offset + SECTOR),
                    Arrays.copyOfRange(target, offset, offset + SECTOR))) {
                changed.add(offset);
            }
        }
        programWithRollback(rom, target, original, changed, status);
        return new Result(saved, changed.size(), version);
    }

    private static void programWithRollback(Link rom, byte[] target, byte[] original,
                                            List<Integer> changed, Status status) throws IOException {
        if (rom.flashStatus() != 0) {
            throw new IOException("擦写前的 Flash 状态异常。");
        }
        int gpio = rom.register(3);
        List<Integer> touched = new ArrayList<>();
        try {
            rom.configureGpio(gpio | 0x44);
            for (int offset : changed) {
                touched.add(offset);
                status.show("正在回写并校验扇区 " + touched.size() + " / " + changed.size() + "…");
                rom.programSector(offset, target);
            }
            status.show("正在回读整个镜像…");
            rom.verifyImage(target);
        } catch (IOException | RuntimeException writeError) {
            if (touched.isEmpty()) {
                throw writeError;
            }
            status.show("写入中断，正在尝试恢复原固件…");
            try {
                rom.waitFlash();
                for (int i = touched.size() - 1; i >= 0; --i) {
                    int offset = touched.get(i);
                    if (!Arrays.equals(rom.region(PD_START + offset, SECTOR),
                            Arrays.copyOfRange(original, offset, offset + SECTOR))) {
                        rom.programSector(offset, original);
                    }
                }
                rom.verifyImage(original);
            } catch (IOException | RuntimeException restoreError) {
                writeError.addSuppressed(restoreError);
                throw new UnverifiedFlash("写入中断，原固件恢复未通过校验。请保持供电，并保留自动备份。", writeError);
            }
            throw new IOException("写入中断，已恢复原固件并验证回读。", writeError);
        } finally {
            try {
                rom.writeRegister(3, gpio);
            } catch (IOException | RuntimeException error) {
                throw new UnverifiedFlash("无法确认线控写保护状态，已停止复位。请保留自动备份。", error);
            }
        }
    }

    static void pause(int millis) throws InterruptedIOException {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException error) {
            throw new InterruptedIOException("USB 操作被中断。");
        }
    }

    static final class Link implements AutoCloseable {
        private final Usb usb;

        Link(Usb usb) {
            this.usb = usb;
        }

        @Override public void close() {
            usb.close();
        }

        private void transfer(int type, int request, int value, int index,
                              byte[] data, int offset, int size) throws IOException {
            int count = usb.transfer(type, request, value, index, data, offset, size);
            if (count != size) {
                throw new IOException(String.format(Locale.ROOT, "USB 请求 0x%02X 应返回 %d 字节，实得 %d。",
                        request, size, count));
            }
        }

        private int readByte(int request, int value, int index) throws IOException {
            byte[] buffer = new byte[1];
            transfer(0xc0, request, value, index, buffer, 0, 1);
            return buffer[0] & 0xff;
        }

        byte[] version() throws IOException {
            byte[] version = new byte[4];
            transfer(0xc0, 0xe2, 1, 0, version, 0, version.length);
            return version;
        }

        boolean runtime() throws IOException {
            return (register(0xf7) & 0x80) != 0;
        }

        int register(int address) throws IOException {
            return readByte(0xe0, ((address & 0xff) << 8) | 1, address >> 8);
        }

        void writeRegister(int address, int value) throws IOException {
            transfer(0x40, 0xe0, ((address & 0xff) << 8) | 2, address >> 8,
                    new byte[]{(byte) value}, 0, 1);
        }

        void configureGpio(int control) throws IOException {
            int[] values = {0x7f, 0, 2, control};
            for (int i = 0; i < GPIO_REGISTERS.length; ++i) {
                writeRegister(GPIO_REGISTERS[i], values[i]);
            }
        }

        void enterRom() throws IOException {
            int[] saved = new int[GPIO_REGISTERS.length];
            for (int i = 0; i < saved.length; ++i) {
                saved[i] = register(GPIO_REGISTERS[i]);
            }
            try {
                configureGpio((saved[3] | 0x10) & 0xfe);
            } catch (IOException error) {
                for (int i = saved.length - 1; i >= 0; --i) {
                    try {
                        writeRegister(GPIO_REGISTERS[i], saved[i]);
                    } catch (IOException restoreError) {
                        error.addSuppressed(restoreError);
                    }
                }
                throw error;
            }
            reset(0xc0);
        }

        void reset(int request) {
            // The status transfer may fail when the USB address disappears.
            usb.transfer(0x40, request, 0, 0, EMPTY, 0, 0);
        }

        byte[] region(int start, int size) throws IOException {
            byte[] result = new byte[size];
            for (int offset = 0; offset < size; offset += BLOCK) {
                int address = start + offset;
                transfer(0xc0, 0xc4, ((address & 0xff) << 8) | 3, address >> 8,
                        result, offset, Math.min(BLOCK, size - offset));
            }
            return result;
        }

        int flashStatus() throws IOException {
            return readByte(0xc2, 5, 0);
        }

        void waitFlash() throws IOException {
            long until = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
            while ((flashStatus() & 1) != 0) {
                if (System.nanoTime() >= until) {
                    throw new IOException("Flash 等待就绪超时。");
                }
                pause(5);
            }
        }

        void verifyImage(byte[] expected) throws IOException {
            if (!Arrays.equals(region(PD_START, expected.length), expected)) {
                throw new IOException("写入区未通过完整镜像回读。");
            }
        }

        private void writeEnable() throws IOException {
            transfer(0x40, 0xd4, 6, 0, EMPTY, 0, 0);
        }

        void programSector(int offset, byte[] image) throws IOException {
            int address = PD_START + offset;
            writeEnable();
            transfer(0x40, 0xd2, 0x20, address >> 8, EMPTY, 0, 0);
            waitFlash();
            for (byte value : region(address, SECTOR)) {
                if (value != (byte) 0xff) {
                    throw new IOException("扇区擦除未通过回读。");
                }
            }
            for (int chunk = 0; chunk < SECTOR; chunk += BLOCK) {
                int position = address + chunk;
                int start = offset + chunk;
                boolean blank = true;
                for (int i = start; i < start + BLOCK; ++i) {
                    if (image[i] != (byte) 0xff) {
                        blank = false;
                        break;
                    }
                }
                if (blank) {
                    continue;
                }
                writeEnable();
                transfer(0x40, 0xdc, ((position & 0xff) << 8) | 2, position >> 8,
                        image, start, BLOCK);
                pause(1);
                waitFlash();
            }
            if (!Arrays.equals(region(address, SECTOR), Arrays.copyOfRange(image, offset, offset + SECTOR))) {
                throw new IOException("扇区写入未通过回读。");
            }
        }
    }
}
