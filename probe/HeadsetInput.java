package org.cv10.displayprobe;

import android.hardware.usb.UsbConstants;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbDeviceConnection;
import android.hardware.usb.UsbEndpoint;
import android.hardware.usb.UsbInterface;
import android.hardware.usb.UsbManager;
import android.hardware.usb.UsbRequest;
import android.os.SystemClock;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.TimeoutException;

final class HeadsetInput {
    // Report descriptor read from CV10AC10.0.1.357 on the Fold7.
    private static final String CV10_DESCRIPTOR =
            "06ff000901a101850109077508953b8182850409077508957fb18285020903750895048182"
            + "850609057508951481828503090175089504818285040902750895048182c0";

    static String sample(UsbManager usb, UsbDevice d) {
        if (d == null || d.getVendorId() != 0x12d1 || d.getProductId() != 0x107e)
            return "HID: CV10 设备未连接";
        if (!usb.hasPermission(d)) return "HID: 缺少 USB 访问权限";
        for (int i = 0; i < d.getInterfaceCount(); i++) {
            UsbInterface iface = d.getInterface(i);
            if (iface.getId() != 3 || iface.getAlternateSetting() != 0 ||
                    iface.getInterfaceClass() != UsbConstants.USB_CLASS_HID ||
                    iface.getInterfaceSubclass() != 0 || iface.getInterfaceProtocol() != 0) continue;
            for (int j = 0; j < iface.getEndpointCount(); j++) {
                UsbEndpoint ep = iface.getEndpoint(j);
                if (ep.getAddress() != 0x84 || ep.getType() != UsbConstants.USB_ENDPOINT_XFER_INT) continue;
                UsbDeviceConnection c = null;
                try {
                    c = usb.openDevice(d);
                    if (c == null) return "HID: 无法打开 USB";
                    boolean forced = !c.claimInterface(iface, false);
                    if (forced && !c.claimInterface(iface, true)) return "HID: 接口 3 占用";
                    try {
                        byte[] descriptor = new byte[2048];
                        int size = c.controlTransfer(0x81, 6, 0x2200, iface.getId(),
                                descriptor, descriptor.length, 1000);
                        StringBuilder hex = new StringBuilder();
                        for (int k = 0; k < size; k++)
                            hex.append(String.format(Locale.ROOT, "%02x", descriptor[k] & 0xff));
                        android.util.Log.i("Cv10Probe", "HID descriptor bytes=" + size + " hex=" + hex);
                        String target = "HID iface=3 IN=0x84 claim=" + (forced ? "force" : "normal");
                        Capture passive = collect(c, ep);
                        if (!passive.silent || !CV10_DESCRIPTOR.contentEquals(hex))
                            return target + " " + passive.description;
                        int enabled = sensorReport(c, iface, 5);
                        if (enabled != 5) return target + " passive: " + passive.description + " enable=" + enabled;
                        Capture active;
                        int disabled;
                        try { active = collect(c, ep); }
                        finally { disabled = sensorReport(c, iface, 6); }
                        return target + " passive: " + passive.description + "\nactive: "
                                + active.description + " enable=" + enabled + " disable=" + disabled;
                    } finally {
                        c.releaseInterface(iface);
                    }
                } catch (RuntimeException error) {
                    return "HID: " + error;
                } finally {
                    if (c != null) c.close();
                }
            }
        }
        return "HID: 接口或端点与 CV10 实测不符";
    }

    private static int sensorReport(UsbDeviceConnection c, UsbInterface iface, int id) {
        byte[] payload = {(byte) id, 2, 0, 0, 0};
        return c.controlTransfer(0x21, 9, 0x0300 | id, iface.getId(), payload, payload.length, 1000);
    }

    private static final class Capture {
        final String description;
        final boolean silent;
        Capture(String description, boolean silent) {
            this.description = description;
            this.silent = silent;
        }
    }

