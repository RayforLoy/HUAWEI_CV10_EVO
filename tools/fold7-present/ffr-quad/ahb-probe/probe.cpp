// Standalone Fold7 probe: EGL producer -> ImageReader -> Vulkan external image.
#define VK_USE_PLATFORM_ANDROID_KHR
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <android/hardware_buffer.h>
#include <android/native_window.h>
#include <media/NdkImageReader.h>
#include <vulkan/vulkan.h>

#include <array>
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <time.h>
#include <vector>

namespace {
constexpr int frames = 180;
constexpr uint64_t timeout_ns = 2'000'000'000;
constexpr auto ahb_handle = VK_EXTERNAL_MEMORY_HANDLE_TYPE_ANDROID_HARDWARE_BUFFER_BIT_ANDROID;
constexpr auto sync_handle = VK_EXTERNAL_SEMAPHORE_HANDLE_TYPE_SYNC_FD_BIT;
constexpr uint64_t reader_usage = AHARDWAREBUFFER_USAGE_GPU_SAMPLED_IMAGE | AHARDWAREBUFFER_USAGE_GPU_COLOR_OUTPUT;
constexpr VkImageUsageFlags image_usage = VK_IMAGE_USAGE_SAMPLED_BIT;
constexpr VkImageSubresourceRange pixels = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};

void require(bool success, const char *operation, int detail = 0) {
    if (!success) {
        std::fprintf(stderr, "%s failed (%d)\n", operation, detail);
        std::exit(1);
    }
}

void check(VkResult result, const char *operation) {
    require(result == VK_SUCCESS, operation, result);
}

int64_t now_ns() {
    timespec time{};
    require(clock_gettime(CLOCK_MONOTONIC, &time) == 0, "clock_gettime");
    return time.tv_sec * 1'000'000'000LL + time.tv_nsec;
}

uint32_t memory_type(const VkPhysicalDeviceMemoryProperties &memory, uint32_t allowed,
                     VkMemoryPropertyFlags required) {
    for (uint32_t i = 0; i < memory.memoryTypeCount; ++i) {
        if ((allowed & (1u << i)) && (memory.memoryTypes[i].propertyFlags & required) == required) {
            return i;
        }
    }
    require(false, "find supported memory type");
    return 0;
}

struct ImportedImage {
    VkImage image = VK_NULL_HANDLE;
    VkDeviceMemory memory = VK_NULL_HANDLE;
    VkImageView view = VK_NULL_HANDLE;
};
} // namespace

