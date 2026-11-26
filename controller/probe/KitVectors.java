// SPDX-License-Identifier: GPL-3.0-or-later
package org.freedesktop.monado.openxr_runtime;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayDeque;
import java.util.Arrays;

final class KitVectors {
    public static void main(String[] args) throws IOException, InterruptedException {
        byte[] report = new byte[Cv10KitReport.HID_REPORT_SIZE];
        ByteBuffer fields = ByteBuffer.wrap(report).order(ByteOrder.LITTLE_ENDIAN);
        check(Cv10KitReport.head(report) == null, "unmarked head report");
        check(Cv10KitReport.hand(report, false) == null, "unmarked controller report");
        ByteBuffer headFields = fields.duplicate().order(ByteOrder.BIG_ENDIAN);
        headFields.putLong(12, 987654321L);
        headFields.putShort(21, (short) 100);
        headFields.putShort(23, (short) 200);
        headFields.putShort(25, (short) -100);
        headFields.put(27, (byte) 1);
        headFields.putShort(28, (short) -200);
        headFields.putShort(30, (short) 300);
        headFields.putShort(32, (short) -0x1234);
        Cv10KitReport.Head head = Cv10KitReport.head(report);
        check(head != null && head.deviceNs == 987654321L, "head clock");
        close(head.ax, -0.47824f, "head X accelerometer");
        close(head.ay, 0.23912f, "head Y accelerometer");
        close(head.az, -0.23912f, "head Z accelerometer");
        close(head.gx, (float) Math.toRadians(-21), "head X gyroscope");
        close(head.gy, (float) Math.toRadians(-14), "head Y gyroscope");
        close(head.gz, (float) Math.toRadians(-0x1234 * 0.07), "head Z gyroscope");
        check(Cv10KitReport.head(new byte[33]) == null, "short head report");

        fields.put(0x30, (byte) 0x20);
        fields.put(0x31, (byte) Cv10KitReport.Hand.CONFIRM);
        fields.putInt(0x32, Integer.reverseBytes(0x80000012));
        fields.putShort(0x36, (short) -100);
        fields.putShort(0x3c, (short) 200);
        fields.putShort(0x42, (short) -1);
        fields.put(0x48, (byte) 2);
        fields.put(0x49, (byte) 88);
        fields.putShort(0x4a, (short) -10);
        fields.putShort(0x4c, (short) 20);
        fields.putShort(0x4e, (short) -1499);
        fields.putShort(0x50, (short) -1642);
        fields.put(0x52, (byte) 0x41);
        fields.put(0x53, (byte) 1);
        fields.put(0x55, (byte) Cv10KitReport.Hand.BACK);
        fields.putInt(0x56, Integer.reverseBytes(2345));
        fields.put(0x6d, (byte) 67);
        Cv10KitReport.Hand left = Cv10KitReport.hand(report, false);
        Cv10KitReport.Hand right = Cv10KitReport.hand(report, true);
        check(left != null && right != null, "two hand records");
        check(left.clockTicks == 0x80000012L && left.clockMultiplier == 2 && right.clockTicks == 2345, "hand clocks");
        check(left.buttons == Cv10KitReport.Hand.CONFIRM && right.buttons == Cv10KitReport.Hand.BACK,
                "left and right button independence");
        check(left.batteryField == 88 && right.batteryField == 67, "hand battery fields");
        check(left.touches == 0x41 && left.gripTouch == 1 && left.mx == 65535, "touch and magnetic sensor fields");
        close(left.ax, -0.4788404f, "hand accelerometer");
        close(left.gx, 0.4261056f, "hand gyroscope");
        close(left.trigger, -250f, "trigger");
        close(left.grip, 500f, "grip");
        close(left.stickX, 0f, "stick X");
        close(left.stickY, 1f, "stick Y");
        check(Cv10KitReport.hand(java.util.Arrays.copyOf(report, 119), true) == null, "short right record");
        fields.put(0x30, (byte) 0x29);
        check(Cv10KitReport.hand(report, false) == null, "non-hand record");

        final int stride = 1312;
        final int position = 7;
        ByteBuffer y8 = ByteBuffer.allocate(position + 480 * stride + 0x1d).order(ByteOrder.LITTLE_ENDIAN);
        y8.position(position);
        check(Cv10KitReport.frame(y8, stride, 1) == null, "zero camera timestamp");
        int base = position + 480 * stride;
        y8.putLong(base, 123456789L);
        y8.putInt(base + 0x12, 321);
        y8.putShort(base + 0x16, (short) 6800);
        y8.put(base + 0x1c, (byte) 0x81);
        Cv10KitReport.Frame image = Cv10KitReport.frame(y8, stride, 1);
        check(image != null && image.deviceNs == 123456789L && image.frameNumber == 321 &&
                image.exposureUs == 6800 && image.frameMarker == 0x81,
                "padded Y8 camera frame metadata");
        int lastRow = position + (Cv10KitReport.CAMERA_HEIGHT - 1) * stride;
        y8.put(position + 639, (byte) 0x71);
        y8.put(position + 640, (byte) 0x72);
        y8.put(lastRow + 639, (byte) 0x73);
        y8.put(lastRow + 1279, (byte) 0x74);
        Cv10KitReport.StereoFrame stereo = Cv10KitReport.stereo(y8, stride, 1);
        check(stereo != null && stereo.camera0.length == 307200 && stereo.camera1.length == 307200 &&
                stereo.camera0[639] == 0x71 && stereo.camera1[0] == 0x72 &&
                stereo.camera0[307199] == 0x73 && stereo.camera1[307199] == 0x74 &&
                stereo.trailer.length == 0x1d && (stereo.trailer[0x1c] & 0xff) == 0x81 &&
                y8.position() == position, "padded Y8 stereo split and metadata preservation");
        check(Cv10KitReport.frame(y8, stride, 2) == null, "invalid Y8 pixel stride");
        y8.limit(y8.limit() - 1);
        check(Cv10KitReport.frame(y8, stride, 1) == null && y8.position() == position, "truncated Y8 camera frame");

        Cv10KitCalibration.Calibration android = Cv10KitCalibration.read(
                new CalibrationLink(false, false), Cv10KitCalibration.Component.LOCATOR);
        check(android != null && android.protocol().equals("Android") &&
                Arrays.equals(android.deviceHash, new byte[] {0x42}) &&
                Arrays.equals(android.data, new byte[] {1, 2, 2, 3}), "Android calibration sequence");
        Cv10KitCalibration.Calibration windows = Cv10KitCalibration.read(
                new CalibrationLink(true, false), Cv10KitCalibration.Component.RIGHT);
        check(windows != null && windows.protocol().equals("Windows") && windows.deviceHash.length == 33 &&
                windows.data.length == 812 && windows.data[28 * 28] == 29, "Windows calibration fallback and chunk count");
        try {
            Cv10KitCalibration.read(new CalibrationLink(true, false, 27), Cv10KitCalibration.Component.RIGHT);
            throw new AssertionError("an undersized Windows calibration must fail");
        } catch (IOException expected) {
            check(expected.getMessage().contains("unexpected size"), "Windows calibration size");
        }
        try {
            Cv10KitCalibration.read(new CalibrationLink(false, true), Cv10KitCalibration.Component.LOCATOR);
            throw new AssertionError("an incomplete calibration must fail");
        } catch (IOException expected) {
            check(expected.getMessage().contains("chunk 2"), "missing chunk");
        }
        checkLocatorCameras();
        checkCalibratedImusAndLeds();
        checkSlamParameters();
        System.out.println("Huawei 6DoF kit report vectors passed");
    }

