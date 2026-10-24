"""Run verbatim pinned OBS getter/unset functions, not a full libobs build."""
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / 'evidence/upstream/libobs/obs-data.c').read_bytes()
if hashlib.sha256(source).hexdigest() != 'be204adab14cf4e814df4841a9fd6050297fdd97b79e62645dac7d239085b214':
    raise ValueError('OBS source fixture differs from reviewed upstream pin')
source = source.decode()

def function(name):
    match = re.search(r'^[^\n]*\b' + name + r'\([^;]*?\)\n\{', source, re.M)
    if not match:
        raise ValueError(name)
    start = match.start()
    end = match.end()
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'

names = ['get_item_name', 'get_data_ptr', 'get_item_data', 'get_default_data_ptr',
         'get_item_default_data', 'get_autoselect_data_ptr', 'get_item_autoselect_data',
         'move_data', 'item_valid', 'data_item_get_bool', 'data_item_get_string',
         'obs_data_item_has_user_value', 'obs_data_item_has_default_value',
         'obs_data_item_has_autoselect_value', 'obs_data_item_unset_user_value',
         'obs_data_item_unset_default_value', 'obs_data_item_unset_autoselect_value']
preamble = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
enum obs_data_type { OBS_DATA_STRING, OBS_DATA_BOOLEAN };
/* Test layout, NOT ABI layout. Only fields read by extracted functions. */
typedef struct obs_data_item {
 enum obs_data_type type;
 size_t name_len, data_len, data_size, default_len, default_size, autoselect_size;
} obs_data_item_t;
typedef void *(*get_data_t)(obs_data_item_t *);
/* For primitive scalar types upstream release helpers have no side effects.
   Objects/arrays are deliberately outside this executable's domain. */
static void item_data_release(obs_data_item_t *item) { (void)item; }
static void item_default_data_release(obs_data_item_t *item) { (void)item; }
static void item_autoselect_data_release(obs_data_item_t *item) { (void)item; }
'''
harness = r'''
static size_t put(unsigned char *p, int kind, int state) {
 if (!state) return 0;
 if (kind == 0) { bool v = state == 2; memcpy(p, &v, sizeof v); return sizeof v; }
 const char *v = state == 1 ? "" : "選択";
 size_t n = strlen(v) + 1; memcpy(p, v, n); return n;
}
int main(void) {
 for (int kind=0; kind<2; kind++)
 for (int u=0; u<3; u++) for(int d=0; d<3; d++) for(int a=0; a<3; a++)
 for (int op=0; op<4; op++) {
  obs_data_item_t *item = calloc(1, sizeof(*item) + 64);
  if (!item) return 2;
  item->type = kind == 0 ? OBS_DATA_BOOLEAN : OBS_DATA_STRING;
  unsigned char *p = (unsigned char *)(item + 1);
  item->data_size = item->data_len = put(p, kind, u); p += item->data_len;
  item->default_size = item->default_len = put(p, kind, d); p += item->default_len;
  item->autoselect_size = put(p, kind, a);
  if (op==1) obs_data_item_unset_user_value(item);
  if (op==2) obs_data_item_unset_default_value(item);
  if (op==3) obs_data_item_unset_autoselect_value(item);
  printf("%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%s\t%s\t%s\t%d\t%d\t%d\n",
   kind,u,d,a,op,
   data_item_get_bool(item,get_item_data), data_item_get_bool(item,get_item_default_data), data_item_get_bool(item,get_item_autoselect_data),
   data_item_get_string(item,get_item_data), data_item_get_string(item,get_item_default_data), data_item_get_string(item,get_item_autoselect_data),
   obs_data_item_has_user_value(item),obs_data_item_has_default_value(item),obs_data_item_has_autoselect_value(item));
  free(item);
 }
 return 0;
}
'''
def run(harness, preamble=preamble, names=names):
    with tempfile.TemporaryDirectory(prefix='obs-scalar-oracle-') as folder:
        c = Path(folder) / 'oracle.c'
        exe = Path(folder) / 'oracle'
        c.write_text(source[:source.index('#include')] + preamble + ''.join(map(function, names)) + harness)
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)

if __name__ == '__main__':
    run(harness)
