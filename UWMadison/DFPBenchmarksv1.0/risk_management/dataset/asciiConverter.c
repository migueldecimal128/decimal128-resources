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


#ifdef BID 
  #include "../bid_conf.h"
  #include "../bid_functions.h"
  #define decIEEE_t UINT64 
#elif defined(DEC32)
 #include "../decimal32.h"
 #define decIEEE_t decimal32
#elif defined(DEC128)
 #include "../decimal128.h"
 #define decIEEE_t decimal128
#else
 #include "../decimal64.h"
 #define decIEEE_t decimal64
#endif

#define MAX_BUF_SIZE 100
typedef struct cmd_struct{
  decIEEE_t index;
  decIEEE_t volume;
  decIEEE_t split;
  decIEEE_t dividend;
}cmd_t;

int main(int argc, char *argv[]){
  FILE *inp = NULL;
  FILE *oup = NULL;
  char strin[100];
  char strout[100];

  char msg[100];
  char index[MAX_BUF_SIZE], volume[MAX_BUF_SIZE], split[MAX_BUF_SIZE], 
    dividend[MAX_BUF_SIZE];
  cmd_t cmd;

  FILE *cmp = NULL;
  int ret;
  char filename[100];

#ifdef BID
#define decIEEEFromString(Z, R, C) __bid64_from_string(Z, R, C)
  _IDEC_round set = ROUNDING_TIES_AWAY;
#elif defined(DEC32)
#define decIEEEFromString(Z, R, C) decimal32FromString(Z, R, C)
  decContext set;
  decContextDefault(&set, DEC_INIT_DECIMAL32);
#elif defined(DEC128)
#define decIEEEFromString(Z, R, C) decimal128FromString(Z, R, C)
  decContext set;
  decContextDefault(&set, DEC_INIT_DECIMAL128);
#else
#define decIEEEFromString(Z, R, C) decimal64FromString(Z, R, C)
  decContext set;
  decContextDefault(&set, DEC_INIT_DECIMAL64);
#endif

  DIR *dirp;
  struct direct *dp; //the file
  if ((dirp = opendir(DIRECTORY)) == NULL) {
    return -1;
  }
  do {
    errno = 0;
    strcpy(strin, DIRECTORY);
    strcpy(strout, BIN_DIRECTORY);
    if ((dp = readdir(dirp)) != NULL ) {
      char filename[100];
      strcpy (&filename[0], dp->d_name);
      if ((strcmp(&filename[0], ".")==0)||(strcmp(&filename[0], "..")==0)||
	  (strcmp(&filename[0], "README.txt")==0)){
        //Skip all the unrelated files
        continue;
      }
      strcat(strin, filename);
      strcat(strout, filename);
#ifdef BID 
      strcat(strout, ".bid");
#elif DEC32
      strcat(strout, ".d32");
#elif defined(DEC128)
      strcat(strout, ".d128");
#else
      strcat(strout, ".d64");
#endif

      inp = fopen(strin, "r");
      oup = fopen(strout, "wb");
      if (inp==NULL) return -1;
      if (oup==NULL) return -1;
      if (strcmp(&filename[0], "3month_tbill.cvs")==0){
	decIEEE_t temp2;
	ret = fscanf(inp, "%s", index);
	if (ret!=1) break;
	decIEEEFromString(&temp2, index, &set);
	fwrite(&temp2, sizeof(decIEEE_t), 1, oup);
      }
      else {
	do {
	  ret = fscanf(inp, "%s %s %s %s", index, volume, split, dividend);
	  if (ret!=4) break;
	  decIEEEFromString(&cmd.index, index, &set);
	  decIEEEFromString(&cmd.volume, volume, &set);
	  decIEEEFromString(&cmd.split, split, &set);
	  decIEEEFromString(&cmd.dividend, dividend, &set);
	  fwrite(&cmd, sizeof(cmd_t), 1, oup);
	}while (1);
      }
      fclose(inp);
      fclose(oup);
    }
  }while (dp != NULL);
}
