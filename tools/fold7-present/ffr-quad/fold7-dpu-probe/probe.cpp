#include <android/data_space.h>
#include <android/hardware_buffer.h>
#include <android/log.h>
#include <android/native_window_jni.h>
#include <android/surface_control.h>
#include <jni.h>
#include <linux/sync_file.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include <array>
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdint>
#include <cstring>
#include <thread>

namespace {
using Clock = std::chrono::steady_clock;
constexpr char kTag[] = "Cv10DpuProbe";
constexpr int kCount = 810;
constexpr int kPatternCount = 4;
constexpr int64_t kPeriodNs = 11111111;
struct Sample {
    int index = 0;
    int64_t submitted = 0;
    std::atomic<int> fence{-2}; // -2: callback not yet published.
};

std::array<Sample, kCount> samples;
std::atomic_bool started{false};

int64_t signaledAt(int fd) {
    sync_file_info info{};
    if (ioctl(fd, SYNC_IOC_FILE_INFO, &info) < 0 || !info.num_fences || info.num_fences > 32)
        return 0;
    std::array<sync_fence_info, 32> fences{};
    info.sync_fence_info = reinterpret_cast<uintptr_t>(fences.data());
    if (ioctl(fd, SYNC_IOC_FILE_INFO, &info) < 0 || info.status != 1) return 0;
    uint64_t last = 0;
    for (unsigned int i = 0; i < info.num_fences; ++i)
        if (fences[i].timestamp_ns > last) last = fences[i].timestamp_ns;
    return last;
}

void completed(void* context, ASurfaceTransactionStats* stats) {
    auto& sample = *static_cast<Sample*>(context);
    int fd = ASurfaceTransactionStats_getPresentFenceFd(stats);
    int pending = -2;
    if (!sample.fence.compare_exchange_strong(pending, fd) && fd >= 0) close(fd);
}

bool createImage(AHardwareBuffer_Desc desc, unsigned phase, AHardwareBuffer** result) {
    if (AHardwareBuffer_allocate(&desc, result) != 0 || !*result) return false;
    AHardwareBuffer_describe(*result, &desc);
    if (desc.format == AHARDWAREBUFFER_FORMAT_Y8Cb8Cr8_420) {
        AHardwareBuffer_Planes planes{};
        if (AHardwareBuffer_lockPlanes(*result, AHARDWAREBUFFER_USAGE_CPU_WRITE_OFTEN,
                                       -1, nullptr, &planes) != 0) return false;
        if (planes.planeCount != 3) {
            __android_log_print(ANDROID_LOG_ERROR, kTag, "YUV planeCount=%u", planes.planeCount);
            AHardwareBuffer_unlock(*result, nullptr);
            return false;
        }
        for (unsigned i = 0; i < planes.planeCount; ++i) {
            const auto& plane = planes.planes[i];
            const unsigned width = i == 0 ? desc.width : desc.width / 2;
            const unsigned height = i == 0 ? desc.height : desc.height / 2;
            if (!plane.data || !plane.pixelStride ||
                    plane.rowStride < 1 + (width - 1) * plane.pixelStride) {
                __android_log_print(ANDROID_LOG_ERROR, kTag,
                    "YUV plane=%u mapped=%d rowStride=%u pixelStride=%u", i, plane.data != nullptr,
                    plane.rowStride, plane.pixelStride);
                AHardwareBuffer_unlock(*result, nullptr);
                return false;
            }
            for (unsigned y = 0; y < height; ++y) {
                auto* row = static_cast<uint8_t*>(plane.data) + y * plane.rowStride;
                if (i == 0 && plane.pixelStride == 1) {
                    std::memset(row, 24, width);
                    if (y > 690 && y < 910) {
                        const unsigned markerStart = 720 + 12 * phase;
                        std::memset(row + markerStart, 210, 34);
                        std::memset(row + width / 2 + markerStart, 210, 34);
                    }
                } else {
                    for (unsigned x = 0; x < width; ++x) row[x * plane.pixelStride] = 128;
                }
            }
        }
        return AHardwareBuffer_unlock(*result, nullptr) == 0;
    }
    void* address = nullptr;
    if (AHardwareBuffer_lock(*result, AHARDWAREBUFFER_USAGE_CPU_WRITE_RARELY,
                            -1, nullptr, &address) != 0 || !address) return false;
    auto* pixels = static_cast<uint32_t*>(address);
    for (unsigned y = 0; y < desc.height; ++y) {
        for (unsigned x = 0; x < desc.width; ++x) {
            unsigned eyeX = x % (desc.width / 2);
            bool line = eyeX > 720 + 12 * phase && eyeX < 754 + 12 * phase && y > 690 && y < 910;
            pixels[y * desc.stride + x] = line ? 0xff40e0f0 : 0xff403020;
        }
    }
    return AHardwareBuffer_unlock(*result, nullptr) == 0;
}

void probe(ANativeWindow* window, int width, int height, int format) {
    ASurfaceControl* surface = ASurfaceControl_createFromWindow(window, "CV10 DPU probe");
    ANativeWindow_release(window);
    if (!surface) {
        __android_log_print(ANDROID_LOG_ERROR, kTag, "createFromWindow failed");
        return;
    }
    std::array<AHardwareBuffer*, kPatternCount> buffers{};
    AHardwareBuffer_Desc desc{};
    desc.width = width;
    desc.height = height;
    desc.layers = 1;
    desc.format = format;
    desc.usage = AHARDWAREBUFFER_USAGE_CPU_WRITE_RARELY | AHARDWAREBUFFER_USAGE_GPU_SAMPLED_IMAGE |
                 AHARDWAREBUFFER_USAGE_COMPOSER_OVERLAY;
    if (format == AHARDWAREBUFFER_FORMAT_Y8Cb8Cr8_420) {
        desc.usage &= ~static_cast<uint64_t>(AHARDWAREBUFFER_USAGE_CPU_WRITE_MASK);
        desc.usage |= AHARDWAREBUFFER_USAGE_CPU_WRITE_OFTEN;
    }
    for (unsigned i = 0; i < buffers.size(); ++i) {
        if (createImage(desc, i, &buffers[i])) continue;
        __android_log_print(ANDROID_LOG_ERROR, kTag, "could not allocate or fill format %u", desc.format);
        for (auto* buffer : buffers) if (buffer) AHardwareBuffer_release(buffer);
        ASurfaceControl_release(surface);
        return;
    }
    const auto start = Clock::now() + std::chrono::milliseconds(100);
    __android_log_print(ANDROID_LOG_INFO, kTag, "start format=%u frames=%d", desc.format, kCount);
    for (int i = 0; i < kCount; ++i) {
        std::this_thread::sleep_until(start + std::chrono::nanoseconds(i * kPeriodNs));
        Sample& sample = samples[i];
        sample.index = i;
        sample.submitted = std::chrono::duration_cast<std::chrono::nanoseconds>(
            Clock::now().time_since_epoch()).count();
        ASurfaceTransaction* tx = ASurfaceTransaction_create();
        if (i == 0) {
            ASurfaceTransaction_setZOrder(tx, surface, 1);
            ASurfaceTransaction_setVisibility(tx, surface, ASURFACE_TRANSACTION_VISIBILITY_SHOW);
            ASurfaceTransaction_setBufferTransparency(tx, surface, ASURFACE_TRANSACTION_TRANSPARENCY_OPAQUE);
            ASurfaceTransaction_setBufferDataSpace(tx, surface,
                    format == AHARDWAREBUFFER_FORMAT_Y8Cb8Cr8_420 ? ADATASPACE_BT709 : ADATASPACE_SRGB);
            ASurfaceTransaction_setFrameRate(tx, surface, 90.f, ANATIVEWINDOW_FRAME_RATE_COMPATIBILITY_DEFAULT);
        }
        ASurfaceTransaction_setBuffer(tx, surface, buffers[i % buffers.size()], -1);
        ASurfaceTransaction_setOnComplete(tx, &sample, completed);
        ASurfaceTransaction_apply(tx);
        ASurfaceTransaction_delete(tx);
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(750));
    int valid = 0;
    int missing = 0;
    for (auto& sample : samples) {
        int fd = sample.fence.exchange(-3);
        int64_t actual = fd < 0 ? 0 : signaledAt(fd);
        if (fd >= 0) close(fd);
        if (fd == -2) ++missing;
        if (actual > 0) {
            ++valid;
            __android_log_print(ANDROID_LOG_INFO, kTag, "id=%d queue=%" PRId64 " present=%" PRId64,
                                sample.index, sample.submitted, actual);
        }
    }
    __android_log_print(ANDROID_LOG_INFO, kTag, "finished valid=%d missingCallback=%d", valid, missing);
    ASurfaceControl_release(surface);
    for (auto* buffer : buffers) AHardwareBuffer_release(buffer);
}
}

extern "C" JNIEXPORT void JNICALL Java_org_cv10_dpuprobe_Probe_runProbe(
        JNIEnv* env, jclass, jobject surface, jint width, jint height, jint format) {
    if (started.exchange(true)) return;
    ANativeWindow* window = ANativeWindow_fromSurface(env, surface);
    if (window) std::thread(probe, window, width, height, format).detach();
}
