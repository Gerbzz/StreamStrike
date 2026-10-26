/* Reduced unattached-fader state semantics, not complete-libobs acceptance.
 * Derived from OBS Leonhard Oelke 2014; GPL-2.0-or-later. */
#include <math.h>
#include <stdint.h>
#include <string.h>
extern float streamstrike_iec_def_to_db(float);
extern float streamstrike_iec_db_to_def(float);
void diagnostic_row(int operation, uint32_t input_bits, uint32_t output[4])
{
    float input;
    memcpy(&input, &input_bits, sizeof input);
    float db = operation ? input : streamstrike_iec_def_to_db(input);
    int accepted = 1;
    if (db > 0.0f) {
        db = 0.0f;
        accepted = 0;
    }
    if (db < -INFINITY) {
        db = -INFINITY;
        accepted = 0;
    }
    float def = streamstrike_iec_db_to_def(db);
    output[0] = input_bits;
    output[1] = accepted;
    memcpy(output + 2, &db, sizeof db);
    memcpy(output + 3, &def, sizeof def);
}
