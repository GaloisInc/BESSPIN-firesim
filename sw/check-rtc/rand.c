#include <stdlib.h>
#include <stdio.h>
#include "util.h"
#include "mmio.h"

#define ARRAY_SIZE (256 * 256)
#define NUM_ITERS  1000000
int a[ARRAY_SIZE];

int main(void)
{
    long i = 0;
    uint16_t lfsr = 5;
    uint16_t bit;

    for (int i = 0; i < NUM_ITERS; i++) {
        bit = ((lfsr >> 0) ^ (lfsr >> 2) ^ (lfsr >> 3) ^ (lfsr >> 5)) /* & 1u */;
        lfsr = (lfsr >> 1) | (bit << 15);
        a[ARRAY_SIZE - lfsr] = a[lfsr];
    }
	printf("%ld cycles\n", rdcycle());
	return 0;
}
