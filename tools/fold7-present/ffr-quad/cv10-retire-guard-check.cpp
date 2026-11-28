
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <errno.h>
#include <linux/sync_file.h>
#include <poll.h>
#include <stdio.h>
#include <stdint.h>
#include <sys/ioctl.h>
#include <sys/eventfd.h>
#include <time.h>
#include <unistd.h>
#include <cassert>
#include <cstring>
#include <memory>

namespace real {

constexpr uint64_t kNanosecondsPerSecond = 1000000000;
constexpr uint64_t kRetireGuardNs = 750000;
constexpr int kRetirePollMs = 17;
constexpr uint64_t kRetireBudgetNs = 18000000;

uint64_t MonotonicNs() {
  timespec now = {};
  if (clock_gettime(CLOCK_MONOTONIC, &now)) {
    return 0;
  }
  return static_cast<uint64_t>(now.tv_sec) * kNanosecondsPerSecond + now.tv_nsec;
}

const char *WaitForRetireGuard(int fd) {
  if (fd < 0) {
    return "CV10 retire guard invalid fence";
  }

  const uint64_t start = MonotonicNs();
  if (!start) {
    return "CV10 retire guard clock error";
  }
  const uint64_t deadline = start + kRetireBudgetNs;
  pollfd fence_poll = {fd, POLLIN, 0};
  const int ready = poll(&fence_poll, 1, kRetirePollMs);
  if (!ready) {
    return "CV10 retire guard timeout";
  }
  if (ready < 0 || !(fence_poll.revents & POLLIN) || (fence_poll.revents & POLLERR)) {
    return "CV10 retire guard fence error";
  }

  // This is a connector fence straight from the DRM request, with one timeline.
  sync_fence_info signal = {};
  sync_file_info fence = {};
  fence.num_fences = 1;
  fence.sync_fence_info = reinterpret_cast<uintptr_t>(&signal);
  if (ioctl(fd, SYNC_IOC_FILE_INFO, &fence) || fence.num_fences != 1 ||
      fence.status != 1 || signal.status != 1) {
    return "CV10 retire guard fence info error";
  }

  const uint64_t now = MonotonicNs();
  if (!now || !signal.timestamp_ns || signal.timestamp_ns > now) {
    return "CV10 retire guard clock error";
  }
  const uint64_t target = signal.timestamp_ns + kRetireGuardNs;
  if (now > deadline || target > deadline) {
    return "CV10 retire guard timeout";
  }
  if (now < target) {
    timespec wake = {static_cast<time_t>(target / kNanosecondsPerSecond),
                     static_cast<long>(target % kNanosecondsPerSecond)};
    int result;
    do {
      result = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &wake, nullptr);
    } while (result == EINTR && MonotonicNs() < deadline);
    if (result) {
      return "CV10 retire guard sleep error";
    }
    if (MonotonicNs() > deadline) {
      return "CV10 retire guard timeout";
    }
  }
  return "CV10 retire guard ready";
}


}

