//----------------------------------------
// rate.c
// Currency Conversion Microbenchmark
// Decimal Floating-Point Benchmark
// header file to generate/access/update/close all the rate tables
// Developed by Liang-Kai Wang
// Department of Electrical and Computer Engineering
// University of Wisconsin-Madison
// $Revision: 1.2 $

#define DECIMAL_GLOBAL_EXCEPTION_FLAGS 1
#define DECNUMDIGITS 34
#include "dfp_includes.h"
  
int main(int argc, char *argv[]) {
  int size;
  int i;
  decimal64 num;
  UINT64 bid_num;
  _IDEC_round setp; 
  FILE *infile;
  FILE *outfile;

  printf("Reading %s in DPD. Writing to %s in BID\n", argv[1], argv[2]);

  // Open both files
  infile = fopen(argv[1], "r");
  outfile = fopen(argv[2], "w");  


  while ((size = fread(&num, sizeof(decimal64), 1, infile))!=0){
    if (size==1) {
      char temp_str[255];
      decimal64ToString(&num, temp_str);
      printf("String val: %s\n", temp_str);
      __bid64_from_string(&bid_num, temp_str, &setp);
      fwrite(&bid_num, sizeof(UINT64), 1, outfile);
    }
  }

  printf("Closing files\n");
  fclose(infile);
  fclose(outfile);
  return 0;

}


