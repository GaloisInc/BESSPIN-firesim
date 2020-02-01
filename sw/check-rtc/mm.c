#include <stdlib.h>
#include <stdio.h>
#include "util.h"
#include "mmio.h"

#define ARRAY_SIZE 16
#define ARRAY_DIM_B 16
int a[ARRAY_SIZE * ARRAY_DIM_B];
int b[ARRAY_SIZE * ARRAY_DIM_B];
int c[ARRAY_SIZE * ARRAY_SIZE];


int main(void) {
  	printf("Starting matmul\n");
    for (int i = 0; i < ARRAY_SIZE; i+=1) {
        for (int j = 0; j < ARRAY_SIZE; j+=1) {
            for (int k = 0; k < ARRAY_DIM_B; k+=1) {
                 c[i * ARRAY_SIZE + j] += a[i * ARRAY_SIZE + k] * b[k * ARRAY_SIZE + j];
            }
        }
    }
	printf("%ld cycles\n", rdcycle());
	return 0;
}