namespace fake {

uint64_t now_ns;
uint64_t signaled_ns;
uint64_t polled_ns;
uint64_t slept_until;
int poll_result;
short poll_events;
int fence_count;
int fence_status;
int signal_status;
int sleep_interrupts;

static int mock_clock(clockid_t which, timespec *time) {
  assert(which == CLOCK_MONOTONIC);
  *time = {static_cast<time_t>(now_ns / 1000000000),
           static_cast<long>(now_ns % 1000000000)};
  return 0;
}

static int mock_poll(pollfd *input, nfds_t count, int timeout) {
  assert(count == 1 && timeout == 17 && input[0].events == POLLIN);
  input[0].revents = poll_events;
  now_ns += polled_ns;
  return poll_result;
}

static int mock_ioctl(int fd, unsigned long request, sync_file_info *output) {
  assert(fd == 20 && request == SYNC_IOC_FILE_INFO && output->num_fences == 1);
  auto *signal = reinterpret_cast<sync_fence_info *>(output->sync_fence_info);
  *signal = {};
  signal->status = signal_status;
  signal->timestamp_ns = signaled_ns;
  output->status = fence_status;
  output->num_fences = fence_count;
  return 0;
}

static int mock_sleep(clockid_t which, int flags, const timespec *until, timespec *) {
  assert(which == CLOCK_MONOTONIC && flags == TIMER_ABSTIME);
  const uint64_t target = uint64_t(until->tv_sec) * 1000000000 + until->tv_nsec;
  assert(target > now_ns);
  if (sleep_interrupts > 0) {
    --sleep_interrupts;
    now_ns += 3000;
    return EINTR;
  }
  now_ns = slept_until = target;
  return 0;
}

#define clock_gettime mock_clock
#define poll mock_poll
#define ioctl mock_ioctl
#define clock_nanosleep mock_sleep

constexpr uint64_t kNanosecondsPerSecond = 1000000000;
constexpr uint64_t kRetireGuardNs = 750000;
constexpr int kRetirePollMs = 17;
constexpr uint64_t kRetireBudgetNs = 18000000;

uint64_t MonotonicNs() {
  timespec now = {};
  if (clock_gettime(CLOCK_MONOTONIC, &now)) {
    return 0;
  }
  return static_cast<uint64_t>(now.tv_sec) * kNanosecondsPerSecond + now.tv_nsec;
}

const char *WaitForRetireGuard(int fd) {
  if (fd < 0) {
    return "CV10 retire guard invalid fence";
  }

  const uint64_t start = MonotonicNs();
  if (!start) {
    return "CV10 retire guard clock error";
  }
  const uint64_t deadline = start + kRetireBudgetNs;
  pollfd fence_poll = {fd, POLLIN, 0};
  const int ready = poll(&fence_poll, 1, kRetirePollMs);
  if (!ready) {
    return "CV10 retire guard timeout";
  }
  if (ready < 0 || !(fence_poll.revents & POLLIN) || (fence_poll.revents & POLLERR)) {
    return "CV10 retire guard fence error";
  }

  // This is a connector fence straight from the DRM request, with one timeline.
  sync_fence_info signal = {};
  sync_file_info fence = {};
  fence.num_fences = 1;
  fence.sync_fence_info = reinterpret_cast<uintptr_t>(&signal);
  if (ioctl(fd, SYNC_IOC_FILE_INFO, &fence) || fence.num_fences != 1 ||
      fence.status != 1 || signal.status != 1) {
    return "CV10 retire guard fence info error";
  }

  const uint64_t now = MonotonicNs();
  if (!now || !signal.timestamp_ns || signal.timestamp_ns > now) {
    return "CV10 retire guard clock error";
  }
  const uint64_t target = signal.timestamp_ns + kRetireGuardNs;
  if (now > deadline || target > deadline) {
    return "CV10 retire guard timeout";
  }
  if (now < target) {
    timespec wake = {static_cast<time_t>(target / kNanosecondsPerSecond),
                     static_cast<long>(target % kNanosecondsPerSecond)};
    int result;
    do {
      result = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &wake, nullptr);
    } while (result == EINTR && MonotonicNs() < deadline);
    if (result) {
      return "CV10 retire guard sleep error";
    }
    if (MonotonicNs() > deadline) {
      return "CV10 retire guard timeout";
    }
  }
  return "CV10 retire guard ready";
}


#undef clock_nanosleep
#undef ioctl
#undef poll
#undef clock_gettime

static void Reset() {
  now_ns = 4999900000;
  signaled_ns = 5000000000;
  polled_ns = 120000;
  slept_until = 0;
  poll_result = 1;
  poll_events = POLLIN;
  fence_count = fence_status = signal_status = 1;
  sleep_interrupts = 0;
}

static void Outcome(int fd, const char *expected) {
  const char *observed = WaitForRetireGuard(fd);
  assert(strcmp(observed, expected) == 0);
}

}  // namespace fake

struct RetireHistory {
  bool cv10_retire_guard_enabled_ = true;
  std::shared_ptr<int> cv10_previous_retire_;
  std::shared_ptr<int> cv10_next_retire_;

  void Finish(bool guard_frame, int ret, uint32_t retire_offset,
              const std::shared_ptr<int> &retire_fence) {

  if (cv10_retire_guard_enabled_) {
    if (guard_frame && !ret) {
      // Offset one signals on the next commit. Use the fence from one commit earlier.
      cv10_previous_retire_ = retire_offset == 0 ? retire_fence : cv10_next_retire_;
      cv10_next_retire_ = retire_offset == 1 ? retire_fence : nullptr;
    } else {
      cv10_previous_retire_.reset();
      cv10_next_retire_.reset();
    }
  }

  }

  void Check(int previous, int next) {
    assert((cv10_previous_retire_ ? *cv10_previous_retire_ : -1) == previous);
    assert((cv10_next_retire_ ? *cv10_next_retire_ : -1) == next);
  }
};

