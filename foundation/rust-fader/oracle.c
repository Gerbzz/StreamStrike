/* Build-only original OBS IEC reference, GPL-2.0-or-later.
 * Copyright (C) 2014 Leonhard Oelke. Not linked into shipped libobs. */
#include <cpuid.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static float iec_def_to_db(const float def)
{
	if (def == 1.0f)
		return 0.0f;
	else if (def <= 0.0f)
		return -INFINITY;

	float db;

	if (def >= 0.75f)
		db = (def - 1.0f) / 0.25f * 9.0f;
	else if (def >= 0.5f)
		db = (def - 0.75f) / 0.25f * 11.0f - 9.0f;
	else if (def >= 0.3f)
		db = (def - 0.5f) / 0.2f * 10.0f - 20.0f;
	else if (def >= 0.15f)
		db = (def - 0.3f) / 0.15f * 10.0f - 30.0f;
	else if (def >= 0.075f)
		db = (def - 0.15f) / 0.075f * 10.0f - 40.0f;
	else if (def >= 0.025f)
		db = (def - 0.075f) / 0.05f * 10.0f - 50.0f;
	else if (def >= 0.001f)
		db = (def - 0.025f) / 0.025f * 90.0f - 60.0f;
	else
		db = -INFINITY;

	return db;
}

static float iec_db_to_def(const float db)
{
	if (db == 0.0f)
		return 1.0f;
	else if (db == -INFINITY)
		return 0.0f;

	float def;

	if (db >= -9.0f)
		def = (db + 9.0f) / 9.0f * 0.25f + 0.75f;
	else if (db >= -20.0f)
		def = (db + 20.0f) / 11.0f * 0.25f + 0.5f;
	else if (db >= -30.0f)
		def = (db + 30.0f) / 10.0f * 0.2f + 0.3f;
	else if (db >= -40.0f)
		def = (db + 40.0f) / 10.0f * 0.15f + 0.15f;
	else if (db >= -50.0f)
		def = (db + 50.0f) / 10.0f * 0.075f + 0.075f;
	else if (db >= -60.0f)
		def = (db + 60.0f) / 10.0f * 0.05f + 0.025f;
	else if (db >= -114.0f)
		def = (db + 150.0f) / 90.0f * 0.025f;
	else
		def = 0.0f;

	return def;
}

/* Test original OBS function bodies against the Rust archive through C ABI. */
extern float streamstrike_iec_def_to_db(float);
extern float streamstrike_iec_db_to_def(float);
static uint32_t bits(float value) { uint32_t out; memcpy(&out, &value, sizeof out); return out; }
static int compare(float value) {
    float expected[] = {iec_def_to_db(value), iec_db_to_def(value)};
    float actual[] = {streamstrike_iec_def_to_db(value), streamstrike_iec_db_to_def(value)};
    for (unsigned i = 0; i < 2; ++i) {
        if (bits(expected[i]) != bits(actual[i])) {
            fprintf(stderr, "function %u input %08x expected %08x actual %08x\n",
                    i, bits(value), bits(expected[i]), bits(actual[i]));
            return 1;
        }
    }
    return 0;
}
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    if (strcmp(argv[1], "fused") == 0) {
        unsigned a, b, c, d, lo, hi;
        if (!__get_cpuid(1, &a, &b, &c, &d) ||
            (c & (bit_FMA | bit_AVX | bit_OSXSAVE)) != (bit_FMA | bit_AVX | bit_OSXSAVE)) return 2;
        __asm__ volatile ("xgetbv" : "=a"(lo), "=d"(hi) : "c"(0));
        if ((lo & 6) != 6) return 2;
    }

    float edges[] = {-INFINITY, INFINITY, NAN, -0.0f, 0.0f, 1.0f,
                    0.75f, 0.5f, 0.3f, 0.15f, 0.075f, 0.025f, 0.001f,
                    -9.0f, -20.0f, -30.0f, -40.0f, -50.0f, -60.0f, -114.0f, -150.0f};
    for (unsigned i = 0; i < sizeof edges / sizeof *edges; ++i) {
        if (compare(edges[i]) || compare(nextafterf(edges[i], -INFINITY)) ||
            compare(nextafterf(edges[i], INFINITY))) return 1;
    }
    uint32_t seed = 0x12345678;
    for (unsigned i = 0; i < 200000; ++i) {
        seed = seed * 1664525u + 1013904223u;
        float value; memcpy(&value, &seed, sizeof value);
        if (compare(value)) return 1;
    }
    puts("IEC parity: 200000 random bit patterns plus boundary neighbors passed");
    return 0;
}
