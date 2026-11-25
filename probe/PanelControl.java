package org.cv10.displayprobe;

import android.hardware.usb.*;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

final class PanelControl {
    static UsbDevice find(UsbManager usb) {
        for (UsbDevice d : usb.getDeviceList().values())
            if (d.getVendorId() == 0x12d1 && d.getProductId() == 0x107e) return d;
        return null;
    }

    private static String command(UsbDeviceConnection c, UsbEndpoint out, UsbEndpoint in,
                                  String cmd) throws IOException {
        byte[] request = (cmd + "\r\n").getBytes(StandardCharsets.US_ASCII);
        if (c.bulkTransfer(out, request, request.length, 1500) != request.length)
            throw new IOException(cmd + " 发送未完成");
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        byte[] packet = new byte[in.getMaxPacketSize()];
        long end = android.os.SystemClock.elapsedRealtime() + 2000;
        while (android.os.SystemClock.elapsedRealtime() < end && bytes.size() < 4096) {
            int n = c.bulkTransfer(in, packet, packet.length, 250);
            if (n <= 0) continue;
            bytes.write(packet, 0, n);
            String s = bytes.toString("US-ASCII");
            if (s.matches("(?s).*(^|[\r\n])(OK|ERROR)[\r\n]+$")) break;
        }
        String result = bytes.toString("US-ASCII").trim();
        return result.isEmpty() ? "无应答" : result;
    }

    static String wake(UsbManager usb, UsbDevice d) throws IOException {
        UsbInterface port = null;
        for (int i = 0; i < d.getInterfaceCount(); i++) {
            UsbInterface iface = d.getInterface(i);
            if (iface.getId() == 0 && iface.getInterfaceClass() == 255 &&
                    iface.getInterfaceSubclass() == 0x13 && iface.getInterfaceProtocol() == 0x12)
                port = iface;
        }
        if (port == null) throw new IOException("未找到已验证的 PCUI 接口");
        UsbEndpoint out = null, in = null;
        for (int i = 0; i < port.getEndpointCount(); i++) {
            UsbEndpoint ep = port.getEndpoint(i);
            if (ep.getType() != UsbConstants.USB_ENDPOINT_XFER_BULK) continue;
            if (ep.getAddress() == 0x01) out = ep;
            if (ep.getAddress() == 0x81) in = ep;
        }
        if (in == null || out == null) throw new IOException("PCUI 端点不符");
        UsbDeviceConnection c = usb.openDevice(d);
        if (c == null) throw new IOException("无法打开 USB");
        try {
            if (!c.claimInterface(port, false)) throw new IOException("无法打开 PCUI");
            try {
                String model = command(c, out, in, "AT^DEVMODEL?");
                String version = command(c, out, in, "AT^SWVER");
                String report = "DEVMODEL: " + model + "\nSWVER: " + version;
                if (!(model + " " + version).toUpperCase(Locale.ROOT).contains("CV10"))
                    return report + "\n未取得 CV10 身份应答，未发送开屏指令";
                return report + "\nSWITCHSCREEN=1: " + command(c, out, in, "AT^SWITCHSCREEN=1");
            } finally { c.releaseInterface(port); }
        } finally { c.close(); }
    }
}
