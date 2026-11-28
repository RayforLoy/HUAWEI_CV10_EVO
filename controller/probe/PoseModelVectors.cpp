// SPDX-License-Identifier: GPL-3.0-or-later
#include <cassert>
#include <cmath>
#include <cstdio>

extern "C" {
#include "cv10_pose_models.h"
#include "math/m_api.h"
}

static void
check_near(float actual, float expected)
{
	assert(std::abs(actual - expected) < 0.0001f);
}

static xrt_space_relation
relation(xrt_quat orientation = {0, 0, 0, 1})
{
	xrt_space_relation result{};
	result.pose.orientation = orientation;
	result.relation_flags = static_cast<xrt_space_relation_flags>(XRT_SPACE_RELATION_ORIENTATION_VALID_BIT |
	                                                              XRT_SPACE_RELATION_ORIENTATION_TRACKED_BIT);
	return result;
}

int
main()
{
	const float pi = 3.14159265358979323846f;
	auto head = relation();
	cv10_head_model_apply(1.72f, &head);
	check_near(head.pose.position.y, 1.72f);
	assert((head.relation_flags & XRT_SPACE_RELATION_POSITION_VALID_BIT) != 0);
	assert((head.relation_flags & XRT_SPACE_RELATION_POSITION_TRACKED_BIT) == 0);
	xrt_vec3 right{1, 0, 0};
	xrt_quat pitch;
	math_quat_from_angle_vector(0.2f, &right, &pitch);
	auto tilted = relation(pitch);
	const float rise = 0.075f * (std::cos(0.2f) - 1.f) + 0.0805f * std::sin(0.2f);
	cv10_head_model_apply(1.72f - rise, &tilted);
	check_near(tilted.pose.position.y, 1.72f);
	assert(std::abs(tilted.pose.position.z) > 0.01f);

	cv10_arm_model arm{};
	auto grip = relation();
	auto aim = relation();
	cv10_arm_model_apply(&arm, 1'000'000'000, &head, false, &grip);
	cv10_arm_model_apply(&arm, 1'000'000'000, &head, true, &aim);
	check_near(grip.pose.position.x, 0.22f);
	check_near(grip.pose.position.y, 0.97f);
	check_near(grip.pose.position.z, -0.39f);
	check_near(aim.pose.position.y - grip.pose.position.y, 0.020f);
	check_near(aim.pose.position.z - grip.pose.position.z, -0.069f);
	assert((grip.relation_flags & XRT_SPACE_RELATION_POSITION_VALID_BIT) != 0);
	assert((grip.relation_flags & XRT_SPACE_RELATION_ORIENTATION_TRACKED_BIT) != 0);
	assert((grip.relation_flags & XRT_SPACE_RELATION_POSITION_TRACKED_BIT) == 0);

	xrt_vec3 up{0, 1, 0};
	xrt_quat yaw;
	math_quat_from_angle_vector(pi / 2.f, &up, &yaw);
	auto turned_head = relation(yaw);
	cv10_head_model_apply(1.72f, &turned_head);
	check_near(turned_head.pose.position.x, -0.0805f);
	check_near(turned_head.pose.position.z, 0.0805f);
	auto turned_grip = relation(yaw);
	arm = {};
	cv10_arm_model_apply(&arm, 1'000'000'000, &turned_head, false, &turned_grip);
	check_near(turned_grip.pose.position.x - turned_head.pose.position.x, grip.pose.position.z);
	check_near(turned_grip.pose.position.z - turned_head.pose.position.z, -grip.pose.position.x);

	xrt_quat raised;
	math_quat_from_angle_vector(pi / 3.f, &right, &raised);
	auto raised_grip = relation(raised);
	arm = {};
	cv10_arm_model_apply(&arm, 1'010'000'000, &head, false, &raised_grip);
	check_near(raised_grip.pose.position.x, 0.09f);
	assert(raised_grip.pose.position.y > grip.pose.position.y + 0.2f);
	xrt_quat behind;
	math_quat_from_angle_vector(pi, &up, &behind);
	auto reversed_grip = relation(behind);
	cv10_arm_model_apply(&arm, 1'020'000'000, &head, false, &reversed_grip);
	assert(std::isfinite(reversed_grip.pose.position.z));

	auto missing = relation();
	missing.relation_flags = XRT_SPACE_RELATION_BITMASK_NONE;
	cv10_arm_model_apply(&arm, 1'030'000'000, &missing, false, &grip);
	assert((grip.relation_flags & XRT_SPACE_RELATION_POSITION_VALID_BIT) == 0);
	assert((grip.relation_flags & XRT_SPACE_RELATION_ORIENTATION_TRACKED_BIT) != 0);
	std::puts("CV10 neck, eye height, grip and aim pose vectors passed");
}
