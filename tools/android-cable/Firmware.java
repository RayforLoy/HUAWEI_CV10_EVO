package org.cv10.cableupdater;

import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.Locale;

final class Firmware {
    static final int SIZE = 0xc000;
    static final int HEADER = 0x1003;
    static final String STOCK_49 = "f16057065c4c29d6d86901239371f2a6aab2bcf03c6976505c8f5971fba93e02";
    static final String STOCK_52 = "1ebf1217d0dda526f64ed3b15504db409fbdf25bc866f0fbebb874adcd00485a";
    static final String TWO_AMP = "34034349f4f991098569b385b7271adb9807a78d9f1dacc49d0413e483d786f5";

    static {
        System.loadLibrary("cv10_crc");
    }

    private Firmware() {}

    private static native int crc16Usb(byte[] image, int length);

    static String inspect(byte[] image) throws IOException {
        if (image.length != SIZE) {
            throw new IOException("连接线镜像长度错误，应为 49,152 字节。");
        }
        int tag = image[HEADER] & 0xff;
        if ((tag & 0x0f) != 0x0c || tag >= 0xa0
                || image[HEADER + 4] != 0x09 || image[HEADER + 5] != 0x21
                || image[HEADER + 6] != 0x05 || image[HEADER + 7] != 0x01) {
            throw new IOException("镜像头与 CV10 的 VL105 目标不匹配。");
        }
        int storedCrc = (image[SIZE - 2] & 0xff) | ((image[SIZE - 1] & 0xff) << 8);
        if (crc16Usb(image, SIZE - 2) != storedCrc) {
            throw new IOException("固件 CRC 校验失败。");
        }
        try {
            return hex(MessageDigest.getInstance("SHA-256").digest(image));
        } catch (NoSuchAlgorithmException error) {
            throw new AssertionError(error);
        }
    }

    static byte[] versionBytes(byte[] image) {
        return Arrays.copyOfRange(image, HEADER, HEADER + 4);
    }

    static String version(byte[] bytes) {
        return String.format(Locale.ROOT, "%X%X.%X.%X", bytes[0] & 0xff, bytes[1] & 0xff,
                bytes[2] & 0xff, bytes[3] & 0xff);
    }

    private static String hex(byte[] data) {
        StringBuilder text = new StringBuilder(2 * data.length);
        for (byte value : data) {
            text.append(Character.forDigit((value >> 4) & 15, 16));
            text.append(Character.forDigit(value & 15, 16));
        }
        return text.toString();
    }
}
