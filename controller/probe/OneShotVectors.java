// SPDX-License-Identifier: GPL-3.0-or-later
package org.freedesktop.monado.openxr_runtime;

public final class OneShotVectors {
    private static final long START = 1_000_000_000L;
    private static final long STEP = 10_000_000L;

    public static void main(String[] args) {
        Cv10ControllerReport atRest = report(0, 8, 0, 0);
        Cv10OneShotCalibration calibration = new Cv10OneShotCalibration();
        check(!calibration.start(START, atRest, heading(START - 250_000_000L, 0f), 1.65f), "stale head");
        check(!calibration.start(START, report(0, 0, 0, 0), heading(START, 0f), 1.65f), "missing gravity");
        check(calibration.start(START, atRest, heading(START, 0f), 1.65f), "start at right temple");
        check(!calibration.sample(START + 200_000_000L, atRest), "abort over a report gap");
        calibration.reset();

        check(calibration.start(START, atRest, heading(START, 0f), 1.65f), "start translation");
        for (int i = 1; i <= 20; i++) {
            check(calibration.sample(START + i * STEP, report(0, 8, 4, 0)), "accelerate forward");
        }
        check(calibration.finish() == null, "no finish while moving");
        for (int i = 21; i <= 60; i++) {
            int az = i <= 40 ? -4 : 0;
            check(calibration.sample(START + i * STEP, report(0, 8, az, 0)), "brake and settle");
        }
        Cv10OneShotCalibration.Position forward = calibration.finish();
        check(forward != null, "valid stop");
        near(forward.x, 0.09f, "right-side origin");
        near(forward.y, 1.65f, "height");
        near(forward.z, -0.198f, "integrated negative Z displacement");

        calibration.reset();
        float quarterTurn = (float) (Math.PI / 2);
        check(calibration.start(START, atRest, heading(START, quarterTurn), 1.65f), "start with different head yaw");
        for (int i = 1; i <= 60; i++) {
            int az = i <= 20 ? 4 : i <= 40 ? -4 : 0;
            check(calibration.sample(START + i * STEP, report(0, 8, az, 0)), "yaw-aligned move");
        }
        Cv10OneShotCalibration.Position left = calibration.finish();
        check(left != null, "valid stop at different yaw");
        near(left.x, -0.198f, "move follows the head heading");
        near(left.z, -0.09f, "right-side origin follows the head heading");

        calibration.reset();
        check(calibration.start(START, atRest, heading(START, 0f), 1.65f), "start gyro-only case");
        for (int i = 1; i <= 60; i++) {
            // Turning around vertical leaves the sensed gravity unchanged.
            check(calibration.sample(START + i * STEP, report(0, 8, 0, i <= 20 ? 5 : 0)), "pure yaw");
        }
        check(calibration.finish() == null, "gyro-only motion must not be saved as a displacement");
        System.out.println("CF20 one-move calibration vectors passed");
    }

    private static Cv10SimulationCalibration.Orientation heading(long time, float yaw) {
        return new Cv10SimulationCalibration.Orientation(time, 0f, (float) Math.sin(yaw / 2f), 0f,
                (float) Math.cos(yaw / 2f));
    }

    private static Cv10ControllerReport report(int ax, int ay, int az, int gy) {
        byte[] data = new byte[Cv10ControllerReport.SIZE];
        data[5] = (byte) 0x80;
        data[6] = 1; // negative packed W becomes +1
        data[9] = (byte) ax;
        data[10] = (byte) ay;
        data[11] = (byte) az;
        data[13] = (byte) gy;
        return Cv10ControllerReport.decode(data);
    }

    private static void near(float actual, float expected, String message) {
        check(Math.abs(actual - expected) <= 0.012f, message + ": " + actual + " vs " + expected);
    }

    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
