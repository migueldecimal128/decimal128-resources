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
  decimal64 num;
  decimal128 num128;
  decContext set; 
  FILE *infile;
  FILE *outfile;

  printf("Reading %s in 64-bit. Writing to %s in 128-bit\n", argv[1], argv[2]);

  // Open both files
  infile = fopen(argv[1], "r");
  outfile = fopen(argv[2], "w");  
  decContextDefault(&set, DEC_INIT_DECIMAL128);

  while ((size = fread(&num, sizeof(decimal64), 1, infile))!=0){
    if (size==1) {
      char temp_str[255];
      decimal64ToString(&num, temp_str);
      decimal128FromString(&num128, temp_str, &set);
      fwrite(&num128, sizeof(decimal128), 1, outfile);
    }
  }

  printf("Closing files\n");
  fclose(infile);
  fclose(outfile);
  return 0;

}


