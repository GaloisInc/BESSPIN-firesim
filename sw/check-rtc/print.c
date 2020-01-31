#include <stdlib.h>
#include <stdio.h>
#include "util.h"
#include "mmio.h"

#define ARRAY_SIZE 64

int main(void)
{
    for (int i = 0; i < ARRAY_SIZE; i++) {
        for (int j = 0; j < ARRAY_SIZE; j++) {
  	        printf("Tuple: (%u, %u)\n", i, j);
        }
    }
  	printf("Cycles to completion: %lu\n", rdcycle());
	return 0;
}