static void CheckNativeFence() {
  EGLDisplay display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
  assert(display != EGL_NO_DISPLAY && eglInitialize(display, nullptr, nullptr));
  const EGLint config_attrs[] = {
      EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT, EGL_NONE};
  EGLConfig config;
  EGLint count;
  assert(eglChooseConfig(display, config_attrs, &config, 1, &count) && count == 1);
  const EGLint surface_attrs[] = {EGL_WIDTH, 16, EGL_HEIGHT, 16, EGL_NONE};
  EGLSurface surface = eglCreatePbufferSurface(display, config, surface_attrs);
  const EGLint context_attrs[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
  EGLContext context = eglCreateContext(display, config, EGL_NO_CONTEXT, context_attrs);
  assert(eglMakeCurrent(display, surface, surface, context));

  auto create = reinterpret_cast<PFNEGLCREATESYNCKHRPROC>(eglGetProcAddress("eglCreateSyncKHR"));
  auto destroy = reinterpret_cast<PFNEGLDESTROYSYNCKHRPROC>(
      eglGetProcAddress("eglDestroySyncKHR"));
  auto dup = reinterpret_cast<PFNEGLDUPNATIVEFENCEFDANDROIDPROC>(
      eglGetProcAddress("eglDupNativeFenceFDANDROID"));
  assert(create && destroy && dup);

  glClearColor(0.3f, 0.5f, 0.7f, 1.0f);
  glClear(GL_COLOR_BUFFER_BIT);
  EGLSyncKHR sync = create(display, EGL_SYNC_NATIVE_FENCE_ANDROID, nullptr);
  assert(sync != EGL_NO_SYNC_KHR);
  glFlush();
  int sync_fd = dup(display, sync);
  assert(sync_fd >= 0);
  const char *result = real::WaitForRetireGuard(sync_fd);
  printf("EGL native fence: %s\n", result);
  assert(strcmp(result, "CV10 retire guard ready") == 0);

  close(sync_fd);
  eglDestroyContext(display, context);
  eglDestroySurface(display, surface);
  destroy(display, sync);
  eglTerminate(display);
}

int main() {
  using namespace fake;
  Reset();
  sleep_interrupts = 1;
  Outcome(20, "CV10 retire guard ready");
  assert(slept_until == signaled_ns + kRetireGuardNs && sleep_interrupts == 0);
  Reset();
  signaled_ns -= 5000000;
  Outcome(20, "CV10 retire guard ready");
  assert(slept_until == 0);
  Reset();
  Outcome(-1, "CV10 retire guard invalid fence");
  Reset();
  poll_result = 0;
  Outcome(20, "CV10 retire guard timeout");
  Reset();
  polled_ns = 17700000;
  signaled_ns = now_ns + polled_ns;
  Outcome(20, "CV10 retire guard timeout");
  assert(slept_until == 0);
  Reset();
  polled_ns = 20000000;
  Outcome(20, "CV10 retire guard timeout");
  Reset();
  signal_status = -1;
  Outcome(20, "CV10 retire guard fence info error");
  Reset();
  fence_count = 2;
  Outcome(20, "CV10 retire guard fence info error");
  Reset();
  poll_events = POLLERR;
  Outcome(20, "CV10 retire guard fence error");
  Reset();
  signaled_ns = now_ns + 50000000;
  Outcome(20, "CV10 retire guard clock error");

  RetireHistory history;
  history.Finish(true, 0, 0, std::make_shared<int>(1));
  history.Check(1, -1);
  history.Finish(true, 0, 1, std::make_shared<int>(2));
  history.Check(-1, 2);
  history.Finish(true, 0, 1, std::make_shared<int>(3));
  history.Check(2, 3);
  history.Finish(true, 0, 0, std::make_shared<int>(4));
  history.Check(4, -1);
  history.Finish(true, -1, 0, std::make_shared<int>(5));
  history.Check(-1, -1);
  history.Finish(true, 0, 1, std::make_shared<int>(6));
  history.Finish(false, 0, 0, std::make_shared<int>(7));
  history.Check(-1, -1);

  int fd = eventfd(0, EFD_CLOEXEC);
  assert(fd >= 0);
  const uint64_t begin = real::MonotonicNs();
  assert(strcmp(real::WaitForRetireGuard(fd), "CV10 retire guard timeout") == 0);
  const uint64_t elapsed = real::MonotonicNs() - begin;
  assert(elapsed >= 15000000 && elapsed < 250000000);
  assert(eventfd_write(fd, 1) == 0);
  assert(strcmp(real::WaitForRetireGuard(fd), "CV10 retire guard fence info error") == 0);
  close(fd);

  printf("10 wait cases, 6 retire history checks, Android timeout %.3f ms\n",
         elapsed / 1000000.0);
  CheckNativeFence();
}
