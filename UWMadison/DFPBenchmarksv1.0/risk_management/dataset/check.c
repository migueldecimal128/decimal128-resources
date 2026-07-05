#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <dirent.h>
#include <errno.h>
#define direct dirent

//Note: decimal128 has higher priority than others. Also, if decimal128 is 
//      declared, the decNumberDigit is fixed to 34 digits no matter if other
//      decimal format is declared or not.

#define DIRECTORY "ascii/"
#define BIN_DIRECTORY "bin/"

#ifdef DEC32
#include "decimal32.h"
#define decIEEE_t decimal32
#elif defined(DEC128)
#include "decimal128.h"
#define decIEEE_t decimal128
#else
#include "decimal64.h"
#define decIEEE_t decimal64
#endif
#define dec_t decNumber

#define MAX_BUF_SIZE 100
typedef struct cmd_struct{
  decIEEE_t index;
  decIEEE_t volume;
  decIEEE_t split;
  decIEEE_t dividend;
}cmdIEEE_t;

typedef struct cmdIEEE_struct{
  dec_t index;
  dec_t volume;
  dec_t split;
  dec_t dividend;
}cmd_t;

int main(int argc, char *argv[]){
  FILE *binp = NULL;
  FILE *orip = NULL;

  char strori[100];
  char strbin[100];

  char msg[100];
  char index[MAX_BUF_SIZE], volume[MAX_BUF_SIZE], split[MAX_BUF_SIZE], 
    dividend[MAX_BUF_SIZE];
  cmd_t cmd;
  cmdIEEE_t cmdIEEE;

  FILE *cmp = NULL;
  int ret1, ret2;
  char filename[100];

  dec_t index_dec, volume_dec, split_dec, dividend_dec, temp2;
  cmd_t temp1;
  decContext set, setIEEE;
#define decIEEEFromString(Z, R, C) decimal64FromString(Z, R, C)
  decContextDefault(&setIEEE, DEC_INIT_DECIMAL64);
  decContextDefault(&set, DEC_INIT_DECIMAL64);

  strcpy(strbin, 
	 "/home/lwang/Research/CCode/Risk/dataset/bin/sp500.csv.bnum64");
  strcpy(strori, 
	 "/home/lwang/Research/CCode/Risk/dataset/ascii/sp500.csv");
  binp = fopen(strbin, "rb");
  orip = fopen(strori, "r");

  if (binp==NULL) return -1;
  if (orip==NULL) return -1;
  do {
    char str[30];
    ret1 = fscanf(orip, "%s %s %s %s", index, volume, split, dividend);
    ret2 = fread(&temp1, sizeof(cmd_t), 1, binp);

    decNumberFromString(&index_dec   , index, &set);
    decNumberFromString(&volume_dec  , volume, &set);
    decNumberFromString(&split_dec   , split, &set);
    decNumberFromString(&dividend_dec, dividend, &set);
    
    decNumberCompare(&temp2, &temp1.index, &index_dec, &set);
    decNumberToString(&temp1.index, str);
    printf("index ascii is %s, index bin is %s\n", index, str);
    if (decNumberIsZero(&temp2)==0){
      decNumberToString(&temp1.index, str);
      printf("index, ascii index is %s and binary index is %s\n",
	     index, str);
      return -1;
    }
    decNumberCompare(&temp2, &temp1.volume, &volume_dec, &set);
    if (decNumberIsZero(&temp2)==0){
      decNumberToString(&temp1.volume, str);
      printf("index, ascii volume is %s and binary volume is %s\n",
             volume, str);
      return -1;
    }
    decNumberCompare(&temp2, &temp1.split, &split_dec, &set);
    if (decNumberIsZero(&temp2)==0){
      decNumberToString(&temp1.split, str);
      printf("index, ascii split is %s and binary split is %s\n",
             split, str);
      return -1;
    }
    decNumberCompare(&temp2, &temp1.dividend, &dividend_dec, &set);
    if (decNumberIsZero(&temp2)==0){
      decNumberToString(&temp1.dividend, str);
      printf("index, ascii dividend is %s and binary dividend is %s\n",
             dividend, str);
      return -1;
    }
  }while ((ret1!=EOF)&&(ret2!=EOF));
  printf("Done the execution\n");
  fclose(binp);
  fclose(orip);
  return 0;
}
