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

} // namespace

int
wmain(int argc, wchar_t **argv)
{
	if (argc != 3) {
		std::fprintf(stderr, "Usage: HeadSlamAbi <original arvr_slam.dll> <slam-params.bin>\n");
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
		auto get_interface = reinterpret_cast<const Module *(*)()>(GetProcAddress(library, "GetSlamInterface"));
		replay(get_interface ? get_interface() : nullptr, argv[2]);
	} catch (const std::exception &error) {
		std::fprintf(stderr, "%s\n", error.what());
		result = 1;
	}
	FreeLibrary(library);
	return result;
}
