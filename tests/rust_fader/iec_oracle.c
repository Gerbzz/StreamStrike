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
int main(void) {
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
