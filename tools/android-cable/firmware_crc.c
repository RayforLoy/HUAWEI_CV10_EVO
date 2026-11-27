#include <jni.h>
#include <stdint.h>

JNIEXPORT jint JNICALL
Java_org_cv10_cableupdater_Firmware_crc16Usb(JNIEnv *env, jclass type,
                                            jbyteArray image, jint length)
{
    (void)type;
    if (image == NULL || length < 0 || length > (*env)->GetArrayLength(env, image)) {
        return -1;
    }
    jbyte *bytes = (*env)->GetByteArrayElements(env, image, NULL);
    if (bytes == NULL) {
        return -1;
    }

    uint16_t crc = 0xffff;
    for (jint i = 0; i < length; ++i) {
        crc ^= (uint8_t)bytes[i];
        for (unsigned bit = 0; bit < 8; ++bit) {
            crc = (crc >> 1) ^ ((crc & 1) ? 0xa001 : 0);
        }
    }
    (*env)->ReleaseByteArrayElements(env, image, bytes, JNI_ABORT);
    return crc ^ 0xffff;
}
