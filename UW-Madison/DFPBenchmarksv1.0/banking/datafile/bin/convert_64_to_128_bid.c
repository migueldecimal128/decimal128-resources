//----------------------------------------
// rate.c
// Currency Conversion Microbenchmark
// Decimal Floating-Point Benchmark
// header file to generate/access/update/close all the rate tables
// Developed by Liang-Kai Wang
// Department of Electrical and Computer Engineering
// University of Wisconsin-Madison
// $Revision: 1.1 $

#define DECIMAL_GLOBAL_EXCEPTION_FLAGS 1
#define DECNUMDIGITS 34
#include "dfp_includes.h"
  
int main(int argc, char *argv[]) {
  int size;
  int i;
  UINT64 num;
  UINT128 num128;
  _IDEC_round set;
  FILE *infile;
  FILE *outfile;

  set = 0;

  printf("Reading %s in 64-bit. Writing to %s in 128-bit\n", argv[1], argv[2]);

  // Open both files
  infile = fopen(argv[1], "r");
  outfile = fopen(argv[2], "w");  

  while ((size = fread(&num, sizeof(UINT64), 1, infile))!=0){
    if (size==1) {
      char temp_str[255];
      __bid64_to_string(temp_str, &num);
      __bid128_from_string(&num128, temp_str, &set);
      fwrite(&num128, sizeof(UINT128), 1, outfile);
    }
  }

  printf("Closing files\n");
  fclose(infile);
  fclose(outfile);
  return 0;

}


