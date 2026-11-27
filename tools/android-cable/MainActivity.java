package org.cv10.cableupdater;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.Comparator;
import java.util.concurrent.atomic.AtomicBoolean;

public final class MainActivity extends Activity {
    private static final int SAVE_BACKUP = 1;
    private static final int TEXT = 0xff172537;
    private static final int SECONDARY = 0xff4a5b70;
    private static final int ACCENT = 0xff1755a5;
    private static final AtomicBoolean UPDATING = new AtomicBoolean();

    private CheckBox headsetAbsent;
    private CheckBox externalPower;
    private Button update;
    private Button save;
    private TextView status;
    private ProgressBar progress;
    private byte[] image;
    private File backupToExport;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        if (state != null) {
            String savedPath = state.getString("backupToExport");
            if (savedPath != null) {
                backupToExport = new File(savedPath);
            }
        }
        showInterface();
        try (InputStream source = getAssets().open("cv10-c9496-input-2a.bin")) {
            byte[] candidate = new byte[Firmware.SIZE];
            int offset = 0;
            while (offset < candidate.length) {
                int received = source.read(candidate, offset, candidate.length - offset);
                if (received < 0) {
                    throw new IOException("内置固件不完整。");
                }
                offset += received;
            }
            if (source.read() != -1 || !Firmware.TWO_AMP.equals(Firmware.inspect(candidate))) {
                throw new IOException("内置镜像校验未通过。");
            }
            image = candidate;
            report("内置镜像校验通过。");
        } catch (IOException | LinkageError error) {
            report("无法载入内置镜像。\n" + error.getMessage());
        }
        updateButtons();
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        if (backupToExport != null) {
            state.putString("backupToExport", backupToExport.getAbsolutePath());
        }
        super.onSaveInstanceState(state);
    }

    private void showInterface() {
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
                | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        ScrollView page = new ScrollView(this);
        page.setBackgroundColor(0xfff3f6fa);
        page.setFillViewport(true);
        page.setOnApplyWindowInsetsListener((view, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            } else {
                view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                        insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            }
            return insets;
        });
        LinearLayout body = column();
        body.setPadding(dp(20), dp(24), dp(20), dp(20));
        page.addView(body);

        add(body, label("CV10 连接线升级", 28, TEXT, true), 0);
        add(body, label("内置 C9.49.6 · 2.00 A 输入限流", 16, ACCENT, true), 6);
        LinearLayout checks = card();
        add(body, checks, 20);
        add(checks, label("连接方式", 18, TEXT, true), 0);
        add(checks, label("把标有“连接手机”的一端接入这台手机，保持线盒电源接通。", 15,
                SECONDARY, false), 8);
        headsetAbsent = checkbox("已拔下 CV10 眼镜");
        externalPower = checkbox("已接入 5 V / 2 A 电源");
        add(checks, headsetAbsent, 6);
        add(checks, externalPower, 0);
        add(checks, label("请查看电源铭牌确认规格。", 13, SECONDARY, false), 3);

        add(body, label("擦写期间断电或拔线可能导致连接线无法启动。工具会在擦写前保存原固件。", 14,
                SECONDARY, false), 16);
        update = new Button(this);
        update.setText("开始升级");
        update.setBackgroundTintList(new ColorStateList(
                new int[][]{new int[]{-android.R.attr.state_enabled}, new int[]{}},
                new int[]{0xff607084, ACCENT}));
        update.setTextColor(Color.WHITE);
        update.setOnClickListener(view -> confirm());
        add(body, update, 10);

        LinearLayout results = card();
        add(body, results, 12);
        status = label("等待检查内置镜像…", 15, TEXT, false);
        status.setTextIsSelectable(true);
        add(results, status, 0);
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setIndeterminate(true);
        progress.setVisibility(View.GONE);
        add(results, progress, 6);
        save = new Button(this);
        save.setText("导出最近备份");
        save.setOnClickListener(view -> chooseBackupDestination());
        add(results, save, 7);
        setContentView(page);
    }

    private CheckBox checkbox(String text) {
        CheckBox check = new CheckBox(this);
        check.setText(text);
        check.setTextColor(TEXT);
        check.setTextSize(16);
        check.setMinHeight(dp(48));
        check.setOnCheckedChangeListener((button, checked) -> updateButtons());
        return check;
    }

    private LinearLayout column() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        return layout;
    }

    private LinearLayout card() {
        LinearLayout layout = column();
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.WHITE);
        background.setCornerRadius(dp(12));
        layout.setBackground(background);
        layout.setPadding(dp(16), dp(16), dp(16), dp(14));
        return layout;
    }

    private TextView label(String text, int size, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(size);
        view.setTextColor(color);
        if (bold) {
            view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        }
        view.setLineSpacing(dp(2), 1);
        return view;
    }

    private void add(LinearLayout parent, View child, int margin) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.topMargin = dp(margin);
        parent.addView(child, params);
    }

    private int dp(int pixels) {
        return Math.round(pixels * getResources().getDisplayMetrics().density);
    }

    private void updateButtons() {
        boolean idle = !UPDATING.get();
        headsetAbsent.setEnabled(idle);
        externalPower.setEnabled(idle);
        update.setEnabled(idle && image != null && headsetAbsent.isChecked() && externalPower.isChecked());
        save.setEnabled(idle && lastBackup() != null);
        progress.setVisibility(idle ? View.GONE : View.VISIBLE);
    }

    private void confirm() {
        if (!update.isEnabled()) {
            return;
        }
        new AlertDialog.Builder(this).setTitle("确认升级连接线")
                .setMessage("将写入 C9.49.6 的 2.00 A 输入版本。确认 CV10 已拔下，线盒充电口仍接着 5 V / 2 A 电源。\n\n"
                        + "写入期间请保持供电，不要拔线或退出工具。USB 重连时可能需要再次授权。")
                .setNegativeButton("取消", null)
                .setPositiveButton("确认写入", (dialog, which) -> start())
                .show();
    }

    private void start() {
        if (!update.isEnabled() || !UPDATING.compareAndSet(false, true)) {
            return;
        }
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        updateButtons();
        new Thread(() -> {
            try (AndroidUsb host = new AndroidUsb(getApplicationContext(), this::report)) {
                host.checkSetup();
                Updater.Result result = Updater.install(host, image, this::makeBackup, this::report);
                if (result.sectors == 0) {
                    report("当前固件已与内置的 2.00 A 镜像一致。线控已恢复运行态。");
                } else {
                    report(result.version + " 已恢复运行态，" + result.sectors + " 个扇区已写入并通过回读。\n"
                            + "原固件备份 " + result.backup.getName());
                }
            } catch (IOException | RuntimeException | LinkageError error) {
                report("升级未完成。\n" + error.getMessage());
            } finally {
                UPDATING.set(false);
                runOnUiThread(() -> {
                    if (!isDestroyed()) {
                        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                        updateButtons();
                    }
                });
            }
        }, "cv10-upgrade").start();
    }

    private void report(String message) {
        runOnUiThread(() -> {
            if (!isDestroyed()) {
                status.setText(message);
            }
        });
    }

    private File backupFolder() {
        return new File(getFilesDir(), "Backups");
    }

    private File makeBackup(byte[] original, String version) throws IOException {
        File folder = backupFolder();
        if (!folder.isDirectory() && !folder.mkdirs()) {
            throw new IOException("无法创建备份目录，已停止升级。");
        }
        File result = new File(folder, "CV10-cable-" + version + "-before-" + System.currentTimeMillis() + ".bin");
        File staging = File.createTempFile("cv10-", ".tmp", folder);
        try {
            try (FileOutputStream output = new FileOutputStream(staging)) {
                output.write(original);
                output.getFD().sync();
            }
            if (result.exists() || !staging.renameTo(result)) {
                throw new IOException("无法保存原固件备份，已停止升级。");
            }
        } finally {
            if (staging.exists()) {
                staging.delete();
            }
        }
        return result;
    }

    private File lastBackup() {
        File[] files = backupFolder().listFiles((directory, name) -> name.endsWith(".bin"));
        return files == null ? null : Arrays.stream(files)
                .max(Comparator.comparingLong(File::lastModified)).orElse(null);
    }

    private void chooseBackupDestination() {
        backupToExport = lastBackup();
        if (backupToExport != null) {
            Intent picker = new Intent(Intent.ACTION_CREATE_DOCUMENT)
                    .addCategory(Intent.CATEGORY_OPENABLE)
                    .setType("application/octet-stream")
                    .putExtra(Intent.EXTRA_TITLE, backupToExport.getName());
            startActivityForResult(picker, SAVE_BACKUP);
        }
    }

    @Override protected void onActivityResult(int code, int result, Intent data) {
        super.onActivityResult(code, result, data);
        if (code != SAVE_BACKUP || result != RESULT_OK || data == null || backupToExport == null) {
            return;
        }
        Uri destination = data.getData();
        if (destination == null) {
            return;
        }
        try (OutputStream stream = getContentResolver().openOutputStream(destination, "w")) {
            if (stream == null) {
                throw new IOException("无法打开目标文件。");
            }
            Files.copy(backupToExport.toPath(), stream);
            report("已导出原固件备份。");
        } catch (IOException error) {
            report("备份导出失败。\n" + error.getMessage());
        }
        backupToExport = null;
    }

    @Override public void onBackPressed() {
        if (UPDATING.get()) {
            new AlertDialog.Builder(this).setMessage("升级正在进行，请保持供电并等待完成。")
                    .setPositiveButton("知道了", null).show();
        } else {
            super.onBackPressed();
        }
    }
}
