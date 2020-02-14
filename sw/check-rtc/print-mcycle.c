#include <stdio.h>

static inline long rdcycle(void)
{
	long cycle;
	asm volatile ("csrr %[cycle], cycle" : [cycle] "=r" (cycle));
	return cycle;
}

int main(void)
{
	printf("mcycle: %lu\n", rdcycle());
	return 0;
}
