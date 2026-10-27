/* Original OBS cubic/logarithmic bodies via Rust C ABI; GPL-2.0-or-later. */
extern float streamstrike_cubic_def_to_db(float);
extern float streamstrike_cubic_db_to_def(float);
extern float streamstrike_log_def_to_db(float);
extern float streamstrike_log_db_to_def(float);
static uint32_t bits(float value) { uint32_t out; memcpy(&out, &value, sizeof out); return out; }
static int compare(float value) {
    float expected[] = {cubic_def_to_db(value), cubic_db_to_def(value), log_def_to_db(value), log_db_to_def(value)};
    float actual[] = {streamstrike_cubic_def_to_db(value), streamstrike_cubic_db_to_def(value), streamstrike_log_def_to_db(value), streamstrike_log_db_to_def(value)};
    for (unsigned i = 0; i < 4; ++i) {
        if (bits(expected[i]) != bits(actual[i])) {
            fprintf(stderr, "function %u input %08x expected %08x actual %08x\n",
                    i, bits(value), bits(expected[i]), bits(actual[i]));
            return 1;
        }
    }
    return 0;
}
int main(void) {
    float edges[] = {-INFINITY, INFINITY, NAN, -0.0f, 0.0f, 1.0f,
                    0.75f, 0.5f, 0.3f, 0.15f, 0.075f, 0.025f, 0.001f,
                    -9.0f, -20.0f, -30.0f, -40.0f, -50.0f, -60.0f, -114.0f, -150.0f, -96.0f, 6.0f};
    for (unsigned i = 0; i < sizeof edges / sizeof *edges; ++i) {
        if (compare(edges[i]) || compare(nextafterf(edges[i], -INFINITY)) ||
            compare(nextafterf(edges[i], INFINITY))) return 1;
    }
    /* Directed cubic underflow/overflow and signed/signaling NaN payloads. */
    uint32_t directed[] = {0x26800000u, 0x26800001u, 0x26800002u,
                           0x54cb2ff4u, 0x54cb2ff5u, 0x54cb2ff6u,
                           0x7f800001u, 0x7fc12345u, 0xff800001u, 0xffc12345u};
    for (unsigned i = 0; i < sizeof directed / sizeof *directed; ++i) {
        float value; memcpy(&value, &directed[i], sizeof value);
        if (compare(value)) return 1;
    }
    uint32_t seed = 0x12345678;
    for (unsigned i = 0; i < 200000; ++i) {
        seed = seed * 1664525u + 1013904223u;
        float value; memcpy(&value, &seed, sizeof value);
        if (compare(value)) return 1;
    }
    puts("Remaining fader parity: 200000 random bit patterns plus boundary neighbors passed");
    return 0;
}