    private static Capture collect(UsbDeviceConnection c, UsbEndpoint ep) {
        Map<Integer, Integer> lengths = new TreeMap<>();
        Map<Integer, Integer> ids = new TreeMap<>();
        ByteBuffer buffer = ByteBuffer.allocateDirect(ep.getMaxPacketSize()).order(ByteOrder.LITTLE_ENDIAN);
        ImuStats imu = new ImuStats();
        String first = "";
        String status = "complete";
        long start = SystemClock.elapsedRealtimeNanos();
        long firstNs = 0, lastNs = 0;
        int reports = 0;
        UsbRequest request = new UsbRequest();
        try {
            if (!request.initialize(c, ep)) return new Capture("初始化失败", false);
            long stop = SystemClock.elapsedRealtime() + 1500;
            long remaining;
            while ((remaining = stop - SystemClock.elapsedRealtime()) > 0) {
                buffer.clear();
                if (!request.queue(buffer)) {
                    status = "queue failed";
                    break;
                }
                try {
                    if (c.requestWait(remaining) != request) {
                        status = "disconnected or transfer failed";
                        break;
                    }
                } catch (TimeoutException timeout) {
                    request.cancel();
                    try {
                        c.requestWait(200);
                    } catch (TimeoutException ignored) {
                        // The connection may already be gone.
                    }
                    status = "deadline";
                    break;
                }
                int length = buffer.position();
                lengths.put(length, lengths.getOrDefault(length, 0) + 1);
                if (length == 0) continue;
                int id = buffer.get(0) & 0xff;
                if (id == 1 && length == 60) imu.add(buffer);
                ids.put(id, ids.getOrDefault(id, 0) + 1);
                lastNs = SystemClock.elapsedRealtimeNanos();
                if (reports++ == 0) {
                    firstNs = lastNs;
                    StringBuilder prefix = new StringBuilder();
                    int previewLength = id == 1 && length == 60 ? 44 : Math.min(16, length);
                    for (int k = 0; k < previewLength; k++)
                        prefix.append(String.format(Locale.ROOT, "%02x", buffer.get(k) & 0xff));
                    first = prefix.toString();
                }
            }
        } finally {
            request.close();
        }
        double hz = reports > 1 && lastNs > firstNs ? (reports - 1) * 1e9 / (lastNs - firstNs) : 0;
        return new Capture(String.format(Locale.ROOT,
                "reports=%d elapsed_ms=%d rate_hz=%.1f lengths=%s first_byte_ids_dec=%s first_prefix=%s status=%s",
                reports, (SystemClock.elapsedRealtimeNanos() - start) / 1000000, hz, lengths, ids, first, status)
                        + imu.summary(),
                reports == 0 && "deadline".equals(status));
    }

    private static final class ImuStats {
        int count, clockBreaks;
        long first, last;
        double acceleration, angularVelocity;

        void add(ByteBuffer b) {
            if (b.getInt(12) != 0 || b.getInt(28) != 1) return;
            double a = magnitude(b, 16), w = magnitude(b, 32);
            if (!Double.isFinite(a) || !Double.isFinite(w)) return;
            // Wallex encodes a nanosecond timestamp as two LE words, high word first.
            long ns = ((long)b.getInt(4) << 32) | Integer.toUnsignedLong(b.getInt(8));
            if (count == 0) first = ns;
            else if (ns <= last) clockBreaks++;
            last = ns;
            acceleration += a;
            angularVelocity += w;
            count++;
        }

        private double magnitude(ByteBuffer b, int offset) {
            return Math.hypot(Math.hypot(b.getFloat(offset), b.getFloat(offset + 4)), b.getFloat(offset + 8));
        }

        String summary() {
            if (count == 0) return "";
            double hz = clockBreaks == 0 && last > first ? (count - 1) * 1e9 / (last - first) : Double.NaN;
            return String.format(Locale.ROOT, " imu=%d device_hz=%.1f clock_breaks=%d mean_g=%.3f mean_deg_s=%.3f",
                    count, hz, clockBreaks, acceleration / count, angularVelocity / count);
        }
    }
}
