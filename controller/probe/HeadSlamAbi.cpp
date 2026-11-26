// SPDX-License-Identifier: GPL-3.0-or-later
// Exercise the same packet ownership and native adapter used by the APK on Windows.
#define CV10_SLAM_HOST_TEST
#include "../../ports/Monado_CV10/src/xrt/targets/openxr_android/src/main/cpp/cv10_kit_slam.cpp"

#include <Windows.h>
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>

namespace {

void
check(const char *operation, int result)
{
	if (result != 0) throw std::runtime_error(std::string(operation) + " returned " + std::to_string(result));
}

void
replay(const Module *module, const std::filesystem::path &calibration)
{
	Session session;
	std::ifstream parameters(calibration, std::ios::binary);
	if (!parameters.read(reinterpret_cast<char *>(session.parameters.data()), session.parameters.size()) ||
	    parameters.peek() != std::ifstream::traits_type::eof()) {
		throw std::runtime_error("Expected 2112-byte slam-params.bin");
	}
	int status = 0;
	if (const char *error = session.open(module, status)) {
		throw std::runtime_error(std::string(error) + " (" + std::to_string(status) + ")");
	}
	for (uint64_t ns : {1000000000ULL, 1005000000ULL, 1010000000ULL}) {
		check("Accelerometer", session.push_imu(0, ns, 0, 0, 9.8f));
		check("Gyroscope", session.push_imu(1, ns, 0, 0, 0));
	}
	for (uint32_t i = 0; i < 2; ++i) {
		auto *stereo = new Stereo(1010000000ULL + 66666666ULL * i, i + 1, 4000);
		std::memset(stereo->pixels, 0, sizeof(stereo->pixels));
		check("Stereo", session.push_stereo(stereo));
	}
	Sleep(100);
	alignas(8) uint8_t pose[0x38] = {};
	status = session.pose(pose);
	if (status != -1 || std::any_of(std::begin(pose), std::end(pose), [](uint8_t value) { return value != 0; })) {
		throw std::runtime_error("Expected no pose from blank stereo");
	}
	check("Stop/deinit", session.close());
	if (PacketOwner::live.load() != 0) throw std::runtime_error("SLAM retained input after close");
	std::puts("SLAM accepted 6 IMU records and 2 stereo pairs, returned no pose for blank images, and closed.");
}

void
replay_hands(const Module *module, const std::filesystem::path &calibration)
{
	HandSession session;
	std::ifstream parameters(calibration, std::ios::binary);
	if (!parameters.read(reinterpret_cast<char *>(session.parameters.data()), session.parameters.size()) ||
	    parameters.peek() != std::ifstream::traits_type::eof()) {
		throw std::runtime_error("Expected a 7224-byte hand tracking configuration");
	}
	int status = 0;
	if (const char *error = session.open(module, status)) {
		throw std::runtime_error(std::string(error) + " (" + std::to_string(status) + ")");
	}
	const std::array<float, 6> axes{0, 0, 9.8f, 0, 0, 0};
	for (uint64_t ns = 1000000000ULL; ns < 1176000000ULL; ns += 4000000ULL) {
		check("Left IMU", session.push_imu(false, ns, axes));
		check("Right IMU", session.push_imu(true, ns, axes));
	}

	struct HeadPoseFixture {
		double seconds;
		uint32_t state0 = 1;
		uint32_t state1 = 1;
		float position[3] = {0.125f, 1.25f, -0.25f};
		float quaternion[4] = {1, 0, 0, 0};
		uint32_t padding = 0;
		uint8_t image_valid = 1;
	};
	uint64_t ns = 1086666666ULL;
	for (uint32_t i = 0; i < 2; ++i, ns += 66666666ULL) {
		alignas(8) uint8_t head[0x38] = {};
		HeadPoseFixture fixture{ns / 1e9};
		std::memcpy(head, &fixture, offsetof(HeadPoseFixture, image_valid) + 1);
		auto *stereo = new HandStereo(ns, i + 1, 4000, head, nullptr);
		std::memset(stereo->pixels, 0, sizeof(stereo->pixels));
		check("Hand stereo", session.push_stereo(stereo));
	}
	std::vector<HandPose> poses;
	for (int attempt = 0; attempt < 40; ++attempt) {
		Sleep(25);
		status = session.poses(poses, ns - 66666666ULL);
		if (status == 0) break;
		if (status != -1) throw std::runtime_error("Unexpected hand pose query result");
	}
	if (status != 0 || poses.size() != 2 || poses[0].side != '0' || poses[1].side != '1' ||
	    poses[0].state != 255 || poses[1].state != 255) {
		throw std::runtime_error("Expected two invalid hand poses from blank stereo");
	}
	check("Stop/deinit", session.close());
	if (int outstanding = PacketOwner::live.load()) {
		throw std::runtime_error("Hand module retained " + std::to_string(outstanding) + " input allocations after close");
	}
	std::printf("Adapter reclaimed %u stock references after shutdown.\n", session.unreleased_inputs);
	std::puts("Hand tracking accepted 88 IMU records and 2 stereo pairs, returned two invalid poses, and closed.");
}

} // namespace

int
wmain(int argc, wchar_t **argv)
{
	bool hands = argc == 4 && std::wcscmp(argv[3], L"--controllers") == 0;
	if (argc != 3 && !hands) {
		std::fprintf(stderr, "Usage: HeadSlamAbi <original tracking DLL> <configuration.bin> [--controllers]\n");
		return 2;
	}
	auto path = std::filesystem::absolute(argv[1]);
	HMODULE library = LoadLibraryExW(path.c_str(), nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR |
	                                                        LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
	if (!library) {
		std::fprintf(stderr, "LoadLibraryExW failed: %lu\n", GetLastError());
		return 1;
	}
	int result = 0;
	try {
		const char *export_name = hands ? "GetVR6DofInterface" : "GetSlamInterface";
		auto get_interface = reinterpret_cast<const Module *(*)()>(GetProcAddress(library, export_name));
		const Module *module = get_interface ? get_interface() : nullptr;
		if (hands) replay_hands(module, argv[2]);
		else replay(module, argv[2]);
	} catch (const std::exception &error) {
		std::fprintf(stderr, "%s\n", error.what());
		result = 1;
	}
	FreeLibrary(library);
	return result;
}