int main(int argc, char **argv) {
    require(argc == 3, "pass the SPIR-V path and eye size (1600, 2240 or 3200)");
    const auto eye = std::strtol(argv[2], nullptr, 10);
    require(eye == 1600 || eye == 2240 || eye == 3200, "supported probe dimensions");
    const int32_t width = static_cast<int32_t>(eye * 2);
    const int32_t height = static_cast<int32_t>(eye);
    std::ifstream shader_file(argv[1], std::ios::binary | std::ios::ate);
    require(shader_file.good(), "open verification shader");
    const auto shader_size = shader_file.tellg();
    require(shader_size > 0 && shader_size % sizeof(uint32_t) == 0, "SPIR-V size");
    std::vector<uint32_t> shader_code(static_cast<size_t>(shader_size) / sizeof(uint32_t));
    shader_file.seekg(0);
    require(static_cast<bool>(shader_file.read(reinterpret_cast<char *>(shader_code.data()), shader_size)),
            "read verification shader");
    AImageReader *reader = nullptr;
    auto media_result = AImageReader_newWithUsage(width, height, AIMAGE_FORMAT_RGBA_8888,
                                                  reader_usage, 4, &reader);
    require(media_result == AMEDIA_OK, "AImageReader_newWithUsage", media_result);
    ANativeWindow *window = nullptr;
    require(AImageReader_getWindow(reader, &window) == AMEDIA_OK, "AImageReader_getWindow");
    const EGLDisplay egl = eglGetDisplay(EGL_DEFAULT_DISPLAY);
    require(egl != EGL_NO_DISPLAY && eglInitialize(egl, nullptr, nullptr), "eglInitialize");
    const EGLint config_attributes[] = {EGL_SURFACE_TYPE, EGL_WINDOW_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT_KHR,
                                       EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 8, EGL_NONE};
    EGLConfig egl_config = nullptr;
    EGLint config_count = 0;
    require(eglChooseConfig(egl, config_attributes, &egl_config, 1, &config_count) && config_count == 1,
            "eglChooseConfig");
    const EGLint context_attributes[] = {EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE};
    const EGLContext context = eglCreateContext(egl, egl_config, EGL_NO_CONTEXT, context_attributes);
    require(context != EGL_NO_CONTEXT, "eglCreateContext");
    const EGLSurface surface = eglCreateWindowSurface(egl, egl_config, window, nullptr);
    require(surface != EGL_NO_SURFACE, "eglCreateWindowSurface");
    require(eglMakeCurrent(egl, surface, surface, context), "eglMakeCurrent");
    const auto set_time = reinterpret_cast<PFNEGLPRESENTATIONTIMEANDROIDPROC>(eglGetProcAddress("eglPresentationTimeANDROID"));
    require(set_time != nullptr, "eglPresentationTimeANDROID");

    VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO};
    app.apiVersion = VK_API_VERSION_1_1;
    VkInstanceCreateInfo instance_info{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
    instance_info.pApplicationInfo = &app;
    VkInstance instance = VK_NULL_HANDLE;
    check(vkCreateInstance(&instance_info, nullptr, &instance), "vkCreateInstance");
    uint32_t physical_count = 0;
    check(vkEnumeratePhysicalDevices(instance, &physical_count, nullptr), "enumerate devices");
    require(physical_count > 0, "available Vulkan device");
    std::vector<VkPhysicalDevice> devices(physical_count);
    check(vkEnumeratePhysicalDevices(instance, &physical_count, devices.data()), "enumerate devices");
    const VkPhysicalDevice physical = devices.front();
    VkPhysicalDeviceProperties physical_info{};
    vkGetPhysicalDeviceProperties(physical, &physical_info);
    VkPhysicalDeviceMemoryProperties memory{};
    vkGetPhysicalDeviceMemoryProperties(physical, &memory);
    uint32_t family_count = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(physical, &family_count, nullptr);
    std::vector<VkQueueFamilyProperties> families(family_count);
    vkGetPhysicalDeviceQueueFamilyProperties(physical, &family_count, families.data());
    uint32_t family = 0;
    constexpr VkQueueFlags graphics_compute = VK_QUEUE_GRAPHICS_BIT | VK_QUEUE_COMPUTE_BIT;
    while (family < family_count && (families[family].queueFlags & graphics_compute) != graphics_compute) ++family;
    require(family < family_count, "graphics and compute queue family");

    VkPhysicalDeviceExternalImageFormatInfo external_format{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_IMAGE_FORMAT_INFO};
    external_format.handleType = ahb_handle;
    VkPhysicalDeviceImageFormatInfo2 image_format{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_IMAGE_FORMAT_INFO_2, &external_format};
    image_format.format = VK_FORMAT_R8G8B8A8_UNORM;
    image_format.type = VK_IMAGE_TYPE_2D;
    image_format.tiling = VK_IMAGE_TILING_OPTIMAL;
    image_format.usage = image_usage;
    VkExternalImageFormatProperties external_props{VK_STRUCTURE_TYPE_EXTERNAL_IMAGE_FORMAT_PROPERTIES};
    VkImageFormatProperties2 format_props{VK_STRUCTURE_TYPE_IMAGE_FORMAT_PROPERTIES_2, &external_props};
    check(vkGetPhysicalDeviceImageFormatProperties2(physical, &image_format, &format_props), "query AHB image format");
    require(external_props.externalMemoryProperties.externalMemoryFeatures & VK_EXTERNAL_MEMORY_FEATURE_IMPORTABLE_BIT,
            "RGBA8 AHB can be imported");
    const auto max_extent = format_props.imageFormatProperties.maxExtent;
    require(max_extent.width >= static_cast<uint32_t>(width) && max_extent.height >= static_cast<uint32_t>(height),
            "full stereo buffer fits");
    VkPhysicalDeviceExternalSemaphoreInfo external_sync{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_SEMAPHORE_INFO};
    external_sync.handleType = sync_handle;
    VkExternalSemaphoreProperties sync_props{VK_STRUCTURE_TYPE_EXTERNAL_SEMAPHORE_PROPERTIES};
    vkGetPhysicalDeviceExternalSemaphoreProperties(physical, &external_sync, &sync_props);
    constexpr auto sync_features = VK_EXTERNAL_SEMAPHORE_FEATURE_IMPORTABLE_BIT | VK_EXTERNAL_SEMAPHORE_FEATURE_EXPORTABLE_BIT;
    require((sync_props.externalSemaphoreFeatures & sync_features) == sync_features, "sync fd import and export");

    const float priority = 1.0f;
    VkDeviceQueueCreateInfo queue_info{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
    queue_info.queueFamilyIndex = family;
    queue_info.queueCount = 1;
    queue_info.pQueuePriorities = &priority;
    const char *extensions[] = {VK_ANDROID_EXTERNAL_MEMORY_ANDROID_HARDWARE_BUFFER_EXTENSION_NAME,
                                VK_EXT_QUEUE_FAMILY_FOREIGN_EXTENSION_NAME, VK_KHR_EXTERNAL_SEMAPHORE_FD_EXTENSION_NAME};
    VkDeviceCreateInfo device_info{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
    device_info.queueCreateInfoCount = 1;
    device_info.pQueueCreateInfos = &queue_info;
    device_info.enabledExtensionCount = std::size(extensions);
    device_info.ppEnabledExtensionNames = extensions;
    VkDevice device = VK_NULL_HANDLE;
    check(vkCreateDevice(physical, &device_info, nullptr, &device), "vkCreateDevice");
    const auto hardware_buffer_properties = reinterpret_cast<PFN_vkGetAndroidHardwareBufferPropertiesANDROID>(
        vkGetDeviceProcAddr(device, "vkGetAndroidHardwareBufferPropertiesANDROID"));
    const auto import_fd = reinterpret_cast<PFN_vkImportSemaphoreFdKHR>(vkGetDeviceProcAddr(device, "vkImportSemaphoreFdKHR"));
    const auto export_fd = reinterpret_cast<PFN_vkGetSemaphoreFdKHR>(vkGetDeviceProcAddr(device, "vkGetSemaphoreFdKHR"));
    require(hardware_buffer_properties && import_fd && export_fd, "resolve Vulkan extension entry points");
    VkQueue queue = VK_NULL_HANDLE;
    vkGetDeviceQueue(device, family, 0, &queue);

    VkBufferCreateInfo target_info{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
    target_info.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT;
    target_info.size = 16;
    VkBuffer target = VK_NULL_HANDLE;
    check(vkCreateBuffer(device, &target_info, nullptr, &target), "vkCreateBuffer");
    VkMemoryRequirements target_requirements{};
    vkGetBufferMemoryRequirements(device, target, &target_requirements);
    VkMemoryAllocateInfo target_allocation{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
    target_allocation.allocationSize = target_requirements.size;
    target_allocation.memoryTypeIndex = memory_type(memory, target_requirements.memoryTypeBits,
                                               VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
    VkDeviceMemory target_memory = VK_NULL_HANDLE;
    check(vkAllocateMemory(device, &target_allocation, nullptr, &target_memory), "allocate readback memory");
    check(vkBindBufferMemory(device, target, target_memory, 0), "vkBindBufferMemory");
    void *mapped = nullptr;
    check(vkMapMemory(device, target_memory, 0, VK_WHOLE_SIZE, 0, &mapped), "vkMapMemory");

    const VkDescriptorSetLayoutBinding bindings[] = {
        {0, VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 1, VK_SHADER_STAGE_COMPUTE_BIT, nullptr},
        {1, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1, VK_SHADER_STAGE_COMPUTE_BIT, nullptr},
    };
    VkDescriptorSetLayoutCreateInfo set_info{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
    set_info.bindingCount = std::size(bindings);
    set_info.pBindings = bindings;
    VkDescriptorSetLayout set_layout = VK_NULL_HANDLE;
    check(vkCreateDescriptorSetLayout(device, &set_info, nullptr, &set_layout), "create descriptor set layout");
    const VkDescriptorPoolSize pool_sizes[] = {{bindings[0].descriptorType, 1}, {bindings[1].descriptorType, 1}};
    VkDescriptorPoolCreateInfo descriptor_pool_info{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};
    descriptor_pool_info.maxSets = 1;
    descriptor_pool_info.poolSizeCount = std::size(pool_sizes);
    descriptor_pool_info.pPoolSizes = pool_sizes;
    VkDescriptorPool descriptor_pool = VK_NULL_HANDLE;
    check(vkCreateDescriptorPool(device, &descriptor_pool_info, nullptr, &descriptor_pool), "create descriptor pool");
    VkDescriptorSetAllocateInfo set_allocation{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};
    set_allocation.descriptorPool = descriptor_pool;
    set_allocation.descriptorSetCount = 1;
    set_allocation.pSetLayouts = &set_layout;
    VkDescriptorSet set = VK_NULL_HANDLE;
    check(vkAllocateDescriptorSets(device, &set_allocation, &set), "allocate descriptor set");
    VkPipelineLayoutCreateInfo layout_info{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
    layout_info.setLayoutCount = 1;
    layout_info.pSetLayouts = &set_layout;
    VkPipelineLayout layout = VK_NULL_HANDLE;
    check(vkCreatePipelineLayout(device, &layout_info, nullptr, &layout), "create pipeline layout");
    VkShaderModuleCreateInfo shader_info{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};
    shader_info.codeSize = shader_code.size() * sizeof(uint32_t);
    shader_info.pCode = shader_code.data();
    VkShaderModule shader = VK_NULL_HANDLE;
    check(vkCreateShaderModule(device, &shader_info, nullptr, &shader), "create verification shader");
    VkComputePipelineCreateInfo pipeline_info{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};
    pipeline_info.stage = {VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO};
    pipeline_info.stage.stage = VK_SHADER_STAGE_COMPUTE_BIT;
    pipeline_info.stage.module = shader;
    pipeline_info.stage.pName = "main";
    pipeline_info.layout = layout;
    VkPipeline pipeline = VK_NULL_HANDLE;
    check(vkCreateComputePipelines(device, VK_NULL_HANDLE, 1, &pipeline_info, nullptr, &pipeline), "create verification pipeline");
    VkSamplerCreateInfo sampler_info{VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO};
    sampler_info.addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    sampler_info.addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    sampler_info.addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    VkSampler sampler = VK_NULL_HANDLE;
    check(vkCreateSampler(device, &sampler_info, nullptr, &sampler), "create verification sampler");

    VkCommandPoolCreateInfo pool_info{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};
    pool_info.queueFamilyIndex = family;
    VkCommandPool pool = VK_NULL_HANDLE;
    check(vkCreateCommandPool(device, &pool_info, nullptr, &pool), "vkCreateCommandPool");
    VkCommandBufferAllocateInfo command_info{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
    command_info.commandPool = pool;
    command_info.commandBufferCount = 1;
    VkCommandBuffer command = VK_NULL_HANDLE;
    check(vkAllocateCommandBuffers(device, &command_info, &command), "vkAllocateCommandBuffers");
    VkSemaphore producer_done = VK_NULL_HANDLE;
    VkSemaphore consumer_done = VK_NULL_HANDLE;
    VkSemaphoreCreateInfo semaphore_info{VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO};
    check(vkCreateSemaphore(device, &semaphore_info, nullptr, &producer_done), "create acquire semaphore");
    VkExportSemaphoreCreateInfo export_info{VK_STRUCTURE_TYPE_EXPORT_SEMAPHORE_CREATE_INFO};
    export_info.handleTypes = sync_handle;
    semaphore_info.pNext = &export_info;
    check(vkCreateSemaphore(device, &semaphore_info, nullptr, &consumer_done), "create release semaphore");
    VkFenceCreateInfo fence_info{VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
    VkFence completed = VK_NULL_HANDLE;
    check(vkCreateFence(device, &fence_info, nullptr, &completed), "vkCreateFence");

    // The reader and its fixed-size configuration outlive this cache.
    std::map<uint64_t, ImportedImage> imported;
    int acquire_fds = 0;
    int release_fds = 0;
    bool flip = false;
    AImage *retained_frame = nullptr;
    uint64_t retained_id = 0;
    int retained_release_fd = -1;
    std::printf("device=%s GLES=%s source=%dx%d\n", physical_info.deviceName, glGetString(GL_VERSION), width, height);
    for (int i = 0; i < frames; ++i) {
        const uint8_t tag = static_cast<uint8_t>(i + 1);
        const std::array<uint8_t, 16> gl_pixels{tag, 0, 0, 255, 0, tag, 0, 255,
                                                0, 0, tag, 255, tag, tag, 0, 255};
        glEnable(GL_SCISSOR_TEST);
        for (int quadrant = 0; quadrant < 4; ++quadrant) {
            glScissor((quadrant % 2) * width / 2, (quadrant / 2) * height / 2, width / 2, height / 2);
            const uint8_t *rgba = gl_pixels.data() + 4 * quadrant;
            glClearColor(rgba[0] / 255.0f, rgba[1] / 255.0f, rgba[2] / 255.0f, 1.0f);
            glClear(GL_COLOR_BUFFER_BIT);
        }
        const int64_t stamp = now_ns();
        require(set_time(egl, surface, stamp) && eglSwapBuffers(egl, surface), "post EGL frame");
        AImage *frame = nullptr;
        int acquire_fd = -1;
        media_result = AImageReader_acquireLatestImageAsync(reader, &frame, &acquire_fd);
        require(media_result == AMEDIA_OK, "acquire reader frame", media_result);
        int64_t acquired_stamp = 0;
        require(AImage_getTimestamp(frame, &acquired_stamp) == AMEDIA_OK && acquired_stamp == stamp,
                "match producer timestamp exactly");
        AImageCropRect crop{};
        require(AImage_getCropRect(frame, &crop) == AMEDIA_OK && crop.left == 0 && crop.top == 0 &&
                crop.right == width && crop.bottom == height, "image exposes the full stereo crop");

        AHardwareBuffer *buffer = nullptr;
        uint64_t buffer_id = 0;
        require(AImage_getHardwareBuffer(frame, &buffer) == AMEDIA_OK && AHardwareBuffer_getId(buffer, &buffer_id) == 0,
                "read image buffer identity");
        if (retained_frame) {
            require(buffer_id != retained_id, "producer did not reuse the retained buffer");
            AImage_deleteAsync(retained_frame, retained_release_fd);
        }
        const auto [it, inserted] = imported.try_emplace(buffer_id);
        auto &image = it->second;
        if (inserted) {
            require(imported.size() <= 8, "bounded external buffer pool");
            AHardwareBuffer_Desc desc{};
            AHardwareBuffer_describe(buffer, &desc);
            require(desc.width == static_cast<uint32_t>(width) && desc.height == static_cast<uint32_t>(height) && desc.layers == 1 &&
                    desc.format == AHARDWAREBUFFER_FORMAT_R8G8B8A8_UNORM && (desc.usage & reader_usage) == reader_usage,
                    "reader buffer matches format, size and usage");
            VkAndroidHardwareBufferFormatPropertiesANDROID format{VK_STRUCTURE_TYPE_ANDROID_HARDWARE_BUFFER_FORMAT_PROPERTIES_ANDROID};
            VkAndroidHardwareBufferPropertiesANDROID properties{VK_STRUCTURE_TYPE_ANDROID_HARDWARE_BUFFER_PROPERTIES_ANDROID, &format};
            check(hardware_buffer_properties(device, buffer, &properties), "query reader buffer properties");
            require(format.format == image_format.format, "reader buffer Vulkan format is RGBA8");
            VkExternalMemoryImageCreateInfo external_image{VK_STRUCTURE_TYPE_EXTERNAL_MEMORY_IMAGE_CREATE_INFO};
            external_image.handleTypes = ahb_handle;
            VkImageCreateInfo image_info{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, &external_image};
            image_info.imageType = VK_IMAGE_TYPE_2D;
            image_info.format = format.format;
            image_info.extent = {desc.width, desc.height, 1};
            image_info.mipLevels = 1;
            image_info.arrayLayers = 1;
            image_info.samples = VK_SAMPLE_COUNT_1_BIT;
            image_info.usage = image_usage;
            check(vkCreateImage(device, &image_info, nullptr, &image.image), "create external reader image");
            VkMemoryDedicatedAllocateInfo dedicated{VK_STRUCTURE_TYPE_MEMORY_DEDICATED_ALLOCATE_INFO};
            dedicated.image = image.image;
            VkImportAndroidHardwareBufferInfoANDROID import_info{VK_STRUCTURE_TYPE_IMPORT_ANDROID_HARDWARE_BUFFER_INFO_ANDROID, &dedicated};
            import_info.buffer = buffer;
            VkMemoryAllocateInfo allocation{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, &import_info};
            allocation.allocationSize = properties.allocationSize;
            allocation.memoryTypeIndex = memory_type(memory, properties.memoryTypeBits, 0);
            check(vkAllocateMemory(device, &allocation, nullptr, &image.memory), "import reader buffer");
            check(vkBindImageMemory(device, image.image, image.memory, 0), "bind reader buffer");
            VkImageViewCreateInfo view_info{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};
            view_info.image = image.image;
            view_info.viewType = VK_IMAGE_VIEW_TYPE_2D;
            view_info.format = format.format;
            view_info.subresourceRange = pixels;
            check(vkCreateImageView(device, &view_info, nullptr, &image.view), "create reader image view");
            std::printf("imported id=%" PRIu64 " bytes=%" PRIu64 " usage=0x%" PRIx64 "\n",
                        buffer_id, properties.allocationSize, desc.usage);
        }

        const VkDescriptorImageInfo texture_info{sampler, image.view, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
        const VkDescriptorBufferInfo output_info{target, 0, VK_WHOLE_SIZE};
        VkWriteDescriptorSet writes[] = {{VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET}, {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET}};
        for (size_t binding = 0; binding < std::size(writes); ++binding) {
            writes[binding].dstSet = set;
            writes[binding].dstBinding = bindings[binding].binding;
            writes[binding].descriptorType = bindings[binding].descriptorType;
            writes[binding].descriptorCount = 1;
        }
        writes[0].pImageInfo = &texture_info;
        writes[1].pBufferInfo = &output_info;
        vkUpdateDescriptorSets(device, std::size(writes), writes, 0, nullptr);
        VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
        begin.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
        check(vkBeginCommandBuffer(command, &begin), "vkBeginCommandBuffer");
        VkImageMemoryBarrier ownership{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};
        ownership.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
        ownership.oldLayout = VK_IMAGE_LAYOUT_GENERAL;
        ownership.newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
        ownership.srcQueueFamilyIndex = VK_QUEUE_FAMILY_FOREIGN_EXT;
        ownership.dstQueueFamilyIndex = family;
        ownership.image = image.image;
        ownership.subresourceRange = pixels;
        vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, 0,
                             0, nullptr, 0, nullptr, 1, &ownership);
        vkCmdBindPipeline(command, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline);
        vkCmdBindDescriptorSets(command, VK_PIPELINE_BIND_POINT_COMPUTE, layout, 0, 1, &set, 0, nullptr);
        vkCmdDispatch(command, 1, 1, 1);
        std::swap(ownership.oldLayout, ownership.newLayout);
        std::swap(ownership.srcQueueFamilyIndex, ownership.dstQueueFamilyIndex);
        std::swap(ownership.srcAccessMask, ownership.dstAccessMask);
        VkMemoryBarrier readback{VK_STRUCTURE_TYPE_MEMORY_BARRIER};
        readback.srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT;
        readback.dstAccessMask = VK_ACCESS_HOST_READ_BIT;
        vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_HOST_BIT, 0,
                             1, &readback, 0, nullptr, 1, &ownership);
        check(vkEndCommandBuffer(command), "vkEndCommandBuffer");

        const VkPipelineStageFlags wait_stage = VK_PIPELINE_STAGE_ALL_COMMANDS_BIT;
        VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};
        if (acquire_fd >= 0) {
            VkImportSemaphoreFdInfoKHR imported_fence{VK_STRUCTURE_TYPE_IMPORT_SEMAPHORE_FD_INFO_KHR};
            imported_fence.semaphore = producer_done;
            imported_fence.flags = VK_SEMAPHORE_IMPORT_TEMPORARY_BIT;
            imported_fence.handleType = sync_handle;
            imported_fence.fd = acquire_fd;
            check(import_fd(device, &imported_fence), "import producer sync fd");
            ++acquire_fds;
            submit.waitSemaphoreCount = 1;
            submit.pWaitSemaphores = &producer_done;
            submit.pWaitDstStageMask = &wait_stage;
        }
        submit.commandBufferCount = 1;
        submit.pCommandBuffers = &command;
        submit.signalSemaphoreCount = 1;
        submit.pSignalSemaphores = &consumer_done;
        check(vkQueueSubmit(queue, 1, &submit, completed), "vkQueueSubmit");
        VkSemaphoreGetFdInfoKHR release{VK_STRUCTURE_TYPE_SEMAPHORE_GET_FD_INFO_KHR};
        release.semaphore = consumer_done;
        release.handleType = sync_handle;
        int release_fd = -1;
        check(export_fd(device, &release, &release_fd), "export reader release sync fd");
        release_fds += release_fd >= 0;
        // Reprojection keeps the previous frame until a different buffer has reached the consumer.
        retained_frame = frame;
        retained_id = buffer_id;
        retained_release_fd = release_fd;
        check(vkWaitForFences(device, 1, &completed, VK_TRUE, timeout_ns), "wait for verification readback");
        const auto top_down = std::array<uint8_t, 16>{0, 0, tag, 255, tag, tag, 0, 255,
                                                      tag, 0, 0, 255, 0, tag, 0, 255};
        if (i == 0) flip = std::memcmp(mapped, top_down.data(), top_down.size()) == 0;
        const auto &expected = flip ? top_down : gl_pixels;
        if (std::memcmp(mapped, expected.data(), expected.size()) != 0) {
            const auto *actual = static_cast<const uint8_t *>(mapped);
            std::fprintf(stderr, "frame %d mismatch:", i);
            for (int p = 0; p < 16; ++p) std::fprintf(stderr, " %02x", actual[p]);
            std::fputc('\n', stderr);
            return 2;
        }
        check(vkResetFences(device, 1, &completed), "vkResetFences");
        check(vkResetCommandPool(device, pool, 0), "vkResetCommandPool");
    }
    std::printf("verified=%d imports=%zu exact_timestamps=%d acquire_fds=%d release_fds=%d raw_y=%s\n",
                frames, imported.size(), frames, acquire_fds, release_fds, flip ? "top-first" : "bottom-first");

    AImage_deleteAsync(retained_frame, retained_release_fd);
    for (const auto &[id, image] : imported) {
        vkDestroyImageView(device, image.view, nullptr);
        vkDestroyImage(device, image.image, nullptr);
        vkFreeMemory(device, image.memory, nullptr);
    }
    vkDestroyFence(device, completed, nullptr);
    vkDestroySemaphore(device, consumer_done, nullptr);
    vkDestroySemaphore(device, producer_done, nullptr);
    vkDestroyCommandPool(device, pool, nullptr);
    vkDestroySampler(device, sampler, nullptr);
    vkDestroyPipeline(device, pipeline, nullptr);
    vkDestroyShaderModule(device, shader, nullptr);
    vkDestroyPipelineLayout(device, layout, nullptr);
    vkDestroyDescriptorPool(device, descriptor_pool, nullptr);
    vkDestroyDescriptorSetLayout(device, set_layout, nullptr);
    vkUnmapMemory(device, target_memory);
    vkDestroyBuffer(device, target, nullptr);
    vkFreeMemory(device, target_memory, nullptr);
    vkDestroyDevice(device, nullptr);
    vkDestroyInstance(instance, nullptr);
    eglMakeCurrent(egl, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
    eglDestroySurface(egl, surface);
    eglDestroyContext(egl, context);
    eglTerminate(egl);
    AImageReader_delete(reader);
    return 0;
}
