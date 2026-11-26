// SPDX-License-Identifier: GPL-3.0-or-later
package org.freedesktop.monado.openxr_runtime;

final class ReportVectors {
    public static void main(String[] args) {
        check(Cv10ControllerReport.decode(null) == null, "missing report");
        check(Cv10ControllerReport.decode(new byte[19]) == null, "short report");
        check(Cv10ControllerReport.decode(new byte[21]) == null, "long report");
        Cv10ControllerReport idle = Cv10ControllerReport.decode(hex("00 00 00 00 00 80 01 00 00 00 00 08 00 00 00 00 00 64 00 00"));
        check(idle.buttons == 0 && !idle.isTouched() && idle.battery == 100, "idle/button release");
        check(idle.orientationValid, "identity orientation");
        close(idle.w, 1f, "identity W sign");

        Cv10ControllerReport active = Cv10ControllerReport.decode(hex("3f 40 00 40 00 40 00 40 00 7f 80 01 7f 80 ff 00 ff 32 ab cd"));
        for (int mask = 1; mask <= Cv10ControllerReport.BACK; mask <<= 1) {
            check(active.isPressed(mask), "button bit " + mask);
        }
        check(active.orientationValid, "unit quaternion");
        close(active.x, 0.5f, "X");
        close(active.y, -0.5f, "Y");
        close(active.z, 0.5f, "Z");
        close(active.w, -0.5f, "W");
        close(active.accelX, 16f, "accelerometer scale");
        close(active.accelY, -2048f / 127f, "signed accelerometer");
        close(active.gyroX, 2000f, "gyro scale");
        close(active.gyroZ, -2000f / 127f, "signed gyro");
        check(active.isTouched() && active.touchX == 0 && active.touchY == 255, "edge touch");
        check(active.battery == 50, "battery");

        Cv10ControllerReport asymmetric = Cv10ControllerReport.decode(hex("02 00 00 00 00 80 22 12 34 00 00 00 00 00 00 ff 00 ff 00 00"));
        check(asymmetric.isPressed(Cv10ControllerReport.CONFIRM) &&
                !asymmetric.isPressed(Cv10ControllerReport.BACK | Cv10ControllerReport.TRIGGER), "confirm isolation");
        close(asymmetric.z, 4660f / 32767f, "Z wire order");
        close(asymmetric.w, 32734f / 32767f, "W wire order");
        check(asymmetric.isTouched() && asymmetric.touchX == 255 && asymmetric.touchY == 0 &&
                asymmetric.battery == -1, "signed battery and unsigned touch");
        check(!Cv10ControllerReport.decode(new byte[20]).orientationValid, "zero quaternion");
        System.out.println("CF20 report vectors passed");
    }

    private static byte[] hex(String input) {
        String[] pairs = input.split(" ");
        byte[] value = new byte[pairs.length];
        for (int i = 0; i < value.length; ++i) value[i] = (byte) Integer.parseInt(pairs[i], 16);
        return value;
    }

    private static void close(float actual, float expected, String field) {
        check(Math.abs(actual - expected) < 0.0001f, field);
    }

    private static void check(boolean ok, String field) {
        if (!ok) throw new AssertionError(field);
    }
}