    private static void checkCalibratedImusAndLeds() throws IOException {
        byte[] locator = new byte[0x3de];
        putImu(ByteBuffer.wrap(locator).order(ByteOrder.LITTLE_ENDIAN), 0x2a0, 500);
        Cv10KitCalibration.ImuCalibration head = Cv10KitCalibration.locatorImu(locator);
        check(head.needsCompensation, "calibrated IMU compensation flag");
        close(head.gyroHz, 500, "calibrated IMU gyro rate");
        close(head.accelHz, 501, "calibrated IMU accelerometer rate");
        close((float) head.gyroBias[0], 0.75f, "calibrated gyro bias");
        close((float) head.accelBias[0], 0.25f, "calibrated accelerometer bias");
        close((float) head.gyroToAccel[3], 1, "calibrated cross-sensor rotation");
        close((float) head.accelBiasSigma, 0.05f, "calibrated accelerometer bias sigma");

        byte[] hand = new byte[0x32c];
        ByteBuffer fields = ByteBuffer.wrap(hand).order(ByteOrder.LITTLE_ENDIAN);
        putImu(fields, 0x240, 250);
        double sin45 = Math.sqrt(0.5);
        fields.putDouble(0x50, sin45);
        fields.putDouble(0x58, sin45);
        fields.putDouble(0x60, 0.1);
        fields.putDouble(0x98, -0.035);
        fields.putDouble(0x98 + 15 * 24 + 16, 0.047);
        fields.putDouble(0x218, -0.032);
        Cv10KitCalibration.HandCalibration decoded = Cv10KitCalibration.hand(hand);
        close(decoded.imu.gyroHz, 250, "hand IMU starts at 0x240");
        check(decoded.ledPositions.length == 16, "sixteen LEDs");
        close((float) decoded.ledPositions[0][0], -0.035f, "first LED X");
        close((float) decoded.ledPositions[15][2], 0.047f, "last LED Z");
        close((float) decoded.cameraToImuDelaySeconds, -0.032f, "hand camera to IMU delay");
        close((float) decoded.imuToHandle[2], (float) -sin45, "hand extrinsic uses conjugate Z");
        close((float) decoded.imuToHandle[4], 0, "hand extrinsic x");
        close((float) decoded.imuToHandle[5], 0.1f, "hand extrinsic y rotates negative translation");
        try {
            Cv10KitCalibration.hand(Arrays.copyOf(hand, 0x319));
            throw new AssertionError("a truncated hand IMU calibration must fail");
        } catch (IOException expected) {
            check(expected.getMessage().contains("Truncated"), "hand IMU bounds");
        }
        fields.putFloat(0x241, Float.POSITIVE_INFINITY);
        try {
            Cv10KitCalibration.hand(hand);
            throw new AssertionError("a non-finite hand IMU rate must fail");
        } catch (IOException expected) {
            check(expected.getMessage().contains("Invalid"), "hand IMU record validation");
        }
    }

