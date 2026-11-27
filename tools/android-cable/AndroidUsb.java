package org.cv10.cableupdater;

import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbDeviceConnection;
import android.hardware.usb.UsbInterface;
import android.hardware.usb.UsbManager;
import android.os.Build;
import android.os.SystemClock;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

final class AndroidUsb implements Updater.Host, AutoCloseable {
    private static final String GRANT_USB = "org.cv10.cableupdater.USB_PERMISSION";
    private final Context context;
    private final UsbManager manager;
    private final Updater.Status status;
    private volatile Grant waiting;

    private static final class Grant {
        final String token = UUID.randomUUID().toString();
        final CountDownLatch reply = new CountDownLatch(1);
    }

    private final BroadcastReceiver permission = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            Grant current = waiting;
            if (current != null && current.token.equals(intent.getStringExtra("request"))) {
                current.reply.countDown();
            }
        }
    };

    AndroidUsb(Context context, Updater.Status status) {
        this.context = context;
        this.manager = context.getSystemService(UsbManager.class);
        this.status = status;
        IntentFilter filter = new IntentFilter(GRANT_USB);
        if (Build.VERSION.SDK_INT >= 33) {
            context.registerReceiver(permission, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            context.registerReceiver(permission, filter);
        }
    }

    @Override public void close() {
        context.unregisterReceiver(permission);
    }

    private UsbDevice findCable() throws IOException {
        if (manager == null) {
            throw new IOException("此手机未提供 USB Host。");
        }
        UsbDevice cable = null;
        for (UsbDevice device : manager.getDeviceList().values()) {
            int vid = device.getVendorId();
            int pid = device.getProductId();
            if (vid == 0x12d1 && (pid == 0x107e || pid == 0x1092 || pid == 0x1093)) {
                throw new IOException("检测到头显接口，请拔下 CV10 再开始升级。");
            }
            if (vid == 0x2109 && pid == 0x0105) {
                if (cable != null) {
                    throw new IOException("检测到多根匹配的线，只保留待升级的原厂线。");
                }
                cable = device;
            }
        }
        return cable;
    }

    @Override public void checkSetup() throws IOException {
        if (findCable() == null) {
            throw new IOException("未检测到线控。请只将原厂线的手机端接入运行工具的手机。");
        }
    }

    private boolean grant(UsbDevice device) throws IOException {
        if (manager.hasPermission(device)) {
            return true;
        }
        status.show("请在系统弹窗中允许访问连接线…");
        Grant request = new Grant();
        waiting = request;
        Intent intent = new Intent(GRANT_USB).setPackage(context.getPackageName())
                .putExtra("request", request.token);
        PendingIntent result = PendingIntent.getBroadcast(context, 1, intent,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_ONE_SHOT | PendingIntent.FLAG_CANCEL_CURRENT);
        try {
            manager.requestPermission(device, result);
            long until = SystemClock.elapsedRealtime() + 45_000;
            while (SystemClock.elapsedRealtime() < until) {
                if (manager.hasPermission(device)) {
                    return true;
                }
                if (!manager.getDeviceList().containsKey(device.getDeviceName())) {
                    return false;
                }
                if (request.reply.await(250, TimeUnit.MILLISECONDS)) {
                    if (manager.hasPermission(device)) {
                        return true;
                    }
                    if (!manager.getDeviceList().containsKey(device.getDeviceName())) {
                        return false;
                    }
                    throw new IOException("USB 权限未获允许。");
                }
            }
            throw new IOException("等待 USB 授权超时。");
        } catch (InterruptedException error) {
            throw new InterruptedIOException("等待 USB 授权时操作中断。");
        } finally {
            waiting = null;
            result.cancel();
        }
    }

    @Override public Updater.Link open(boolean runtime) throws IOException {
        long start = SystemClock.elapsedRealtime();
        long until = start + 18_000;
        IOException lastError = null;
        while (SystemClock.elapsedRealtime() < until) {
            UsbDevice device = findCable();
            if (device != null) {
                long beforeGrant = SystemClock.elapsedRealtime();
                boolean allowed = grant(device);
                until = Math.min(start + 65_000, until + SystemClock.elapsedRealtime() - beforeGrant);
                if (allowed) {
                    Updater.Link link = connect(device);
                    if (link != null) {
                        boolean matched = false;
                        try {
                            matched = link.runtime() == runtime;
                            if (matched) {
                                return link;
                            }
                        } catch (IOException error) {
                            lastError = error;
                        } finally {
                            if (!matched) {
                                link.close();
                            }
                        }
                    }
                }
            }
            Updater.pause(200);
        }
        String mode = runtime ? "运行态" : "维护模式";
        throw new IOException("等待线控进入" + mode + "超时。请检查线和供电。", lastError);
    }

    private Updater.Link connect(UsbDevice device) {
        UsbDeviceConnection connection = manager.openDevice(device);
        if (connection == null) {
            return null;
        }
        UsbInterface intf = device.getInterfaceCount() == 0 ? null : device.getInterface(0);
        if (intf != null && !connection.claimInterface(intf, true)) {
            connection.close();
            return null;
        }
        return new Updater.Link(new Updater.Usb() {
            @Override public int transfer(int type, int request, int value, int index,
                                          byte[] data, int offset, int size) {
                return connection.controlTransfer(type, request, value, index, data, offset, size, 1500);
            }

            @Override public void close() {
                if (intf != null) {
                    connection.releaseInterface(intf);
                }
                connection.close();
            }
        });
    }
}
