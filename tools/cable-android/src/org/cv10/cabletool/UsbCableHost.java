package org.cv10.cabletool;

import android.app.Activity;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbDeviceConnection;
import android.hardware.usb.UsbManager;
import android.os.Build;
import android.os.SystemClock;
import android.util.Log;

import java.io.IOException;
import java.util.Locale;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;

final class UsbCableHost implements Vl105.Host {
    static final String TAG = "Cv10CableTool";
    private static final String ACTION = "org.cv10.cabletool.USB_PERMISSION";
    private static final int USB_TIMEOUT = 1500;
    private final Activity activity;
    private final UsbManager manager;
    private final Consumer<String> progress;
    private String bus;
    private volatile Grant grant;

    private static final class Grant {
        final CountDownLatch callback = new CountDownLatch(1);
        volatile RuntimeException error;
    }

    private static final class DeviceGone extends IOException {
        DeviceGone() {
            super("线盒的 USB 地址已改变。");
        }
    }

    private final BroadcastReceiver receiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            Grant current = grant;
            if (ACTION.equals(intent.getAction()) && current != null) {
                current.callback.countDown();
            }
        }
    };

    UsbCableHost(Activity activity, Consumer<String> progress) {
        this.activity = activity;
        this.progress = progress;
        manager = activity.getSystemService(UsbManager.class);
        IntentFilter filter = new IntentFilter(ACTION);
        if (Build.VERSION.SDK_INT >= 33) {
            activity.registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            activity.registerReceiver(receiver, filter);
        }
    }

    void close() {
        activity.unregisterReceiver(receiver);
    }

    @Override public Vl105.Transport initial() throws IOException {
        UsbDevice device = find(null);
        if (device == null) {
            throw new IOException("未发现 2109:0105 CV10 线盒。");
        }
        String name = device.getDeviceName();
        bus = name.substring(0, name.lastIndexOf('/') + 1);
        return open(device);
    }

    @Override public Vl105.Transport awaitMode(boolean runtime) throws IOException {
        // Allow the old USB address to disappear before requesting access again.
        Vl105.sleep(700);
        long deadline = SystemClock.elapsedRealtime() + 10_000;
        IOException lastTransferFailure = null;
        while (SystemClock.elapsedRealtime() < deadline) {
            UsbDevice device = find(bus);
            if (device != null) {
                Connection connection = null;
                try {
                    connection = open(device);
                    if (Vl105.isRuntime(connection) == runtime) {
                        Log.i(TAG, (runtime ? "Runtime " : "ROM ") + device.getDeviceName());
                        Connection ready = connection;
                        connection = null;
                        return ready;
                    }
                } catch (TransferFailed | DeviceGone retry) {
                    lastTransferFailure = retry;
                } finally {
                    if (connection != null) connection.close();
                }
            }
            Vl105.sleep(250);
        }
        throw new IOException(runtime ? "未检测到线盒重新进入运行态。" : "未检测到线盒进入维护模式。",
                lastTransferFailure);
    }

    private UsbDevice find(String prefix) throws IOException {
        UsbDevice found = null;
        for (UsbDevice device : manager.getDeviceList().values()) {
            if (device.getVendorId() == 0x2109 && device.getProductId() == 0x0105
                    && device.getDeviceClass() == 0x11
                    && (prefix == null || device.getDeviceName().startsWith(prefix))) {
                if (found != null) {
                    throw new IOException("检测到多个相同型号的 USB 设备，无法确认目标线盒。");
                }
                found = device;
            }
        }
        return found;
    }

    private Connection open(UsbDevice device) throws IOException {
        if (!manager.hasPermission(device)) {
            awaitGrant(device);
        }
        try {
            UsbDeviceConnection connection = manager.openDevice(device);
            if (connection == null) {
                if (!manager.getDeviceList().containsKey(device.getDeviceName())) throw new DeviceGone();
                throw new TransferFailed("Android 无法打开线盒的 USB 控制端点。");
            }
            return new Connection(connection);
        } catch (SecurityException failure) {
            throw new IOException("Android 未授予线盒 USB 访问权限。", failure);
        }
    }

    private void awaitGrant(UsbDevice device) throws IOException {
        Grant requested = new Grant();
        grant = requested;
        progress.accept("请在 Android 提示中允许访问线盒。维护模式重新枚举后可能再次提示。");
        Log.i(TAG, "Requesting USB permission for " + device.getDeviceName());
        activity.runOnUiThread(() -> {
            try {
                Intent intent = new Intent(ACTION).setPackage(activity.getPackageName());
                PendingIntent pending = PendingIntent.getBroadcast(activity, device.getDeviceId(), intent,
                        PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_ONE_SHOT);
                manager.requestPermission(device, pending);
            } catch (RuntimeException failure) {
                requested.error = failure;
                requested.callback.countDown();
            }
        });
        try {
            long deadline = SystemClock.elapsedRealtime() + 45_000;
            while (SystemClock.elapsedRealtime() < deadline) {
                boolean answered = requested.callback.await(200, TimeUnit.MILLISECONDS);
                if (requested.error != null) {
                    throw new IOException("无法打开 Android USB 授权提示。", requested.error);
                }
                if (!manager.getDeviceList().containsKey(device.getDeviceName())) throw new DeviceGone();
                if (manager.hasPermission(device)) return;
                if (answered) throw new IOException("Android USB 授权被拒绝。");
            }
            throw new IOException("等待 Android USB 授权超时。");
        } catch (InterruptedException failure) {
            Thread.currentThread().interrupt();
            throw new IOException("USB 授权等待已中断。", failure);
        } finally {
            grant = null;
        }
    }

    private static final class TransferFailed extends IOException {
        TransferFailed(String message) {
            super(message);
        }
    }

    private static final class Connection implements Vl105.Transport {
        private final UsbDeviceConnection usb;

        Connection(UsbDeviceConnection usb) {
            this.usb = usb;
        }

        @Override public byte[] read(int request, int value, int index, int length) throws IOException {
            byte[] data = new byte[length];
            transfer(0xc0, request, value, index, data);
            return data;
        }

        @Override public void write(int request, int value, int index, byte[] data) throws IOException {
            transfer(0x40, request, value, index, data);
        }

        private void transfer(int type, int request, int value, int index, byte[] data) throws IOException {
            int actual = usb.controlTransfer(type, request, value, index, data, data.length, USB_TIMEOUT);
            if (actual != data.length) {
                throw new TransferFailed(String.format(Locale.ROOT,
                        "USB 请求 0x%02X 失败（返回 %d，预期 %d 字节）。", request, actual, data.length));
            }
        }

        @Override public void close() {
            usb.close();
        }
    }
}
