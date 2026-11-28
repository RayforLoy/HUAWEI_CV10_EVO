package org.cv10.dpuprobe;

import android.app.Activity;
import android.app.Presentation;
import android.content.res.AssetFileDescriptor;
import android.media.MediaPlayer;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.hardware.display.DisplayManager;
import android.os.Bundle;
import android.util.Log;
import android.view.Display;
import android.view.Surface;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.Window;
import android.view.WindowManager;

import java.io.IOException;

public final class Probe extends Activity {
    static { System.loadLibrary("cv10dpu"); }

    private static native void runProbe(Surface surface, int width, int height, int format);
    private Presentation presentation;
    private MediaPlayer video;
    private boolean started;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().getDecorView().setBackgroundColor(Color.BLACK);
        DisplayManager manager = (DisplayManager)getSystemService(Context.DISPLAY_SERVICE);
        for (Display display : manager.getDisplays()) {
            if (!display.getName().equals("HUAWEIAV03")) continue;
            Display.Mode mode = display.getMode();
            if (mode.getPhysicalWidth() != 3200 || mode.getPhysicalHeight() != 1600 ||
                    Math.abs(mode.getRefreshRate() - 90f) > 0.1f) {
                Log.e("Cv10DpuProbe", "Unexpected external mode: " + mode);
                return;
            }
            int format = getIntent().getIntExtra("format", 1);
            presentation = new Presentation(this, display);
            Window window = presentation.getWindow();
            window.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN |
                            WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN);
            window.setBackgroundDrawableResource(android.R.color.black);
            WindowManager.LayoutParams attrs = window.getAttributes();
            attrs.width = WindowManager.LayoutParams.MATCH_PARENT;
            attrs.height = WindowManager.LayoutParams.MATCH_PARENT;
            attrs.setFitInsetsTypes(0);
            window.setAttributes(attrs);
            SurfaceView view = new SurfaceView(presentation.getContext());
            SurfaceHolder holder = view.getHolder();
            holder.setFixedSize(3200, 1600);
            holder.addCallback(new SurfaceHolder.Callback() {
                public void surfaceCreated(SurfaceHolder unused) {}
                public void surfaceDestroyed(SurfaceHolder unused) {}
                public void surfaceChanged(SurfaceHolder h, int fmt, int width, int height) {
                    if (started || width != 3200 || height != 1600) return;
                    started = true;
                    if (format == 0) {
                        startVideo(h);
                        return;
                    }
                    Canvas canvas = h.lockCanvas();
                    if (canvas != null) {
                        canvas.drawColor(Color.BLACK);
                        h.unlockCanvasAndPost(canvas);
                    }
                    runProbe(h.getSurface(), width, height, format);
                }
            });
            presentation.setContentView(view);
            presentation.show();
            return;
        }
        Log.e("Cv10DpuProbe", "No CV10 display");
    }

    private void startVideo(SurfaceHolder holder) {
        video = new MediaPlayer();
        try (AssetFileDescriptor asset = getAssets().openFd("clip.mp4")) {
            video.setDataSource(asset.getFileDescriptor(), asset.getStartOffset(), asset.getLength());
            video.setDisplay(holder);
            video.setOnPreparedListener(player -> player.start());
            video.setOnInfoListener((player, what, extra) -> {
                if (what == MediaPlayer.MEDIA_INFO_VIDEO_RENDERING_START)
                    Log.i("Cv10DpuProbe", "start format=video width=" + player.getVideoWidth()
                            + " height=" + player.getVideoHeight());
                return false;
            });
            video.setOnCompletionListener(player -> Log.i("Cv10DpuProbe", "finished video"));
            video.setOnErrorListener((player, what, extra) -> {
                Log.e("Cv10DpuProbe", "video error " + what + " " + extra);
                return true;
            });
            video.prepareAsync();
        } catch (IOException e) {
            Log.e("Cv10DpuProbe", "Clip unavailable", e);
        }
    }

    @Override protected void onDestroy() {
        if (video != null) video.release();
        if (presentation != null) presentation.dismiss();
        super.onDestroy();
    }
}
