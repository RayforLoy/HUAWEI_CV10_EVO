package org.cv10.cabletool;

import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;

enum Firmware {
    STOCK_49("C9.49.6 原版", "stock49.bin",
            "f16057065c4c29d6d86901239371f2a6aab2bcf03c6976505c8f5971fba93e02"),
    STOCK_52("C9.52.6 原版", "stock52.bin",
            "1ebf1217d0dda526f64ed3b15504db409fbdf25bc866f0fbebb874adcd00485a"),
    STOCK_53("C9.53.6 原版", "stock53.bin",
            "8e8d9d0df2809f2d3a673519834c83662acc5be6635060d75ef246133956843e"),
    PHONE_2A("C9.53.6 供电测试版 · 5 V / 2 A", "phone2a.bin",
            "ba4fa99083c69bcacbd44b0a7afcbfcde228b5535752bc47c59cea13fc3d1096"),
    PIN_C("C9.53.6 群友版 · 仅 Pin C", "pinc.bin",
            "c9d88fcc5205bfb6f9aa6cdd93839c0bfb056522f542132d9ef028efe1c129f6"),
    RT9471_PHONE_2A("C9.53.6 · RT9471 2.5 A ＋ 条件式 2 A", "rt9471-phone2a.bin",
            "6b481d03fadb6911b7fe3e51903a8cc48b9029c5cea85dc848ee5c35787d1f9c");

    static final int SIZE = 0xc000;
    static final int HEADER = 0x1003;
    final String label;
    final String asset;
    final String sha256;

    Firmware(String label, String asset, String sha256) {
        this.label = label;
        this.asset = asset;
        this.sha256 = sha256;
    }

    byte[] verify(byte[] image) throws IOException {
        validate(image);
        if (!sha256.equals(digest(image))) {
            throw new IOException(label + "的 SHA-256 校验失败。");
        }
        return image;
    }

    static void validate(byte[] image) throws IOException {
        if (image.length != SIZE) {
            throw new IOException("VL105 镜像必须为 49,152 字节。");
        }
        if ((image[HEADER] & 0xff) != 0x0c || image[HEADER + 1] != 9
                || image[HEADER + 3] != 6 || image[HEADER + 4] != 9
                || image[HEADER + 5] != 0x21 || image[HEADER + 6] != 5
                || image[HEADER + 7] != 1) {
            throw new IOException("镜像头与 CV10 的 2109:0105 VL105 不匹配。");
        }
        int crc = 0xffff;
        for (int i = 0; i < SIZE - 2; i++) {
            crc ^= image[i] & 0xff;
            for (int bit = 0; bit < 8; bit++) {
                crc = (crc >>> 1) ^ ((crc & 1) == 1 ? 0xa001 : 0);
            }
        }
        int stored = (image[SIZE - 2] & 0xff) | (image[SIZE - 1] & 0xff) << 8;
        if ((crc ^ 0xffff) != stored) {
            throw new IOException("镜像 CRC-16/USB 校验失败。");
        }
    }

    static String buildLabel(byte[] image) {
        String hash = digest(image);
        for (Firmware firmware : values()) {
            if (firmware.sha256.equals(hash)) {
                return firmware.label;
            }
        }
        return version(image, HEADER) + " · 未匹配内置镜像";
    }

    static String version(byte[] bytes, int start) {
        return String.format(Locale.ROOT, "C%X.%02X.%X",
                bytes[start + 1] & 0xff, bytes[start + 2] & 0xff, bytes[start + 3] & 0xff);
    }

    static String digest(byte[] image) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(image);
            StringBuilder hex = new StringBuilder(64);
            for (byte value : digest) {
                hex.append(String.format(Locale.ROOT, "%02x", value & 0xff));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }
}
