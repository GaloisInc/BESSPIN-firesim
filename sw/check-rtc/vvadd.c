#include <stdlib.h>
#include <stdio.h>
#include "util.h"
#include "mmio.h"

#define ARRAY_SIZE 4096
#define STRIDE 4096
#define NUM_ITERS 10
int a[ARRAY_SIZE * STRIDE];
int b[ARRAY_SIZE * STRIDE];
int c[ARRAY_SIZE * STRIDE];


int main(void)
{
  	printf("Starting vvadd\n");
    for (int count = 0; count < NUM_ITERS; count++) {
        for (int i = 0; i < ARRAY_SIZE; i++) {
            c[i * STRIDE] += a[i * STRIDE] * b[i * STRIDE];
        }
    }
	printf("%ld cycles\n", rdcycle());

	return 0;
}
