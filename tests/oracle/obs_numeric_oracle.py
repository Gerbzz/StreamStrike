"""Defined numeric reads/unsets from the same pinned OBS source, not libobs ABI."""
import obs_scalar_oracle as base

# Preserve native number representation; the item container remains a test layout.
number_struct = base.source[base.source.index('struct obs_data_number {'):]
number_struct = number_struct[:number_struct.index('\n};') + 3]
preamble = base.preamble.replace('OBS_DATA_STRING, OBS_DATA_BOOLEAN',
                                'OBS_DATA_STRING, OBS_DATA_BOOLEAN, OBS_DATA_NUMBER')
preamble += '''
#include <inttypes.h>
#include <limits.h>
#include <float.h>
#include <math.h>
enum obs_data_number_type { OBS_DATA_NUM_INVALID, OBS_DATA_NUM_INT, OBS_DATA_NUM_DOUBLE };
'''
preamble += number_struct
preamble += '''
_Static_assert(sizeof(long long) == 8, "oracle requires 64-bit OBS integers");
_Static_assert(sizeof(double) == 8 && FLT_RADIX == 2 && DBL_MANT_DIG == 53 && DBL_MAX_EXP == 1024,
               "oracle requires binary64 double");
_Static_assert(sizeof(obs_data_item_t) % _Alignof(struct obs_data_number) == 0,
               "numeric payload must be aligned");
'''
names = base.names + ['item_int', 'data_item_get_int', 'item_double',
                      'data_item_get_double', 'obs_data_item_numtype']
harness = r'''
static size_t put_number(unsigned char *p, int state) {
 struct obs_data_number num = {0};
 if (!state) return 0;
 if (state == 1) { num.type=OBS_DATA_NUM_INT; num.int_val=-17; }
 else { num.type=OBS_DATA_NUM_DOUBLE; num.double_val=3.75; }
 memcpy(p, &num, sizeof num); return sizeof num;
}
static void print_read(obs_data_item_t *item, get_data_t get_data) {
 /* Enforce the oracle's defined domain before invoking the original cast.
    This harness check is not used as the Rust implementation's expectation. */
 struct obs_data_number *num = get_data(item);
 if (num && num->type == OBS_DATA_NUM_DOUBLE &&
     (!isfinite(num->double_val) || num->double_val < -0x1p63 || num->double_val >= 0x1p63)) {
  fputs("refusing native-undefined double-to-integer oracle input\n",stderr);
  exit(3);
 }
 double d = data_item_get_double(item, get_data);
 uint64_t bits; memcpy(&bits, &d, sizeof bits);
 printf("\t%lld\t%016" PRIx64, data_item_get_int(item,get_data), bits);
}
static void print_item(obs_data_item_t *item) {
 print_read(item, get_item_data);
 print_read(item, get_item_default_data);
 print_read(item, get_item_autoselect_data);
 printf("\t%d\t%d\t%d\t%d\t%d\t%zu\n", obs_data_item_numtype(item),
   obs_data_item_has_user_value(item), obs_data_item_has_default_value(item),
   obs_data_item_has_autoselect_value(item),data_item_get_bool(item,get_item_data),
   strlen(data_item_get_string(item,get_item_data)));
}
int main(void) {
 for(int u=0; u<3; u++) for(int d=0; d<3; d++) for(int a=0; a<3; a++)
 for(int op=0; op<4; op++) {
  obs_data_item_t *item=calloc(1,sizeof(*item)+3*sizeof(struct obs_data_number));
  if(!item) return 2;
  item->type=OBS_DATA_NUMBER;
  unsigned char *p=(unsigned char *)(item+1);
  item->data_size=item->data_len=put_number(p,u); p+=item->data_len;
  item->default_size=item->default_len=put_number(p,d); p+=item->default_len;
  item->autoselect_size=put_number(p,a);
  if(op==1) obs_data_item_unset_user_value(item);
  if(op==2) obs_data_item_unset_default_value(item);
  if(op==3) obs_data_item_unset_autoselect_value(item);
  printf("tiers\t%d\t%d\t%d\t%d",u,d,a,op); print_item(item); free(item);
 }
 /* Every double in this table has a defined double->long long conversion.
    Do not add NaN, infinity, +2^63 or values below -2^63 here. */
 const long long ints[]={0,1,-1,LLONG_MIN,LLONG_MAX,9007199254740991LL,
                         9007199254740992LL,9007199254740993LL,-9007199254740993LL};
 const double doubles[]={0.0,-0.0,0.75,-0.75,1.75,-1.75,0x1p-1074,-0x1p-1074,
                         -0x1p63,0x1.fffffffffffffp62};
 for(int kind=0;kind<2;kind++) {
  size_t n=kind==0 ? sizeof ints/sizeof *ints : sizeof doubles/sizeof *doubles;
  for(size_t i=0;i<n;i++) {
   obs_data_item_t *item=calloc(1,sizeof(*item)+sizeof(struct obs_data_number));
   if(!item) return 2;
   item->type=OBS_DATA_NUMBER; item->data_size=item->data_len=sizeof(struct obs_data_number);
   struct obs_data_number num={0};
   if(kind==0) { num.type=OBS_DATA_NUM_INT; num.int_val=ints[i]; }
   else { num.type=OBS_DATA_NUM_DOUBLE; num.double_val=doubles[i]; }
   memcpy(item+1,&num,sizeof num);
   if(kind==0) printf("int\t%lld\t0\t0\t0",ints[i]);
   else { uint64_t bits; memcpy(&bits,&doubles[i],sizeof bits); printf("double\t%016" PRIx64 "\t0\t0\t0",bits); }
   print_item(item); free(item);
  }
 }
 return 0;
}
'''

if __name__ == '__main__':
    base.run(harness, preamble, names)
