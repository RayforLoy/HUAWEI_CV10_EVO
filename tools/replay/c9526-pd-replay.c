#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "emu8051.h"

static struct em8051 cpu;
static uint8_t code[65536], xdata[65536], upper[128], fifo[32];
static unsigned count;

static void write_xdata(struct em8051 *m, uint16_t address, uint8_t value) {
    (void)m;
    xdata[address] = value;
    if (address == 0x1022) {
        assert(count < sizeof fifo);
        fifo[count++] = value;
    }
}

static void call(unsigned entry) {
    cpu.mLowerData[0x6f] = 0x00;
    cpu.mLowerData[0x70] = 0xed;
    cpu.mSFR[REG_SP] = 0x70;
    cpu.mPC = entry;
    cpu.mTickDelay = 0;
    for (unsigned i = 0; i < 40000 && cpu.mPC != 0xed00; ++i) tick(&cpu);
    if (cpu.mPC != 0xed00) fprintf(stderr, "0x%04x stopped at 0x%04x\n", entry, cpu.mPC);
    assert(cpu.mPC == 0xed00);
}

static void start_case(void) {
    reset(&cpu, false);
    memset(cpu.mLowerData, 0, sizeof cpu.mLowerData);
    memset(upper, 0, sizeof upper);
    memset(xdata, 0, sizeof xdata);
    count = 0;
    cpu.xwrite = write_xdata;
    xdata[0x28d1] = 1;
}

static void expect_caps(const char *label, unsigned n, unsigned milliamps) {
    assert(count == 4 * n);
    assert((xdata[0x1020] & 0x1f) == 1);
    assert((xdata[0x1021] >> 4 & 7) == n);
    printf("%s  header=%02X %02X  PDOs=", label, xdata[0x1020], xdata[0x1021]);
    for (unsigned i = 0; i < n; ++i) {
        const uint8_t *object = fifo + 4 * i;
        uint32_t pdo = object[0] | (uint32_t)object[1] << 8 | (uint32_t)object[2] << 16 | (uint32_t)object[3] << 24;
        unsigned mv = ((pdo >> 10) & 0x3ff) * 50;
        unsigned ma = (pdo & 0x3ff) * 10;
        printf("%s%08lX (%u mV, %u mA)", i ? ", " : "", (unsigned long)pdo, mv, ma);
        assert(pdo >> 30 == 0);
        assert(mv == (i ? 9000 : 5000));
        if (milliamps && !i) assert(ma == milliamps);
    }
    putchar('\n');
}

static void load_source_caps(unsigned n, const uint32_t *pdo) {
    const unsigned rx = 0x2adc + 0x1c;
    cpu.mLowerData[7] = 1;
    cpu.mLowerData[0x49] = 5;
    upper[0x09] = 0x86;
    xdata[0x2a5a] = 1;
    xdata[0x2a54] = n;
    for (unsigned i = 0; i < n; ++i) {
        for (unsigned j = 0; j < 4; ++j) xdata[rx + i * 4 + j] = pdo[i] >> (8 * j);
    }
    call(0x65ee);
    printf("input NDO=%u, policy count after import=%u, first entry=", n, cpu.mLowerData[0x43]);
    for (unsigned i = 0; i < 7; ++i) printf("%02X", xdata[0x294a + i]);
    putchar('\n');
    assert(cpu.mLowerData[0x43] == 1);
}

int main(int argc, char **argv) {
    assert(argc == 2);
    FILE *image = fopen(argv[1], "rb");
    assert(image);
    assert(fread(code, 1, 0xc000, image) == 0xc000);
    fclose(image);
    cpu.mCodeMem = code;
    cpu.mCodeMemMaxIdx = 65535;
    cpu.mExtData = xdata;
    cpu.mExtDataMaxIdx = 65535;
    cpu.mUpperData = upper;

    start_case();
    call(0x5bfe);
    expect_caps("fallback", 1, 1000);

    const uint32_t caps[] = {0x0001912c, 0x0002d12c, 0xc0dc213c};
    start_case();
    load_source_caps(3, caps);
    assert(xdata[0x2951] == 0 && xdata[0x2956] == 0);
    call(0x5bfe);
    expect_caps("stock upstream 5 V + 9 V + PPS", 1, 1500);

    start_case();
    load_source_caps(3, caps);
    cpu.mLowerData[7] = 1;
    cpu.mLowerData[5] = 1;
    xdata[0x2a7e] = 1;
    call(0x0ebe);
    assert((xdata[0x1220] & 0x1f) == 2);
    assert((xdata[0x1221] >> 4 & 7) == 1);
    assert((xdata[0x1225] >> 4 & 7) == 1);
    printf("upstream initial Request  header=%02X %02X  RDO=",
           xdata[0x1220], xdata[0x1221]);
    for (int i = 3; i >= 0; --i) printf("%02X", xdata[0x1222 + i]);
    putchar('\n');

    start_case();
    cpu.mLowerData[7] = 2;
    xdata[0x2a7f] = 1;
    call(0x6459);
    assert((xdata[0x1420] & 0x1f) == 1);
    assert((xdata[0x1421] >> 4 & 7) == 1);
    assert(xdata[0x1422] == 0x5a && xdata[0x1423] == 0x90 && xdata[0x1424] == 1);
    printf("port 2 fallback  header=%02X %02X  PDO=%02X%02X%02X%02X\n",
           xdata[0x1420], xdata[0x1421], xdata[0x1425], xdata[0x1424], xdata[0x1423], xdata[0x1422]);

    start_case();
    load_source_caps(3, caps);
    cpu.mLowerData[0x43] = 3;
    xdata[0x2954] = 0x00;
    xdata[0x2955] = 0xb4;
    xdata[0x2956] = 0x01;
    xdata[0x2957] = 0x2c;
    xdata[0x2958] = 0xc0;
    call(0x5bfe);
    expect_caps("counterfactual policy table seeded with 9 V and PPS", 2, 1500);
    return 0;
}
