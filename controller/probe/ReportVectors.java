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
        check(active.stillnessDone && active.figureEightDone, "both firmware flags");
        check(!idle.stillnessDone && !idle.figureEightDone, "neither firmware flag");
        byte[] flags = new byte[20];
        flags[14] = 1;
        Cv10ControllerReport eight = Cv10ControllerReport.decode(flags);
        check(!eight.stillnessDone && eight.figureEightDone, "figure eight alone");
        check(java.util.Arrays.equals(Cv10ControllerCalibration.requestVersion(), hex("01 07 07 00")), "version query");
        check("4.0.5".equals(Cv10ControllerCalibration.parseVersionResponse(hex("01 07 09 01 aa 07 05 34 2e 30 2e 35"))),
                "firmware TLV after another field");
        check("4.0.5".equals(Cv10ControllerCalibration.parseVersionResponse(hex("01 07 07 80 05 34 2e 30 2e 35"))),
                "extended length");
        check(Cv10ControllerCalibration.parseVersionResponse(hex("01 07 07 05 34 2e 30 2e")) == null, "truncated TLV");
        check(Cv10ControllerCalibration.parseVersionResponse(hex("01 08 07 05 34 2e 30 2e 35")) == null, "unrelated reply");
        check(!Cv10ControllerCalibration.supportsFlags(null) && !Cv10ControllerCalibration.supportsFlags("4.0.4") &&
                Cv10ControllerCalibration.supportsFlags("4.0.5") && Cv10ControllerCalibration.supportsFlags("4.1.0"),
                "minimum firmware for calibration flags");
        calibrationVectors();
        headingVectors();
        System.out.println("CF20 report, firmware and right-side calibration vectors passed");
    }

    private static void calibrationVectors() {
        Cv10SimulationCalibration hold = new Cv10SimulationCalibration();
        float headYaw = 0.4f, handYaw = -0.6f, headPitch = 0.2f;
        long start = 1_000_000_000L;
        check(hold.sample(1, orientation(start - 150_000_000L, headYaw, headPitch, false),
                orientation(start, handYaw, 0f, false)) == null, "stale head cannot calibrate");
        check(hold.sample(1, orientation(start, headYaw, 1f, false), orientation(start, handYaw, 0f, false)) == null,
                "head must be approximately level");
        Cv10SimulationCalibration.Offset result = null;
        for (int i = 0; i <= 16; i++) {
            long now = start + i * 50_000_000L;
            result = hold.sample(1, orientation(now - 10_000_000L, headYaw, headPitch, i % 2 == 0),
                    orientation(now, handYaw, 0f, i % 2 == 1));
            if (i < 16) check(result == null, "800 ms hold required");
        }
        check(result != null, "steady samples including quaternion sign flips");
        close(result.yaw, headYaw - handYaw, "right-side yaw alignment");
        close(result.heightCorrection, -0.075f * ((float) Math.cos(headPitch) - 1f) -
                0.0805f * (float) Math.sin(headPitch), "neck height correction");
        long later = start + 2_000_000_000L;
        check(hold.sample(1, orientation(later, headYaw, headPitch, false), orientation(later, handYaw, 0f, false)) == null,
                "a gap resets the hold");
        check(hold.sample(1, orientation(later + 50_000_000L, headYaw, headPitch, false),
                orientation(later + 50_000_000L, handYaw + 0.2f, 0f, false)) == null, "movement resets the hold");
        check(hold.sample(2, orientation(later + 100_000_000L, headYaw, headPitch, false),
                orientation(later + 100_000_000L, handYaw, 0f, false)) == null, "new arm request starts a new hold");
    }

    private static Cv10SimulationCalibration.Orientation orientation(long ns, float yaw, float pitch, boolean negate) {
        float cY = (float) Math.cos(yaw / 2f), sY = (float) Math.sin(yaw / 2f);
        float cP = (float) Math.cos(pitch / 2f), sP = (float) Math.sin(pitch / 2f);
        float sign = negate ? -1f : 1f;
        return new Cv10SimulationCalibration.Orientation(ns, sign * cY * sP, sign * sY * cP,
                -sign * sY * sP, sign * cY * cP);
    }

    private static Cv10ControllerReport hand(float yaw, float pitch) {
        Cv10SimulationCalibration.Orientation q = orientation(0, yaw, pitch, false);
        java.nio.ByteBuffer bytes = java.nio.ByteBuffer.allocate(20);
        bytes.position(1);
        for (float field : new float[] {q.x, -q.y, -q.w, q.z})
            bytes.putShort((short) Math.round(field * 32767f));
        return Cv10ControllerReport.decode(bytes.array());
    }

    private static void headingVectors() {
        long now = 2_000_000_000L;
        Cv10SimulationCalibration.Heading alignment = new Cv10SimulationCalibration.Heading();
        Cv10SimulationCalibration.Orientation head = orientation(now, 0.4f, 0.1f, false);
        float opposite = 0.4f - (float)Math.PI;
        check(Float.isNaN(alignment.resolve(1, 0, Float.NaN, null, now, hand(opposite, 0))), "wait for HMD");
        check(Float.isNaN(alignment.resolve(1, 0, Float.NaN, head, now, hand(opposite, 1.57f))), "vertical hand");
        float correction = alignment.resolve(1, 0, Float.NaN, head, now, hand(opposite, 0.1f));
        check(Math.abs(Math.abs(correction) - Math.PI) < 0.0001, "opposite bearing aligned");
        close(alignment.resolve(1, 0, Float.NaN, orientation(now, -1f, 0f, false), now, hand(-1f, 0.3f)),
                correction, "head and hand can turn independently");
        close(alignment.resolve(1, 1, Float.NaN, head, now, hand(0.1f, 0f)), 0.3f, "long Home re-aligns");
        close(alignment.resolve(1, 1, 0f, head, now, hand(opposite, 0)), 0f, "saved zero calibration wins");
        close(alignment.resolve(2, 0, -0.2f, head, now, hand(opposite, 0)), -0.2f, "reconnect honors saved yaw");
        check(Float.isNaN(alignment.resolve(3, 0, Float.NaN, head, now + 200_000_000L, hand(0.1f, 0))),
                "stale HMD cannot anchor a new link");
        close(alignment.resolve(3, 0, Float.NaN, head, now, hand(0.2f, 0)), 0.2f, "fresh reconnect");
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