    private static void putImu(ByteBuffer fields, int start, float rate) {
        fields.putFloat(start + 1, rate);
        fields.putFloat(start + 5, rate + 1);
        fields.put(start + 9, (byte) 1);
        fields.putDouble(start + 0x0a, 0.75);
        fields.putDouble(start + 0x52, 0.25);
        fields.putDouble(start + 0xb2, 1);
        fields.putDouble(start + 0xd2, 0.05);
    }

    private static void checkLocatorCameras() throws IOException {
        byte[] data = new byte[0x3de];
        ByteBuffer fixture = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN);
        for (int i = 0; i < 2; i++) {
            int start = i == 0 ? 0x40 : 0x170;
            fixture.put(start, (byte) i);
            fixture.putInt(start + 0x01, 640);
            fixture.putInt(start + 0x05, 480);
            fixture.putFloat(start + 0x09, 15f);
            fixture.putDouble(start + 0x1e, -0.029 + i * 0.001);
            fixture.putDouble(start + 0x26, 230 + i);
            fixture.putDouble(start + 0x2e, 232 + i);
            fixture.putDouble(start + 0x48, 0.25 + i);
            fixture.putFloat(start + 0x8c, 3.25f + i);
            fixture.putDouble(start + 0xd4, 0.5 + i);
            fixture.putFloat(start + 0x10c, 0.2f + i);
        }
        Cv10KitCalibration.CameraCalibration[] cameras = Cv10KitCalibration.locatorCameras(data);
        check(cameras.length == 2 && cameras[0].id == 0 && cameras[1].id == 1, "stereo camera records");
        close(cameras[0].framesPerSecond, 15f, "camera rate");
        close((float) cameras[1].cameraToImuDelaySeconds, -0.028f, "camera to IMU delay");
        close((float) cameras[1].intrinsics[0], 231f, "camera intrinsics");
        close((float) cameras[1].distortion[0], 1.25f, "camera distortion");
        close((float) cameras[0].autofocusCompensation[0], 3.25f, "camera autofocus");
        close((float) cameras[1].tcm[0], 1.5f, "camera extrinsics");
        close(cameras[1].pixelSigma, 1.2f, "camera pixel sigma");
        try {
            Cv10KitCalibration.locatorCameras(Arrays.copyOf(data, 0x29f));
            throw new AssertionError("a truncated second camera must fail");
        } catch (IOException expected) {
            check(expected.getMessage().contains("Truncated"), "stereo bounds");
        }
        fixture.putDouble(0x170 + 0x26, Double.NaN);
        try {
            Cv10KitCalibration.locatorCameras(data);
            throw new AssertionError("non-finite intrinsics must fail");
        } catch (IOException expected) {
            check(expected.getMessage().contains("Invalid"), "stereo intrinsics validation");
        }
    }

    private static void checkSlamParameters() throws IOException {
        byte[] locator = new byte[0x3de];
        ByteBuffer fields = ByteBuffer.wrap(locator).order(ByteOrder.LITTLE_ENDIAN);
        for (int i = 0; i < 2; i++) {
            int camera = 0x40 + i * 0x130;
            fields.put(camera, (byte) i);
            fields.putInt(camera + 0x01, 640);
            fields.putInt(camera + 0x05, 480);
            fields.putFloat(camera + 0x09, 15 + i);
            fields.putDouble(camera + 0x0e, 0.001);
            fields.putDouble(camera + 0x16, 0.01);
            fields.putDouble(camera + 0x1e, -0.032);
            fields.putDouble(camera + 0x26, 230 + i);
            fields.putDouble(camera + 0x2e, 232 + i);
            fields.put(camera + 0x46, (byte) 1);
            fields.put(camera + 0x47, (byte) 1);
            for (int k = 0; k < 8; k++) fields.putDouble(camera + 0x48 + k * 8, k + 0.5);
            fields.putFloat(camera + 0x8c, 4.25f);
            double sin45 = Math.sqrt(0.5);
            fields.putDouble(camera + 0xac, sin45);
            fields.putDouble(camera + 0xb4, sin45);
            fields.putDouble(camera + 0xbc, i * 0.02);
        }
        int imuStart = 0x2a0;
        putImu(fields, imuStart, 500);
        fields.putDouble(imuStart + 0x22, 2);
        fields.putDouble(imuStart + 0x2a, 3);
        fields.putDouble(imuStart + 0x32, 4);
        fields.putDouble(imuStart + 0x3a, 0.25);
        fields.putDouble(imuStart + 0x6a, 5);
        fields.putDouble(imuStart + 0x72, 6);
        fields.putDouble(imuStart + 0x7a, 8);
        fields.putDouble(imuStart + 0xaa, 1);
        fields.putDouble(imuStart + 0xb2, 1);

        Cv10KitCalibration.CameraCalibration[] cameras = Cv10KitCalibration.locatorCameras(locator);
        Cv10KitCalibration.ImuCalibration imu = Cv10KitCalibration.locatorImu(locator);
        byte[] bytes = Cv10KitSlamParameters.encode(cameras, imu);
        check(bytes.length == 2112, "SLAM parameter ABI size");
        ByteBuffer config = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
        check(config.getInt(0) == 2 && config.getInt(0x138) == 1 && config.getInt(0x148) == 640,
                "SLAM camera count, second ID and stride");
        close(config.getFloat(0x14c), 16, "SLAM second camera rate");
        close((float) config.getDouble(0x20), 4.25f, "SLAM autofocus compensation");
        close((float) config.getDouble(0x48), 230, "SLAM camera intrinsics");
        close((float) config.getDouble(0x88), 5.5f, "SLAM higher radial distortion");
        close((float) config.getDouble(0xa0), 3.5f, "SLAM tangential distortion");
        close((float) config.getDouble(0xb8), -1, "SLAM camera-to-IMU rotation");
        close((float) config.getDouble(0x1f8), 0.02f, "SLAM second camera-to-IMU translation");
        close((float) config.getDouble(0x258), 1, "SLAM homogeneous matrix bottom row");
        close((float) config.getDouble(0x260), 0.001f, "SLAM camera readout");
        close(config.getFloat(0x4d4), 1000, "SLAM Android acceleration rate");
        close(config.getFloat(0x4d8), 1000, "SLAM Android gyroscope rate");
        close((float) config.getDouble(0x4e0), -0.032f, "SLAM first camera delay");
        close((float) config.getDouble(0x4e8), 0.01f, "SLAM first camera exposure shift");
        close(config.getFloat(0x578), 3, "SLAM inverse cross-sensor rotation and acceleration scale");
        close(config.getFloat(0x580), -2.5f, "SLAM inverse cross-sensor rotation and acceleration scale sign");
        close(config.getFloat(0x598), -0.05f, "SLAM acceleration bias");
        close(config.getFloat(0x5a8), 0.5f, "SLAM gyroscope misalignment");
        close(config.getFloat(0x5c8), -0.375f, "SLAM gyroscope bias");
        close((float) config.getDouble(0x5f0), 0.05f, "SLAM accelerometer bias noise");
        fields.putDouble(imuStart + 0x22, 0);
        try {
            Cv10KitSlamParameters.encode(cameras, Cv10KitCalibration.locatorImu(locator));
            throw new AssertionError("a singular IMU scale matrix must fail");
        } catch (IOException expected) {
            check(expected.getMessage().contains("Singular"), "SLAM singular calibration");
        }
    }

    private static final class CalibrationLink implements Cv10KitCalibration.Link {
        private final boolean windows, dropLast;
        private final int chunkBytes;
        private final ArrayDeque<byte[]> replies = new ArrayDeque<>();

        CalibrationLink(boolean windows, boolean dropLast) {
            this(windows, dropLast, windows ? 28 : 2);
        }

        CalibrationLink(boolean windows, boolean dropLast, int chunkBytes) {
            this.windows = windows;
            this.dropLast = dropLast;
            this.chunkBytes = chunkBytes;
        }

        @Override
        public byte[] read(int timeoutMs) {
            check(timeoutMs > 0, "positive calibration timeout");
            return replies.poll();
        }

        @Override
        public void write(byte[] report) {
            int selector = windows ? 0x82 : 0x81;
            check(report.length == 64 && report[0] == 2 && (report[1] & 0xff) == selector &&
                    (report[2] & 0xff) == 0x80 && report[3] == 0 && report[63] == 0, "HID request framing");
            int sequence = report[6] & 0xff;
            if (dropLast && sequence == 2) return;
            byte[] reply = new byte[128];
            reply[0x2c] = (byte) 0x80;
            reply[0x2d] = (byte) selector;
            reply[0x30] = report[5];
            if (reply[0x30] == 0x2a) {
                check(sequence == 0, "hash sequence");
                if (windows && report[4] == 2) return;
                check(report[4] == (windows ? 5 : 2), "hash dialect");
                reply[0x2f] = 1;
                reply[0x31] = 0x42;
            } else {
                check(reply[0x30] == 0x29 && report[4] == (windows ? 5 : 2), "chunk command");
                reply[0x2f] = (byte) (3 + chunkBytes);
                reply[0x31] = (byte) (windows ? 0 : 2);
                reply[0x32] = (byte) sequence;
                reply[0x33] = (byte) sequence;
                reply[0x34] = (byte) (sequence + 1);
                replies.add(Arrays.copyOf(reply, 0x34));
            }
            byte[] unrelated = reply.clone();
            unrelated[0x2d] = 0x44;
            replies.add(unrelated);
            replies.add(reply);
        }
    }

    private static void close(float actual, float expected, String field) {
        check(Math.abs(actual - expected) < 0.0001f, field);
    }

    private static void check(boolean ok, String field) {
        if (!ok) throw new AssertionError(field);
    }
}
